import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, cast

from asgiref.sync import async_to_sync
from celery import shared_task
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.future import select

from src.core.database import AsyncSessionLocal
from src.core.encryption import decrypt
from src.integrations.github.commits import fetch_repository_commits
from src.integrations.github.issues import fetch_repository_issues
from src.integrations.github.pull_requests import (
    fetch_pull_request_reviews,
    fetch_repository_pull_requests,
)
from src.modules.repositories.models import UserRepository
from src.modules.sync.models import SyncStatus, utc_now
from src.modules.sync.raw_models import (
    Commit,
    Issue,
    PullRequest,
    PullRequestReview,
)
from src.modules.sync.repository import SyncJobRepository
from src.modules.users.models import GitHubConnection

logger = logging.getLogger(__name__)


def _parse_iso(dt_str: str | None) -> datetime | None:
    if not dt_str:
        return None
    # ISO strings from GitHub (e.g., 2026-08-10T12:00:00Z)
    clean_str = dt_str.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(clean_str)
    except Exception:
        return None


async def _run_sync(job_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        sync_repo = SyncJobRepository(session)
        job = await sync_repo.get_by_id(job_id)

        if not job or job.status != SyncStatus.QUEUED:
            return

        # Mark as running
        job.status = SyncStatus.RUNNING
        job_data = cast(Dict[str, Any], job.progress_data or {})
        job.progress_data = {
            **job_data,
            "stage": "repository_metadata",
            "message": "Starting sync...",
        }
        await sync_repo.update(job)
        await session.commit()

        # Get repository to sync
        user_repo = await session.get(UserRepository, job.user_repository_id)
        if not user_repo:
            job.status = SyncStatus.FAILED
            job.error_message = "Repository not found in database."
            job.finished_at = utc_now()
            await session.commit()
            return

        # Decrypt user token
        conn_res = await session.execute(
            select(GitHubConnection).where(GitHubConnection.user_id == user_repo.user_id)
        )
        connection = conn_res.scalar_one_or_none()
        if not connection or not connection.encrypted_access_token:
            job.status = SyncStatus.FAILED
            job.error_message = "GitHub connection or access token not found."
            job.finished_at = utc_now()
            await session.commit()
            return

        token = decrypt(str(connection.encrypted_access_token))
        full_name = str(user_repo.full_name)

        try:
            # 1. Repository metadata stage
            job_data = cast(Dict[str, Any], job.progress_data or {})
            job.progress_data = {**job_data, "stage": "repository_metadata"}
            await session.commit()

            # 2. Ingest Commits with pagination
            job_data = cast(Dict[str, Any], job.progress_data or {})
            job.progress_data = {**job_data, "stage": "commits", "message": "Fetching commits..."}
            await session.commit()

            commit_count = 0
            page = 1
            max_pages = 5  # fetch up to 500 recent commits for sync
            while page <= max_pages:
                raw_commits = await fetch_repository_commits(
                    token=token, full_name=full_name, page=page, per_page=100
                )
                if not raw_commits:
                    break

                for c in raw_commits:
                    sha = c.get("sha")
                    if not sha:
                        continue
                    commit_obj = c.get("commit") or {}
                    author_data = commit_obj.get("author") or {}
                    author_name = author_data.get("name")
                    author_email = author_data.get("email")
                    date_str = author_data.get("date")
                    authored_dt = _parse_iso(date_str) or datetime.now(timezone.utc)
                    msg = commit_obj.get("message")

                    stmt = (
                        insert(Commit)
                        .values(
                            id=uuid.uuid4(),
                            user_repository_id=user_repo.id,
                            sha=sha,
                            author_name=author_name,
                            author_email=author_email,
                            authored_date=authored_dt,
                            message=msg,
                            created_at=utc_now(),
                        )
                        .on_conflict_do_update(
                            index_elements=["user_repository_id", "sha"],
                            set_={
                                "author_name": author_name,
                                "author_email": author_email,
                                "authored_date": authored_dt,
                                "message": msg,
                            },
                        )
                    )
                    await session.execute(stmt)
                    commit_count += 1

                await session.commit()
                if len(raw_commits) < 100:
                    break
                page += 1

            # 3. Ingest Pull Requests with pagination and reviews
            job_data = cast(Dict[str, Any], job.progress_data or {})
            job.progress_data = {
                **job_data,
                "stage": "pull_requests",
                "commits": commit_count,
                "message": "Fetching pull requests and reviews...",
            }
            await session.commit()

            pr_count = 0
            page = 1
            while page <= max_pages:
                raw_prs = await fetch_repository_pull_requests(
                    token=token, full_name=full_name, page=page, per_page=100
                )
                if not raw_prs:
                    break

                for pr_data in raw_prs:
                    pr_number = pr_data.get("number")
                    if pr_number is None:
                        continue
                    github_pr_id = str(pr_data.get("id")) if pr_data.get("id") else None
                    title = pr_data.get("title")
                    state = pr_data.get("state", "open")
                    user_info = pr_data.get("user") or {}
                    author_login = user_info.get("login")

                    created_at = _parse_iso(pr_data.get("created_at")) or datetime.now(timezone.utc)
                    updated_at = _parse_iso(pr_data.get("updated_at")) or datetime.now(timezone.utc)
                    closed_at = _parse_iso(pr_data.get("closed_at"))
                    merged_at = _parse_iso(pr_data.get("merged_at"))

                    # Upsert pull request
                    pr_id = uuid.uuid4()
                    pr_stmt = (
                        insert(PullRequest)
                        .values(
                            id=pr_id,
                            user_repository_id=user_repo.id,
                            github_pr_id=github_pr_id,
                            number=pr_number,
                            title=title,
                            state=state,
                            author_login=author_login,
                            created_at=created_at,
                            updated_at=updated_at,
                            closed_at=closed_at,
                            merged_at=merged_at,
                        )
                        .on_conflict_do_update(
                            index_elements=["user_repository_id", "number"],
                            set_={
                                "title": title,
                                "state": state,
                                "updated_at": updated_at,
                                "closed_at": closed_at,
                                "merged_at": merged_at,
                            },
                        )
                        .returning(PullRequest.id)
                    )
                    pr_res = await session.execute(pr_stmt)
                    persisted_pr_id = pr_res.scalar_one()

                    # Fetch reviews for this PR
                    try:
                        raw_reviews = await fetch_pull_request_reviews(
                            token=token, full_name=full_name, pull_number=pr_number
                        )
                        for r_data in raw_reviews:
                            review_id_str = str(r_data.get("id")) if r_data.get("id") else None
                            rev_user = r_data.get("user") or {}
                            rev_login = rev_user.get("login")
                            rev_state = r_data.get("state", "COMMENTED")
                            rev_submitted_at = _parse_iso(
                                r_data.get("submitted_at")
                            ) or datetime.now(timezone.utc)

                            # Check if review already exists to avoid duplicates
                            rev_check = await session.execute(
                                select(PullRequestReview).where(
                                    PullRequestReview.pull_request_id == persisted_pr_id,
                                    PullRequestReview.github_review_id == review_id_str,
                                )
                            )
                            existing_review = rev_check.scalar_one_or_none()
                            if existing_review:
                                existing_review.state = rev_state
                                existing_review.submitted_at = rev_submitted_at
                            else:
                                new_rev = PullRequestReview(
                                    id=cast(Any, uuid.uuid4()),
                                    pull_request_id=persisted_pr_id,
                                    github_review_id=review_id_str,
                                    user_login=rev_login,
                                    state=rev_state,
                                    submitted_at=rev_submitted_at,
                                )
                                session.add(new_rev)
                    except Exception as rev_err:
                        logger.warning("Failed to fetch reviews for PR #%s: %s", pr_number, rev_err)

                    pr_count += 1

                await session.commit()
                if len(raw_prs) < 100:
                    break
                page += 1

            # 4. Ingest Issues with pagination
            job_data = cast(Dict[str, Any], job.progress_data or {})
            job.progress_data = {
                **job_data,
                "stage": "issues",
                "pull_requests": pr_count,
                "message": "Fetching issues...",
            }
            await session.commit()

            issue_count = 0
            page = 1
            while page <= max_pages:
                raw_issues = await fetch_repository_issues(
                    token=token, full_name=full_name, page=page, per_page=100
                )
                if not raw_issues:
                    break

                for iss in raw_issues:
                    # In GitHub API, PRs are also returned under /issues. Skip if pull_request key is present.
                    if "pull_request" in iss:
                        continue

                    iss_num = iss.get("number")
                    if iss_num is None:
                        continue

                    gh_issue_id = str(iss.get("id")) if iss.get("id") else None
                    title = iss.get("title")
                    state = iss.get("state", "open")

                    # Check labels for bug identification
                    labels = iss.get("labels") or []
                    is_bug = False
                    for lbl in labels:
                        lbl_name = (
                            lbl.get("name", "") if isinstance(lbl, dict) else str(lbl)
                        ).lower()
                        if "bug" in lbl_name:
                            is_bug = True
                            break

                    iss_created_at = _parse_iso(iss.get("created_at")) or datetime.now(timezone.utc)
                    iss_updated_at = _parse_iso(iss.get("updated_at")) or datetime.now(timezone.utc)
                    iss_closed_at = _parse_iso(iss.get("closed_at"))

                    iss_stmt = (
                        insert(Issue)
                        .values(
                            id=uuid.uuid4(),
                            user_repository_id=user_repo.id,
                            github_issue_id=gh_issue_id,
                            number=iss_num,
                            title=title,
                            state=state,
                            is_bug=is_bug,
                            created_at=iss_created_at,
                            updated_at=iss_updated_at,
                            closed_at=iss_closed_at,
                        )
                        .on_conflict_do_update(
                            index_elements=["user_repository_id", "number"],
                            set_={
                                "title": title,
                                "state": state,
                                "is_bug": is_bug,
                                "updated_at": iss_updated_at,
                                "closed_at": iss_closed_at,
                            },
                        )
                    )
                    await session.execute(iss_stmt)
                    issue_count += 1

                await session.commit()
                if len(raw_issues) < 100:
                    break
                page += 1

            # Mark completed
            job.status = SyncStatus.COMPLETED
            job.finished_at = utc_now()
            job_data = cast(Dict[str, Any], job.progress_data or {})
            job.progress_data = {
                **job_data,
                "commits": commit_count,
                "pull_requests": pr_count,
                "issues": issue_count,
                "message": "Synchronization completed successfully.",
            }
            await session.commit()

            # Trigger analytics computation asynchronously without blocking sync
            try:
                from src.modules.analytics.tasks.compute_metrics import (
                    compute_repository_metrics_task,
                )

                compute_repository_metrics_task.delay(str(job.user_repository_id))
            except Exception as task_err:
                logger.warning(
                    "Failed to schedule analytics recalculation for repository %s: %s",
                    job.user_repository_id,
                    task_err,
                )

        except Exception as e:
            job.status = SyncStatus.FAILED
            job.error_message = str(e)
            job_data = cast(Dict[str, Any], job.progress_data or {})
            job.progress_data = {**job_data, "message": "Synchronization failed."}
            job.finished_at = utc_now()
            await session.commit()


@shared_task(name="sync_repository_task")
def sync_repository_task(job_id_str: str) -> None:
    job_id = uuid.UUID(job_id_str)
    async_to_sync(_run_sync)(job_id)
