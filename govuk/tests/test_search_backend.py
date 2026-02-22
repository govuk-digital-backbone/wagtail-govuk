from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from wagtail.models import Site

from govuk.models import (
    ContentDiscoverySettings,
    ContentDiscoverySource,
    ExternalContentItem,
    GovukTag,
)
from govuk.search_backend import search_backend


class SearchBackendExternalContentRankingTests(TestCase):
    def setUp(self):
        self.site = Site.objects.get(is_default_site=True)
        settings = ContentDiscoverySettings.for_site(self.site)
        self.source = ContentDiscoverySource.objects.create(
            settings=settings,
            sort_order=0,
            name="Default source",
            url="https://example.gov.uk/feed.xml",
        )

    def test_recently_updated_external_content_ranks_higher(self):
        query = "recent signal query"
        now = timezone.now()
        old_item = ExternalContentItem.objects.create(
            source=self.source,
            url="https://example.gov.uk/old",
            title="Recent signal query guidance",
            updated_at=now - timedelta(days=500),
            hidden=False,
        )
        new_item = ExternalContentItem.objects.create(
            source=self.source,
            url="https://example.gov.uk/new",
            title="Recent signal query guidance",
            updated_at=now - timedelta(days=2),
            hidden=False,
        )

        page = search_backend.search(query, page=1)
        urls_in_order = [result.url for result in page.object_list]

        self.assertIn(old_item.url, urls_in_order)
        self.assertIn(new_item.url, urls_in_order)
        self.assertEqual(urls_in_order[0], new_item.url)

    def test_source_name_and_tags_have_lower_impact_than_title_and_recency(self):
        query = "low weight source tag query"
        now = timezone.now()
        matching_tag = GovukTag.objects.create(
            slug="low-weight-source-tag-query",
            name="Low weight source tag query",
        )
        settings = ContentDiscoverySettings.for_site(self.site)
        source_match_source = ContentDiscoverySource.objects.create(
            settings=settings,
            sort_order=1,
            name="Low weight source tag query",
            url="https://example.gov.uk/source-match-feed.xml",
        )
        title_match_source = ContentDiscoverySource.objects.create(
            settings=settings,
            sort_order=2,
            name="Neutral source",
            url="https://example.gov.uk/neutral-feed.xml",
        )

        source_match_item = ExternalContentItem.objects.create(
            source=source_match_source,
            url="https://example.gov.uk/source-tag-match",
            title="Unrelated",
            summary="No direct title match",
            updated_at=now - timedelta(days=500),
            hidden=False,
        )
        source_match_item.tags.add(matching_tag)

        title_match_item = ExternalContentItem.objects.create(
            source=title_match_source,
            url="https://example.gov.uk/title-match",
            title="Low weight source tag query bulletin",
            summary="A direct title match",
            updated_at=now - timedelta(days=3),
            hidden=False,
        )

        page = search_backend.search(query, page=1)
        urls_in_order = [result.url for result in page.object_list]

        self.assertIn(source_match_item.url, urls_in_order)
        self.assertIn(title_match_item.url, urls_in_order)
        self.assertEqual(urls_in_order[0], title_match_item.url)
