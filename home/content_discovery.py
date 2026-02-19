from __future__ import annotations

import ssl

from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from home.models import ContentDiscoverySource, ExternalContentItem

ATOM_NAMESPACE = "http://www.w3.org/2005/Atom"
USER_AGENT = "wagtail-govuk-content-discovery/1.0"


class ContentDiscoveryError(RuntimeError):
    """Raised when remote discovery content cannot be fetched or parsed."""


@dataclass(slots=True)
class FeedEntry:
    format: str
    url: str
    title: str
    summary: str
    created_at: datetime | None
    updated_at: datetime | None
    entry_id: str
    author_names: list[str]
    published_raw: str
    updated_raw: str


@dataclass(slots=True)
class SourceSyncResult:
    source_id: int
    source_label: str
    source_url: str
    total_entries: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _qualified_name(name: str, namespace: str) -> str:
    if not namespace:
        return name
    return f"{{{namespace}}}{name}"


def _element_text(node: ElementTree.Element | None) -> str:
    if node is None:
        return ""
    text = "".join(node.itertext()).strip()
    if not text:
        return ""
    return unescape(text)


def _find_text(node: ElementTree.Element, name: str, namespace: str) -> str:
    return _element_text(node.find(_qualified_name(name, namespace)))


def _find_text_local_name(node: ElementTree.Element, *names: str) -> str:
    expected = {name.lower() for name in names}
    for child in list(node):
        if _local_name(child.tag) in expected:
            value = _element_text(child)
            if value:
                return value
    return ""


def _find_all_text_local_name(node: ElementTree.Element, *names: str) -> list[str]:
    expected = {name.lower() for name in names}
    values: list[str] = []
    for child in list(node):
        if _local_name(child.tag) not in expected:
            continue
        value = _element_text(child)
        if value:
            values.append(value)
    return values


def _parse_timestamp(value: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None

    dt = parse_datetime(value)
    if dt is None:
        try:
            dt = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None

    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, UTC)
    return dt.astimezone(UTC)


def _entry_link(entry_node: ElementTree.Element, namespace: str) -> str:
    link_nodes = entry_node.findall(_qualified_name("link", namespace))
    for link_node in link_nodes:
        href = (link_node.attrib.get("href") or "").strip()
        rel = (link_node.attrib.get("rel") or "alternate").strip().lower()
        if href and rel == "alternate":
            return href
    for link_node in link_nodes:
        href = (link_node.attrib.get("href") or "").strip()
        if href:
            return href
    return ""


def _parse_xml_root(xml_content: str | bytes) -> ElementTree.Element:
    try:
        return ElementTree.fromstring(xml_content)
    except ElementTree.ParseError as exc:
        raise ContentDiscoveryError("Response body is not valid XML.") from exc


def _parse_atom_root(root: ElementTree.Element) -> list[FeedEntry]:
    if _local_name(root.tag) != "feed":
        raise ContentDiscoveryError(
            "Unsupported content type: expected an Atom <feed> document."
        )

    namespace = ""
    if root.tag.startswith("{"):
        namespace = root.tag[1:].split("}", 1)[0]
        if namespace != ATOM_NAMESPACE:
            raise ContentDiscoveryError(
                "Unsupported XML namespace. Only Atom feeds are supported currently."
            )

    entries: list[FeedEntry] = []
    for entry_node in root.findall(_qualified_name("entry", namespace)):
        url = _entry_link(entry_node, namespace)
        title = _find_text(entry_node, "title", namespace)
        summary = _find_text(entry_node, "summary", namespace)
        if not summary:
            summary = _find_text(entry_node, "content", namespace)

        published_raw = _find_text(entry_node, "published", namespace)
        updated_raw = _find_text(entry_node, "updated", namespace)
        if not updated_raw:
            updated_raw = published_raw
        created_at = _parse_timestamp(published_raw or updated_raw)
        updated_at = _parse_timestamp(updated_raw or published_raw)

        author_names: list[str] = []
        for author_node in entry_node.findall(_qualified_name("author", namespace)):
            author_name = _find_text(author_node, "name", namespace)
            if author_name:
                author_names.append(author_name)

        entries.append(
            FeedEntry(
                format="atom",
                url=url,
                title=title,
                summary=summary,
                created_at=created_at,
                updated_at=updated_at,
                entry_id=_find_text(entry_node, "id", namespace) or url,
                author_names=author_names,
                published_raw=published_raw,
                updated_raw=updated_raw,
            )
        )

    return entries


def _parse_rss_root(root: ElementTree.Element) -> list[FeedEntry]:
    if _local_name(root.tag) != "rss":
        raise ContentDiscoveryError(
            "Unsupported content type: expected an RSS <rss> document."
        )

    channel_node = next(
        (child for child in list(root) if _local_name(child.tag) == "channel"),
        None,
    )
    if channel_node is None:
        raise ContentDiscoveryError(
            "Unsupported RSS document: missing required <channel> element."
        )

    entries: list[FeedEntry] = []
    for item_node in list(channel_node):
        if _local_name(item_node.tag) != "item":
            continue

        url = _find_text_local_name(item_node, "link")
        title = _find_text_local_name(item_node, "title")
        summary = _find_text_local_name(
            item_node,
            "description",
            "summary",
            "content",
            "encoded",
        )
        published_raw = _find_text_local_name(
            item_node,
            "pubDate",
            "published",
            "created",
            "date",
        )
        updated_raw = _find_text_local_name(
            item_node,
            "updated",
            "modified",
        )
        if not updated_raw:
            updated_raw = published_raw

        entries.append(
            FeedEntry(
                format="rss",
                url=url,
                title=title,
                summary=summary,
                created_at=_parse_timestamp(published_raw or updated_raw),
                updated_at=_parse_timestamp(updated_raw or published_raw),
                entry_id=_find_text_local_name(item_node, "guid", "id") or url,
                author_names=_find_all_text_local_name(item_node, "author", "creator"),
                published_raw=published_raw,
                updated_raw=updated_raw,
            )
        )

    return entries


def parse_atom_feed(xml_content: str | bytes) -> list[FeedEntry]:
    return _parse_atom_root(_parse_xml_root(xml_content))


def parse_rss_feed(xml_content: str | bytes) -> list[FeedEntry]:
    return _parse_rss_root(_parse_xml_root(xml_content))


def parse_feed(xml_content: str | bytes) -> list[FeedEntry]:
    root = _parse_xml_root(xml_content)
    root_name = _local_name(root.tag)
    if root_name == "feed":
        return _parse_atom_root(root)
    if root_name == "rss":
        return _parse_rss_root(root)

    raise ContentDiscoveryError(
        "Unsupported content type: expected an Atom <feed> or RSS <rss> document."
    )


def fetch_source_content(
    url: str, *, timeout: float = 15.0, disable_tls_verification: bool = False
) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/atom+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.1",
        },
    )

    request_kwargs = {"timeout": timeout}
    if disable_tls_verification:
        request_kwargs["context"] = ssl._create_unverified_context()

    try:
        with urlopen(request, **request_kwargs) as response:
            body = response.read()
    except (HTTPError, URLError, OSError) as exc:
        raise ContentDiscoveryError(f"Could not fetch '{url}': {exc}") from exc

    if not body:
        raise ContentDiscoveryError(
            f"Remote source '{url}' returned an empty response."
        )
    return body


def sync_content_discovery_source(
    source: ContentDiscoverySource, *, timeout: float = 15.0
) -> SourceSyncResult:
    feed_body = fetch_source_content(
        source.url,
        timeout=timeout,
        disable_tls_verification=source.disable_tls_verification,
    )
    entries = parse_feed(feed_body)

    result = SourceSyncResult(
        source_id=source.pk or 0,
        source_label=str(source),
        source_url=source.url,
    )
    existing_urls = set(
        ExternalContentItem.objects.filter(
            url__in=[entry.url for entry in entries]
        ).values_list("url", flat=True)
    )
    seen_urls: set[str] = set()

    for entry in entries:
        result.total_entries += 1
        entry_url = entry.url.strip()
        if not entry_url or entry_url in seen_urls:
            result.skipped += 1
            continue
        seen_urls.add(entry_url)

        metadata = {
            "format": entry.format,
            "entry_id": entry.entry_id,
            "author_names": entry.author_names,
            "published_raw": entry.published_raw,
            "updated_raw": entry.updated_raw,
        }
        metadata = {
            key: value
            for key, value in metadata.items()
            if value not in (None, "", [], {})
        }

        ExternalContentItem.upsert_from_url(
            url=entry_url,
            source=source,
            title=entry.title,
            summary=entry.summary,
            published_at=entry.created_at,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
            metadata=metadata,
        )

        if entry_url in existing_urls:
            result.updated += 1
        else:
            existing_urls.add(entry_url)
            result.created += 1

    return result


def sync_content_discovery_sources(
    sources: Iterable[ContentDiscoverySource], *, timeout: float = 15.0
) -> list[SourceSyncResult]:
    return [
        sync_content_discovery_source(source=source, timeout=timeout)
        for source in sources
    ]
