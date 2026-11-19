import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.integrations.github.client import GitHubClient
from src.integrations.github.commits import fetch_repository_commits
from src.integrations.github.compare import fetch_compare_commits
from src.integrations.github.exceptions import (
    GitHubAuthenticationException,
    GitHubHTTP404Exception,
    GitHubNotFoundException,
    GitHubRateLimitException,
    GitHubServerException,
    GitHubTimeoutException,
)
from src.integrations.github.pagination import GitHubPaginator
from src.integrations.github.pull_requests import (
    fetch_pull_request_reviews,
    fetch_repository_pull_requests,
)
from src.integrations.github.repos import fetch_branch_head


def _make_mock_response(
    status_code: int = 200,
    json_data: Any = None,
    headers: Dict[str, str] | None = None,
    url: str = "https://api.github.com/test",
) -> httpx.Response:
    req = httpx.Request("GET", url)
    resp_headers = headers or {}
    content = json.dumps(json_data).encode("utf-8") if json_data is not None else b""
    return httpx.Response(status_code=status_code, headers=resp_headers, content=content, request=req)


# 1. Commit Pagination
@pytest.mark.asyncio
async def test_commit_pagination() -> None:
    mock_commits_p1 = [{"sha": f"sha_{i}", "commit": {"message": f"m_{i}"}} for i in range(100)]
    mock_commits_p2 = [{"sha": "sha_101", "commit": {"message": "m_101"}}]

    responses = [
        _make_mock_response(200, mock_commits_p1),
        _make_mock_response(200, mock_commits_p2),
    ]

    with patch.object(GitHubClient, "request_with_retry", side_effect=responses) as mock_req:
        commits_p1 = await fetch_repository_commits("token", "owner/repo", sha="main", page=1, per_page=100)
        commits_p2 = await fetch_repository_commits("token", "owner/repo", sha="main", page=2, per_page=100)

        assert len(commits_p1) == 100
        assert len(commits_p2) == 1
        assert mock_req.call_count == 2
        # Verify params
        call1_params = mock_req.call_args_list[0].kwargs["params"]
        assert call1_params == {"per_page": 100, "page": 1, "sha": "main"}
        call2_params = mock_req.call_args_list[1].kwargs["params"]
        assert call2_params == {"per_page": 100, "page": 2, "sha": "main"}


# 2. PR Pagination & Strict No-Since Rule
@pytest.mark.asyncio
async def test_pr_pagination_no_since_param() -> None:
    mock_prs = [{"id": 1, "number": 10, "title": "Test PR", "state": "open"}]
    resp = _make_mock_response(200, mock_prs)

    with patch.object(GitHubClient, "request_with_retry", return_value=resp) as mock_req:
        prs = await fetch_repository_pull_requests(
            token="token",
            full_name="owner/repo",
            page=1,
            per_page=100,
            since_date=datetime(2026, 1, 1, tzinfo=timezone.utc),  # Passed to function
        )
        assert len(prs) == 1
        params = mock_req.call_args.kwargs["params"]
        assert "since" not in params
        assert params["sort"] == "updated"
        assert params["direction"] == "desc"
        assert params["page"] == 1
        assert params["per_page"] == 100


# 3. Review Pagination
@pytest.mark.asyncio
async def test_review_pagination() -> None:
    mock_reviews_p1 = [{"id": i, "state": "APPROVED", "submitted_at": "2026-08-11T14:00:00Z"} for i in range(1, 101)]
    mock_reviews_p2 = [{"id": 101, "state": "COMMENTED", "submitted_at": "2026-08-12T10:00:00Z"}]

    responses = [
        _make_mock_response(200, mock_reviews_p1),
        _make_mock_response(200, mock_reviews_p2),
    ]

    with patch.object(GitHubClient, "request_with_retry", side_effect=responses) as mock_req:
        revs_p1 = await fetch_pull_request_reviews("token", "owner/repo", pull_number=42, page=1, per_page=100)
        revs_p2 = await fetch_pull_request_reviews("token", "owner/repo", pull_number=42, page=2, per_page=100)

        assert len(revs_p1) == 100
        assert len(revs_p2) == 1
        assert mock_req.call_args_list[0].kwargs["url"].endswith("/pulls/42/reviews")
        assert mock_req.call_args_list[0].kwargs["params"] == {"per_page": 100, "page": 1}
        assert mock_req.call_args_list[1].kwargs["params"] == {"per_page": 100, "page": 2}


# 4. Compare API Successful Responses
@pytest.mark.asyncio
async def test_compare_api_successful_responses() -> None:
    mock_payload = {
        "status": "ahead",
        "ahead_by": 3,
        "behind_by": 0,
        "total_commits": 3,
        "commits": [{"sha": "c1"}, {"sha": "c2"}, {"sha": "c3"}],
        "base_commit": {"sha": "base_sha"},
        "merge_base_commit": {"sha": "base_sha"},
    }
    resp = _make_mock_response(200, mock_payload)

    with patch.object(GitHubClient, "request_with_retry", return_value=resp) as mock_req:
        res = await fetch_compare_commits("token", "owner/repo", base="base_sha", head="head_sha", page=1)

        assert res["status"] == "ahead"
        assert res["ahead_by"] == 3
        assert len(res["commits"]) == 3
        assert res["base_commit"]["sha"] == "base_sha"
        url = mock_req.call_args.kwargs["url"]
        assert url.endswith("/compare/base_sha...head_sha")


# 5. Compare API Pagination
@pytest.mark.asyncio
async def test_compare_api_pagination() -> None:
    mock_payload = {
        "status": "ahead",
        "ahead_by": 150,
        "total_commits": 100,
        "commits": [{"sha": f"c_{i}"} for i in range(100)],
    }
    resp = _make_mock_response(200, mock_payload)

    with patch.object(GitHubClient, "request_with_retry", return_value=resp) as mock_req:
        res = await fetch_compare_commits("token", "owner/repo", base="base_sha", head="head_sha", page=2, per_page=100)

        assert len(res["commits"]) == 100
        params = mock_req.call_args.kwargs["params"]
        assert params["page"] == 2
        assert params["per_page"] == 100


# 6. Compare API Fallback & Error Scenarios
@pytest.mark.asyncio
async def test_compare_api_404_raises_not_found() -> None:
    resp_404 = _make_mock_response(404, {"message": "Not Found"})

    with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_client_req:
        mock_client_req.return_value = resp_404
        with pytest.raises(GitHubNotFoundException) as exc_info:
            await fetch_compare_commits("token", "owner/repo", base="pruned_sha", head="head_sha")

        assert isinstance(exc_info.value, GitHubHTTP404Exception)
        assert exc_info.value.status_code == 404


# 7. Rate-Limit Handling (Threshold Proactive Check & Payload Preservation)
def test_rate_limit_handling_threshold() -> None:
    # Remaining = 5 (below threshold 10) on a 200 OK response
    headers = {
        "X-RateLimit-Remaining": "5",
        "X-RateLimit-Reset": "1732000000",
    }
    resp = _make_mock_response(200, {"data": "valid_payload"}, headers=headers)

    # 1. Successful response does NOT raise and preserves payload
    is_low = GitHubClient.check_rate_limit(resp, threshold=10, raise_on_low_budget=False)
    assert is_low is True
    assert getattr(resp, "is_low_budget", False) is True
    assert getattr(resp, "rate_limit_remaining", None) == 5
    assert getattr(resp, "rate_limit_reset_at", None) == datetime.fromtimestamp(1732000000, tz=timezone.utc)
    assert GitHubClient.is_last_request_low_budget(threshold=10) is True

    # 2. check_response does not discard 2xx data
    GitHubClient.check_response(resp, rate_limit_threshold=10)
    assert resp.json() == {"data": "valid_payload"}

    # 3. Explicit raise_on_low_budget=True raises exception with preserved metadata
    with pytest.raises(GitHubRateLimitException) as exc_info:
        GitHubClient.check_rate_limit(resp, threshold=10, raise_on_low_budget=True)

    assert exc_info.value.remaining == 5
    assert exc_info.value.reset_at == datetime.fromtimestamp(1732000000, tz=timezone.utc)


@pytest.mark.asyncio
async def test_successful_response_preserves_payload_on_low_budget() -> None:
    mock_commits = [{"sha": "sha_success", "commit": {"message": "persisted commit"}}]
    headers = {
        "X-RateLimit-Remaining": "3",
        "X-RateLimit-Reset": "1732000000",
    }
    resp = _make_mock_response(200, mock_commits, headers=headers)

    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=resp):
        commits = await fetch_repository_commits("token", "owner/repo", sha="main")
        assert len(commits) == 1
        assert commits[0]["sha"] == "sha_success"
        assert getattr(resp, "is_low_budget", False) is True
        assert getattr(resp, "rate_limit_remaining", None) == 3
        assert GitHubClient.is_last_request_low_budget(threshold=10) is True


# 8. Retry-After Header Handling
def test_retry_after_handling() -> None:
    headers = {
        "Retry-After": "120",
    }
    resp = _make_mock_response(429, {"message": "Too Many Requests"}, headers=headers)

    with pytest.raises(GitHubRateLimitException) as exc_info:
        GitHubClient.check_rate_limit(resp)

    assert exc_info.value.retry_after == 120
    assert exc_info.value.status_code == 429
    assert exc_info.value.reset_at is not None


# 9. HTTP 403 & 429 Handling
def test_http_403_and_429_handling() -> None:
    # 429 rate limit
    resp_429 = _make_mock_response(429, {"message": "rate limit"})
    with pytest.raises(GitHubRateLimitException):
        GitHubClient.check_response(resp_429)

    # 403 with rate limit message
    resp_403_rl = _make_mock_response(403, {"message": "API rate limit exceeded for user"})
    with pytest.raises(GitHubRateLimitException):
        GitHubClient.check_response(resp_403_rl)

    # 403 with permission failure (not rate limit)
    resp_403_perm = _make_mock_response(403, {"message": "Resource not accessible by integration"}, headers={"X-RateLimit-Remaining": "4999"})
    with pytest.raises(GitHubAuthenticationException) as exc_info:
        GitHubClient.check_response(resp_403_perm)
    assert exc_info.value.status_code == 403


# 10. Transient Server Errors (5xx Retries)
@pytest.mark.asyncio
async def test_transient_server_errors_retry_recovery() -> None:
    resp_502 = _make_mock_response(502, {"message": "Bad Gateway"})
    resp_200 = _make_mock_response(200, [{"sha": "recovered_sha"}])

    mock_client = AsyncMock()
    mock_client.request.side_effect = [resp_502, resp_200]

    with patch("asyncio.sleep", new_callable=AsyncMock):
        resp = await GitHubClient.request_with_retry(
            method="GET",
            url="https://api.github.com/repos/owner/repo/commits",
            client=mock_client,
            max_retries=3,
        )
        assert resp.status_code == 200
        assert mock_client.request.call_count == 2


@pytest.mark.asyncio
async def test_transient_server_errors_exhaustion() -> None:
    resp_500 = _make_mock_response(500, {"message": "Internal Error"})

    mock_client = AsyncMock()
    mock_client.request.return_value = resp_500

    with patch("asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(GitHubServerException) as exc_info:
            await GitHubClient.request_with_retry(
                method="GET",
                url="https://api.github.com/repos/owner/repo/commits",
                client=mock_client,
                max_retries=3,
            )
        assert exc_info.value.status_code == 500
        assert mock_client.request.call_count == 3


# 11. Network Timeouts
@pytest.mark.asyncio
async def test_network_timeouts_retry_and_exhaustion() -> None:
    mock_client = AsyncMock()
    mock_client.request.side_effect = httpx.TimeoutException("Read timed out")

    with patch("asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(GitHubTimeoutException):
            await GitHubClient.request_with_retry(
                method="GET",
                url="https://api.github.com/repos/owner/repo/commits",
                client=mock_client,
                max_retries=2,
            )
        assert mock_client.request.call_count == 2


# 12. Empty Responses & Empty Repo 409 Handling
@pytest.mark.asyncio
async def test_empty_responses() -> None:
    resp_empty = _make_mock_response(200, [])
    with patch.object(GitHubClient, "request_with_retry", return_value=resp_empty):
        commits = await fetch_repository_commits("token", "owner/repo")
        assert commits == []

        prs = await fetch_repository_pull_requests("token", "owner/repo")
        assert prs == []

    # 409 Git Repository is empty
    resp_409 = _make_mock_response(409, {"message": "Git Repository is empty."})
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=resp_409):
        commits_empty_repo = await fetch_repository_commits("token", "owner/empty-repo")
        assert commits_empty_repo == []


# 13. Malformed / Unexpected Responses
def test_malformed_link_headers() -> None:
    assert GitHubClient.parse_link_header(None) == {}
    assert GitHubClient.parse_link_header("") == {}
    assert GitHubClient.parse_link_header("not a valid link header") == {}

    valid_header = '<https://api.github.com/repos/o/r/pulls?page=3>; rel="next", <https://api.github.com/repos/o/r/pulls?page=5>; rel="last"'
    links = GitHubClient.parse_link_header(valid_header)
    assert links["next"] == "https://api.github.com/repos/o/r/pulls?page=3"
    assert links["last"] == "https://api.github.com/repos/o/r/pulls?page=5"

    assert GitHubClient.get_next_page_from_link(valid_header) == 3
    assert GitHubClient.get_next_page_from_link('<https://api.github.com/repos/o/r/pulls>; rel="last"') is None


# 14. Pagination Termination Conditions (Correction 1 Requirements)
def test_pagination_termination_conditions() -> None:
    # 1. Short page with valid rel="next" -> continue
    link_next = '<https://api.github.com/repos/o/r/pulls?page=2>; rel="next"'
    next_p, exhausted = GitHubPaginator.calculate_next_page(current_page=1, items_count=50, per_page=100, link_header=link_next)
    assert next_p == 2
    assert exhausted is False

    # 2. Short page with Link header but no rel="next" -> terminate
    link_no_next = '<https://api.github.com/repos/o/r/pulls?page=1>; rel="prev"'
    next_p, exhausted = GitHubPaginator.calculate_next_page(current_page=2, items_count=50, per_page=100, link_header=link_no_next)
    assert next_p == 1
    assert exhausted is True

    # 3. Short page without Link header -> terminate
    next_p, exhausted = GitHubPaginator.calculate_next_page(current_page=1, items_count=50, per_page=100, link_header=None)
    assert next_p == 1
    assert exhausted is True

    # 4. Full page without Link header -> continue
    next_p, exhausted = GitHubPaginator.calculate_next_page(current_page=1, items_count=100, per_page=100, link_header=None)
    assert next_p == 2
    assert exhausted is False

    # 5. Empty page with valid next link -> follow Link header
    empty_with_next = '<https://api.github.com/repos/o/r/pulls?page=2>; rel="next"'
    next_p, exhausted = GitHubPaginator.calculate_next_page(current_page=1, items_count=0, per_page=100, link_header=empty_with_next)
    assert next_p == 2
    assert exhausted is False

    # 6. Empty page without Link header -> terminate
    next_p, exhausted = GitHubPaginator.calculate_next_page(current_page=3, items_count=0, per_page=100, link_header=None)
    assert next_p == 1
    assert exhausted is True


@pytest.mark.asyncio
async def test_paginator_follows_next_link_on_short_page() -> None:
    page_data = {
        1: ([{"id": 1}], '<https://api.github.com/repos/o/r/pulls?page=2>; rel="next"'),
        2: ([{"id": 2}], None),
    }

    async def mock_fetch(page: int, per_page: int) -> tuple[list[dict[str, Any]], str | None]:
        return page_data.get(page, ([], None))

    pages_collected = []
    items_collected = []
    async for page_num, items, _has_more in GitHubPaginator.paginate(
        fetch_page_fn=mock_fetch,  # type: ignore[arg-type]
        start_page=1,
        per_page=100,  # 1 item is shorter than per_page 100
        stop_on_short_page=True,
    ):
        pages_collected.append(page_num)
        items_collected.extend(items)

    # Page 1 had only 1 item (< 100), but had rel="next", so page 2 was fetched!
    assert pages_collected == [1, 2]
    assert len(items_collected) == 2


# 15. No Duplicate Page Fetching or Infinite Loops
@pytest.mark.asyncio
async def test_paginator_loop_prevention() -> None:
    """
    Verifies that if an API Link header loops back to an already visited page,
    the paginator detects the page cycle and terminates traversal without looping infinitely.
    """
    page_data = {
        1: ([{"id": 1}], '<https://api.github.com/repos/o/r/items?page=2>; rel="next"'),
        2: ([{"id": 2}], '<https://api.github.com/repos/o/r/items?page=1>; rel="next"'),
    }

    async def mock_fetch(page: int, per_page: int) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        return page_data.get(page, ([], None))

    results = []
    async for page_num, _items, _has_more in GitHubPaginator.paginate(
        fetch_page_fn=mock_fetch,  # type: ignore[arg-type]
        start_page=1,
        per_page=1,
        max_pages=10,
        stop_on_short_page=False,
    ):
        results.append(page_num)

    # Verify loop terminates after page 2 without repeating page 1
    assert results == [1, 2]


# 16. Mutable Dataset Deduplication and Continuation Across Duplicate Pages
@pytest.mark.asyncio
async def test_paginator_deduplicates_and_continues_on_duplicate_page() -> None:
    """
    Regression test:
    - Page 1 returns A, B, C.
    - Page 2 returns A, B, C again.
    - Page 2 includes a valid rel="next" Link header.
    - Page 3 returns D, E, F.
    - The paginator must yield A, B, C, D, E, F exactly once.
    """
    page_data = {
        1: (
            [{"id": "A"}, {"id": "B"}, {"id": "C"}],
            '<https://api.github.com/repos/o/r/items?page=2>; rel="next"',
        ),
        2: (
            [{"id": "A"}, {"id": "B"}, {"id": "C"}],
            '<https://api.github.com/repos/o/r/items?page=3>; rel="next"',
        ),
        3: (
            [{"id": "D"}, {"id": "E"}, {"id": "F"}],
            None,
        ),
    }

    async def mock_fetch(page: int, per_page: int) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        return page_data.get(page, ([], None))

    yielded_pages = []
    yielded_items: List[Dict[str, Any]] = []
    async for page_num, items, _has_more in GitHubPaginator.paginate(
        fetch_page_fn=mock_fetch,  # type: ignore[arg-type]
        start_page=1,
        per_page=100,
    ):
        yielded_pages.append(page_num)
        yielded_items.extend(items)

    assert yielded_pages == [1, 2, 3]
    item_ids = [item["id"] for item in yielded_items]
    assert item_ids == ["A", "B", "C", "D", "E", "F"]


@pytest.mark.asyncio
async def test_paginator_terminates_when_link_header_has_no_next() -> None:
    """Verifies pagination terminates when Link header is present but has no next link."""
    page_data = {
        1: (
            [{"id": "1"}, {"id": "2"}],
            '<https://api.github.com/repos/o/r/items?page=1>; rel="prev", <https://api.github.com/repos/o/r/items?page=1>; rel="first"',
        ),
    }

    async def mock_fetch(page: int, per_page: int) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        return page_data.get(page, ([], None))

    pages = []
    async for page_num, items, has_more in GitHubPaginator.paginate(
        fetch_page_fn=mock_fetch,  # type: ignore[arg-type]
        start_page=1,
    ):
        pages.append((page_num, len(items), has_more))

    assert len(pages) == 1
    assert pages[0] == (1, 2, False)


@pytest.mark.asyncio
async def test_paginator_terminates_on_empty_page_without_next_link() -> None:
    """Verifies pagination terminates immediately on an empty page without a next link."""
    async def mock_fetch(page: int, per_page: int) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        return ([], None)

    pages = []
    async for page_num, items, has_more in GitHubPaginator.paginate(
        fetch_page_fn=mock_fetch,  # type: ignore[arg-type]
        start_page=1,
    ):
        pages.append((page_num, len(items), has_more))

    assert len(pages) == 1
    assert pages[0] == (1, 0, False)


@pytest.mark.asyncio
async def test_paginator_terminates_at_max_pages_limit() -> None:
    """Verifies pagination respects maximum-page limit even when next links exist."""
    async def mock_fetch(page: int, per_page: int) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        next_url = f'<https://api.github.com/repos/o/r/items?page={page + 1}>; rel="next"'
        return ([{"id": f"item_{page}"}], next_url)

    pages = []
    async for page_num, items, has_more in GitHubPaginator.paginate(
        fetch_page_fn=mock_fetch,  # type: ignore[arg-type]
        start_page=1,
        max_pages=3,
    ):
        pages.append((page_num, len(items), has_more))

    assert len(pages) == 3
    assert [p[0] for p in pages] == [1, 2, 3]
    assert pages[-1][2] is False  # has_more is False on max page


@pytest.mark.asyncio
async def test_paginator_continues_past_twenty_duplicate_pages() -> None:
    """
    Verifies that pagination continues past >20 duplicate-only pages as long as
    the Link header provides a valid rel="next" link, reaching the subsequent new records.
    """
    total_pages = 25

    async def mock_fetch(page: int, per_page: int) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        if page < total_pages:
            next_link = f'<https://api.github.com/repos/o/r/items?page={page + 1}>; rel="next"'
            # Intermediate pages 1..24 return the same duplicate record
            return ([{"id": "seen_id"}], next_link)
        # Final page 25 returns a novel record and no next link
        return ([{"id": "new_record"}], None)

    yielded_pages = []
    yielded_items: List[Dict[str, Any]] = []
    async for page_num, items, _has_more in GitHubPaginator.paginate(
        fetch_page_fn=mock_fetch,  # type: ignore[arg-type]
        start_page=1,
        max_pages=50,
    ):
        yielded_pages.append(page_num)
        yielded_items.extend(items)

    assert len(yielded_pages) == total_pages
    assert yielded_pages == list(range(1, total_pages + 1))
    item_ids = [item["id"] for item in yielded_items]
    assert item_ids == ["seen_id", "new_record"]


@pytest.mark.asyncio
async def test_paginator_default_max_pages_bounds_unbounded_traversal() -> None:
    """
    Verifies that when max_pages is omitted (None), the default maximum-page bound
    (DEFAULT_MAX_PAGES = 100) safely halts an unbounded sequence of unique next-page URLs.
    """
    async def mock_fetch(page: int, per_page: int) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        next_url = f'<https://api.github.com/repos/o/r/items?page={page + 1}>; rel="next"'
        return ([{"id": f"item_{page}"}], next_url)

    pages = []
    async for page_num, items, has_more in GitHubPaginator.paginate(
        fetch_page_fn=mock_fetch,  # type: ignore[arg-type]
        start_page=1,
        max_pages=None,  # omits explicit limit, relies on DEFAULT_MAX_PAGES
    ):
        pages.append((page_num, len(items), has_more))

    assert len(pages) == GitHubPaginator.DEFAULT_MAX_PAGES
    assert pages[0][0] == 1
    assert pages[-1][0] == GitHubPaginator.DEFAULT_MAX_PAGES
    assert pages[-1][2] is False  # has_more is False on the final default page


# 17. Missing / Null Review IDs Normalization
@pytest.mark.asyncio
async def test_missing_or_null_review_ids() -> None:
    raw_reviews = [
        {"id": 12345, "state": "APPROVED", "submitted_at": "2026-08-11T14:00:00Z"},
        {"id": None, "state": "COMMENTED", "submitted_at": "2026-08-11T15:00:00Z"},
        {"state": "DISMISSED", "submitted_at": "2026-08-11T16:00:00Z"},  # missing id key
    ]
    resp = _make_mock_response(200, raw_reviews)

    with patch.object(GitHubClient, "request_with_retry", return_value=resp):
        normalized = await fetch_pull_request_reviews("token", "owner/repo", pull_number=99)

        assert len(normalized) == 3
        assert normalized[0]["github_review_id"] == "12345"
        assert normalized[1]["github_review_id"] is None
        assert normalized[2]["github_review_id"] is None


# 17. Fetch Branch Head
@pytest.mark.asyncio
async def test_fetch_branch_head() -> None:
    branch_data = {
        "name": "main",
        "commit": {
            "sha": "a1b2c3d4e5f67890",
            "url": "https://api.github.com/repos/owner/repo/commits/a1b2c3d4e5f67890",
        },
    }
    resp = _make_mock_response(200, branch_data)

    with patch.object(GitHubClient, "request_with_retry", return_value=resp) as mock_req:
        res = await fetch_branch_head("token", "owner/repo", branch="main")

        assert res["name"] == "main"
        assert res["commit"]["sha"] == "a1b2c3d4e5f67890"
        url = mock_req.call_args.kwargs["url"]
        assert url.endswith("/repos/owner/repo/branches/main")
