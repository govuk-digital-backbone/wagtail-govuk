from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.core.paginator import Page as PaginatorPage
from django.core.paginator import Paginator
from django.db import connections
from django.db.models import Q, QuerySet, TextField
from django.db.models.functions import Cast
from django.utils.html import strip_tags
from wagtail.models import Page, Site

from home.models import ContentPage, SectionPage

DEFAULT_PAGE_SIZE = 10
SEARCH_CONFIG = "english"
SEARCH_WEIGHTS = [0.1, 0.2, 0.4, 1.0]


@dataclass(slots=True)
class SearchResultItem:
    title: str
    search_description: str
    url: str
    score: float = 0.0


class SearchBackend:
    def search(
        self, query: str, filters: dict[str, Any] | None = None, page: int | str = 1
    ) -> PaginatorPage:
        filters = filters or {}
        clean_query = (query or "").strip()

        if not clean_query:
            paginator = Paginator([], self._page_size(filters))
            return paginator.get_page(page)

        page_results = self._build_page_results(clean_query, filters)
        hero_results = self._build_hero_results(clean_query, filters)
        card_results = self._build_card_results(clean_query, filters)
        tag_results = self._build_tag_results(clean_query, filters)
        combined_results = self._merge_results(
            page_results + hero_results + card_results + tag_results
        )

        paginator = Paginator(combined_results, self._page_size(filters))
        return paginator.get_page(page)

    def _build_page_results(
        self, query: str, filters: dict[str, Any]
    ) -> list[SearchResultItem]:
        queryset = self._apply_filters(Page.objects.all(), filters)
        if self._is_postgres(queryset.db):
            queryset = self._search_pages_postgres(queryset, query)
        else:
            queryset = self._search_pages_sqlite(queryset, query)

        request = filters.get("request")
        results: list[SearchResultItem] = []
        for page in queryset:
            specific_page = page.specific
            title = page.title
            description = page.search_description or ""
            tags_text = self._page_tags_text(specific_page)
            page_rank = float(getattr(page, "rank", 0.0) or 0.0)
            score = page_rank + self._text_relevance(
                query,
                (
                    (title, 3.0),
                    (page.seo_title, 2.0),
                    (description, 1.0),
                    (tags_text, 1.5),
                ),
            )
            if score <= 0:
                continue
            results.append(
                SearchResultItem(
                    title=title,
                    search_description=description,
                    url=self._page_url(page, request),
                    score=score,
                )
            )
        return results

    def _build_card_results(
        self, query: str, filters: dict[str, Any]
    ) -> list[SearchResultItem]:
        section_pages = self._apply_filters(SectionPage.objects.all(), filters)
        if self._is_postgres(section_pages.db):
            section_pages = self._search_sections_postgres(section_pages, query)
        else:
            section_pages = self._search_sections_sqlite(section_pages, query)

        request = filters.get("request")
        query_lower = query.lower()
        results: list[SearchResultItem] = []

        for section_page in section_pages:
            section_url = self._page_url(section_page, request)
            section_rank = float(getattr(section_page, "card_rank", 0.0) or 0.0)

            for card in self._section_cards(section_page):
                title = self._clean_text(card.get("title"))
                text = self._clean_text(card.get("text"))
                link_text = self._clean_text(card.get("link_text"))
                link_url = (card.get("link_url") or "").strip()
                tags_text = self._clean_text(" ".join(card.get("tags", [])))

                searchable_text = " ".join(
                    value
                    for value in (title, text, link_text, link_url, tags_text)
                    if value
                ).lower()
                if query_lower not in searchable_text:
                    continue

                score = section_rank + self._text_relevance(
                    query,
                    (
                        (title, 3.5),
                        (text, 2.0),
                        (link_text, 1.5),
                        (link_url, 1.0),
                        (tags_text, 2.0),
                    ),
                )
                results.append(
                    SearchResultItem(
                        title=title or section_page.title,
                        search_description=(
                            text
                            or section_page.search_description
                            or f"Card in {section_page.title}"
                        ),
                        url=link_url or section_url,
                        score=score,
                    )
                )

        return results

    def _build_tag_results(
        self, query: str, filters: dict[str, Any]
    ) -> list[SearchResultItem]:
        request = filters.get("request")
        results: list[SearchResultItem] = []

        for model in (ContentPage, SectionPage):
            queryset = self._apply_filters(
                model.objects.filter(
                    Q(tags__slug__icontains=query) | Q(tags__name__icontains=query)
                )
                .prefetch_related("tags")
                .distinct(),
                filters,
            )

            for page in queryset:
                tags_text = self._page_tags_text(page)
                score = self._text_relevance(query, ((tags_text, 3.0),))
                if score <= 0:
                    continue

                description = page.search_description or self._tag_result_description(page)
                results.append(
                    SearchResultItem(
                        title=page.title,
                        search_description=description,
                        url=self._page_url(page, request),
                        score=score,
                    )
                )

        return results

    def _build_hero_results(
        self, query: str, filters: dict[str, Any]
    ) -> list[SearchResultItem]:
        request = filters.get("request")
        results: list[SearchResultItem] = []

        for model in (ContentPage, SectionPage):
            queryset = self._apply_filters(model.objects.all(), filters)
            if self._is_postgres(queryset.db):
                queryset = self._search_hero_postgres(queryset, query)
            else:
                queryset = self._search_hero_sqlite(queryset, query)

            for page in queryset:
                hero_title = self._clean_text(getattr(page, "hero_title", ""))
                hero_intro = self._clean_text(getattr(page, "hero_intro", ""))
                score = float(
                    getattr(page, "hero_rank", None)
                    or self._text_relevance(
                        query,
                        (
                            (hero_title, 3.0),
                            (hero_intro, 2.0),
                        ),
                    )
                )
                results.append(
                    SearchResultItem(
                        title=page.title,
                        search_description=hero_intro or page.search_description or "",
                        url=self._page_url(page, request),
                        score=score,
                    )
                )

        return results

    def _search_pages_sqlite(self, queryset: QuerySet, query: str) -> QuerySet:
        return queryset.filter(
            Q(title__icontains=query)
            | Q(seo_title__icontains=query)
            | Q(search_description__icontains=query)
        ).order_by("-first_published_at", "-latest_revision_created_at", "title")

    def _search_pages_postgres(self, queryset: QuerySet, query: str) -> QuerySet:
        search_vector = (
            SearchVector("title", weight="A", config=SEARCH_CONFIG)
            + SearchVector("seo_title", weight="B", config=SEARCH_CONFIG)
            + SearchVector("search_description", weight="C", config=SEARCH_CONFIG)
        )
        search_query = SearchQuery(query, search_type="websearch", config=SEARCH_CONFIG)
        return (
            queryset.annotate(
                rank=SearchRank(search_vector, search_query, weights=SEARCH_WEIGHTS),
            )
            .filter(rank__gt=0)
            .order_by("-rank", "-first_published_at", "title")
        )

    def _search_sections_sqlite(self, queryset: QuerySet, query: str) -> QuerySet:
        return queryset.filter(rows__icontains=query).order_by(
            "-first_published_at", "-latest_revision_created_at", "title"
        )

    def _search_sections_postgres(self, queryset: QuerySet, query: str) -> QuerySet:
        rows_vector = SearchVector(
            Cast("rows", TextField()),
            weight="D",
            config=SEARCH_CONFIG,
        )
        search_query = SearchQuery(query, search_type="websearch", config=SEARCH_CONFIG)
        return (
            queryset.annotate(
                card_rank=SearchRank(rows_vector, search_query, weights=SEARCH_WEIGHTS),
            )
            .filter(card_rank__gt=0)
            .order_by("-card_rank", "-first_published_at", "title")
        )

    def _search_hero_sqlite(self, queryset: QuerySet, query: str) -> QuerySet:
        return queryset.filter(
            Q(hero_title__icontains=query) | Q(hero_intro__icontains=query)
        ).order_by("-first_published_at", "-latest_revision_created_at", "title")

    def _search_hero_postgres(self, queryset: QuerySet, query: str) -> QuerySet:
        hero_vector = (
            SearchVector("hero_title", weight="A", config=SEARCH_CONFIG)
            + SearchVector(Cast("hero_intro", TextField()), weight="B", config=SEARCH_CONFIG)
        )
        search_query = SearchQuery(query, search_type="websearch", config=SEARCH_CONFIG)
        return (
            queryset.annotate(
                hero_rank=SearchRank(hero_vector, search_query, weights=SEARCH_WEIGHTS),
            )
            .filter(hero_rank__gt=0)
            .order_by("-hero_rank", "-first_published_at", "title")
        )

    def _apply_filters(self, queryset: QuerySet, filters: dict[str, Any]) -> QuerySet:
        if filters.get("live", True):
            queryset = queryset.live()
        if filters.get("public", True):
            queryset = queryset.public()

        site_or_root = filters.get("site")
        if site_or_root:
            root_page = (
                site_or_root.root_page if isinstance(site_or_root, Site) else site_or_root
            )
            queryset = queryset.descendant_of(
                root_page, inclusive=bool(filters.get("include_root", False))
            )

        exclude_ids = filters.get("exclude_ids")
        if exclude_ids:
            queryset = queryset.exclude(pk__in=exclude_ids)

        return queryset

    def _is_postgres(self, db_alias: str) -> bool:
        return connections[db_alias].vendor == "postgresql"

    def _section_cards(self, section_page: SectionPage) -> list[dict[str, Any]]:
        cards: list[dict[str, Any]] = []
        for block in section_page.rows:
            if block.block_type != "row":
                continue
            for card in block.value.get("cards", []):
                card_tags: list[str] = []
                for tag in card.get("tags", []):
                    tag_text = self._tag_text(tag)
                    if tag_text:
                        card_tags.append(tag_text)

                cards.append(
                    {
                        "title": card.get("title"),
                        "text": card.get("text"),
                        "link_text": card.get("link_text"),
                        "link_url": card.get("link_url"),
                        "tags": card_tags,
                    }
                )
        return cards

    def _page_url(self, page: Page, request) -> str:
        url = page.get_url(request=request)
        if url:
            return url
        return page.url or "#"

    def _clean_text(self, value: Any) -> str:
        if not value:
            return ""
        return " ".join(strip_tags(str(value)).split())

    def _tag_text(self, tag: Any) -> str:
        if not tag:
            return ""

        key = self._clean_text(getattr(tag, "slug", "") or getattr(tag, "key", ""))
        value = self._clean_text(getattr(tag, "name", "") or getattr(tag, "value", ""))
        if key or value:
            return " ".join(part for part in (key, value) if part)

        return self._clean_text(tag)

    def _page_tags_text(self, page: Any) -> str:
        tags_manager = getattr(page, "tags", None)
        if not tags_manager:
            return ""

        tags: list[str] = []
        for tag in tags_manager.all():
            tag_text = self._tag_text(tag)
            if tag_text:
                tags.append(tag_text)
        return " ".join(tags)

    def _tag_result_description(self, page: Any) -> str:
        tags_manager = getattr(page, "tags", None)
        if not tags_manager:
            return ""

        values: list[str] = []
        for tag in tags_manager.all():
            value = self._clean_text(getattr(tag, "name", ""))
            if value:
                values.append(value)
        if not values:
            return ""

        return f"Tagged: {', '.join(values)}"

    def _page_size(self, filters: dict[str, Any]) -> int:
        page_size = filters.get("page_size", DEFAULT_PAGE_SIZE)
        try:
            parsed_page_size = int(page_size)
        except (TypeError, ValueError):
            return DEFAULT_PAGE_SIZE
        return parsed_page_size if parsed_page_size > 0 else DEFAULT_PAGE_SIZE

    def _merge_results(self, results: list[SearchResultItem]) -> list[SearchResultItem]:
        unique_results: list[SearchResultItem] = []
        seen: set[tuple[str, str]] = set()

        for item in sorted(results, key=lambda item: (-item.score, item.title.lower())):
            key = (item.title.lower(), item.url)
            if key in seen:
                continue
            seen.add(key)
            unique_results.append(item)

        return unique_results

    def _text_relevance(
        self, query: str, weighted_values: tuple[tuple[Any, float], ...]
    ) -> float:
        query_lower = query.lower()
        terms = [term for term in query_lower.split() if term]
        score = 0.0

        for value, weight in weighted_values:
            text = self._clean_text(value).lower()
            if not text:
                continue
            if query_lower in text:
                score += 2.0 * weight
            for term in terms:
                if term in text:
                    score += 0.5 * weight
        return score


search_backend = SearchBackend()
