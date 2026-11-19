from typing import Any, AsyncGenerator, Awaitable, Callable, List, Optional, Set, Tuple, Union

from src.integrations.github.client import GitHubClient


class GitHubPaginator:
    """
    Robust pagination utility ensuring deterministic traversal, loop prevention,
    and exact boundary handling matching V6.2 specifications.
    """

    DEFAULT_MAX_PAGES: int = 100

    @staticmethod
    def calculate_next_page(
        current_page: int,
        items_count: int,
        per_page: int = 100,
        link_header: Optional[str] = None,
    ) -> Tuple[int, bool]:
        """
        Determines the next page number and whether pagination has completed.

        Rules (Correction 1):
        1. When a Link header is present and contains rel="next", follow the next-page link
           even if the current page contains fewer than per_page items (or is empty).
        2. When a Link header is present but has no rel="next", treat pagination as exhausted.
        3. When a Link header is absent, use item-count-based fallback:
           - Empty page (items_count == 0) -> exhausted.
           - Short page (items_count < per_page) -> exhausted.
           - Full page (items_count >= per_page) -> continue (next page = current_page + 1).

        Returns:
            (next_page, is_exhausted)
        """
        # 1 & 2: Link header precedence when present
        if link_header is not None and link_header.strip():
            if 'rel="next"' in link_header:
                next_page = GitHubClient.get_next_page_from_link(link_header) or (current_page + 1)
                return next_page, False
            # Present but no rel="next" -> exhausted
            return 1, True

        # 3: Link header absent -> item-count-based fallback
        if items_count == 0 or items_count < per_page:
            return 1, True

        return current_page + 1, False

    @staticmethod
    def get_item_key(item: Any, item_id_key: Optional[str] = "id") -> Optional[Any]:
        """
        Extracts unique identifier from an item (dict or object) for deduplication.
        """
        if isinstance(item, dict):
            if item_id_key and item_id_key in item and item[item_id_key] is not None:
                return item[item_id_key]
            if "id" in item and item["id"] is not None:
                return item["id"]
            if "sha" in item and item["sha"] is not None:
                return item["sha"]
            return None
        if hasattr(item, "id"):
            return item.id
        if hasattr(item, "sha"):
            return item.sha
        return None

    @classmethod
    async def paginate(
        cls,
        fetch_page_fn: Callable[[int, int], Awaitable[Union[List[Any], Tuple[List[Any], Optional[str]]]]],
        start_page: int = 1,
        per_page: int = 100,
        max_pages: Optional[int] = None,
        stop_on_empty: bool = True,
        stop_on_short_page: bool = True,
        item_id_key: Optional[str] = "id",
    ) -> AsyncGenerator[Tuple[int, List[Any], bool], None]:
        """
        Asynchronously yields (page_number, novel_items, has_more) across pages.

        Guarantees:
        - Never visits the same page twice (guards against loops).
        - Tracks previously seen item identifiers and deduplicates yielded records.
        - Follows authoritative Link header rel="next" links even when intermediate pages
          contain only duplicate or empty records.
        - When no Link header exists, follows standard page-size boundary rules.
        - Bounds total pages using max_pages (or DEFAULT_MAX_PAGES if omitted).
        - Yields novel (unseen) items deterministically without duplicates.
        """
        clamped_per_page = min(max(1, per_page), 100)
        current_page = max(1, start_page)
        effective_max_pages = max_pages if max_pages is not None else cls.DEFAULT_MAX_PAGES
        pages_visited: Set[int] = set()
        seen_item_keys: Set[Any] = set()
        pages_count = 0

        while True:
            if pages_count >= effective_max_pages:
                break

            if current_page in pages_visited:
                # Cycle detected: abort to prevent infinite loop
                break

            pages_visited.add(current_page)
            pages_count += 1

            raw_result = await fetch_page_fn(current_page, clamped_per_page)
            raw_items: List[Any]
            link_header: Optional[str] = None

            if isinstance(raw_result, tuple) and len(raw_result) == 2:
                raw_items = list(raw_result[0])
                link_header = raw_result[1]
            else:
                raw_items = list(raw_result)

            # If raw response is empty and there is no rel="next", terminate
            if not raw_items and stop_on_empty and (link_header is None or 'rel="next"' not in link_header):
                yield (current_page, [], False)
                break

            # Deduplicate items: yield only novel (unseen) records
            novel_items: List[Any] = []
            for item in raw_items:
                key = cls.get_item_key(item, item_id_key)
                if key is not None:
                    if key in seen_item_keys:
                        continue
                    seen_item_keys.add(key)
                novel_items.append(item)

            # Determine next page and exhaustion status based on raw items count and Link header
            next_page, is_exhausted = cls.calculate_next_page(
                current_page=current_page,
                items_count=len(raw_items),
                per_page=clamped_per_page,
                link_header=link_header,
            )

            has_more = not is_exhausted
            if pages_count >= effective_max_pages:
                has_more = False

            yield (current_page, novel_items, has_more)

            # When Link header is absent and page is short, terminate if stop_on_short_page is True
            if link_header is None and len(raw_items) < clamped_per_page and stop_on_short_page:
                break

            if is_exhausted or not has_more:
                break

            if next_page in pages_visited:
                # Genuine page cycle: next page was already visited
                break

            current_page = next_page
