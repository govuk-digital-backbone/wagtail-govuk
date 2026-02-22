import hashlib

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import models
from django.db.models.functions import Coalesce
from django.utils.text import Truncator
from modelcluster.contrib.taggit import ClusterTaggableManager
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from taggit.models import TagBase, TaggedItemBase
from wagtail import blocks
from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.contrib.settings.models import BaseSiteSetting, register_setting
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Orderable, Page
from wagtail.snippets.blocks import SnippetChooserBlock


@register_setting(icon="warning")
class PhaseBannerSettings(BaseSiteSetting):
    enabled = models.BooleanField(
        default=False,
        verbose_name="Show phase banner across the site",
    )
    phase_label = models.CharField(
        max_length=20,
        default="Alpha",
        help_text="Label shown in the phase tag, for example Alpha or Beta.",
    )
    feedback_url = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="Feedback link URL, for example /feedback or https://example.gov.uk/feedback.",
    )

    panels = [
        FieldPanel("enabled"),
        FieldPanel("phase_label"),
        FieldPanel("feedback_url"),
    ]


@register_setting(icon="link")
class FooterSettings(BaseSiteSetting):
    footer_links = StreamField(
        [
            (
                "link",
                blocks.StructBlock(
                    [
                        (
                            "title",
                            blocks.CharBlock(
                                required=True,
                                max_length=120,
                            ),
                        ),
                        (
                            "url",
                            blocks.CharBlock(
                                required=True,
                                max_length=500,
                                help_text="Use a relative URL like /cookies or an absolute URL like https://www.gov.uk/help.",
                            ),
                        ),
                    ],
                    icon="link",
                    label="Footer link",
                ),
            )
        ],
        blank=True,
        help_text="Links shown in the footer support links list.",
    )

    panels = [
        FieldPanel("footer_links"),
    ]


@register_setting(icon="search")
class ContentDiscoverySettings(ClusterableModel, BaseSiteSetting):
    panels = [
        InlinePanel(
            "sources",
            heading="Content discovery sources",
            label="Source",
            help_text="Add one or more remote URLs for sitemaps, APIs, JSON feeds, RSS or Atom feeds.",
        ),
    ]

    class Meta:
        verbose_name = "Content discovery"
        verbose_name_plural = "Content discovery"


@register_setting(icon="redirect")
class AuthenticatedRedirectSettings(ClusterableModel, BaseSiteSetting):
    panels = [
        InlinePanel(
            "redirect_rules",
            heading="Authenticated user redirects",
            label="Redirect",
            help_text=(
                "Add one or more temporary redirects. "
                "When an authenticated user requests the source path, "
                "they are redirected to the destination path."
            ),
        ),
    ]

    class Meta:
        verbose_name = "Authenticated user redirects"
        verbose_name_plural = "Authenticated user redirects"


class AuthenticatedRedirectRule(Orderable):
    settings = ParentalKey(
        "govuk.AuthenticatedRedirectSettings",
        on_delete=models.CASCADE,
        related_name="redirect_rules",
    )
    source_path = models.CharField(
        max_length=255,
        help_text="Path to match, for example /.",
    )
    destination_path = models.CharField(
        max_length=500,
        help_text="Path to redirect to, for example /dashboard.",
    )

    panels = [
        FieldPanel("source_path"),
        FieldPanel("destination_path"),
    ]

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["settings", "source_path"],
                name="home_auth_redirect_source_path_unique_per_site",
            )
        ]

    def clean(self):
        super().clean()
        self.source_path = self._normalize_path(self.source_path)
        self.destination_path = self._normalize_path(self.destination_path)

        if not self.source_path.startswith("/"):
            raise ValidationError({"source_path": "Source path must start with '/'."})
        if "?" in self.source_path or "#" in self.source_path:
            raise ValidationError(
                {
                    "source_path": (
                        "Source path must not include a query string or fragment."
                    )
                }
            )
        if not self.destination_path.startswith("/"):
            raise ValidationError(
                {"destination_path": "Destination path must start with '/'."}
            )

        if self.source_path == self.destination_path:
            raise ValidationError(
                {
                    "destination_path": (
                        "Destination path must be different from source path."
                    )
                }
            )

    @staticmethod
    def _normalize_path(path: str) -> str:
        return (path or "").strip()

    def __str__(self) -> str:
        return f"{self.source_path} -> {self.destination_path}"


class GovukTag(TagBase):
    """Tag dictionary entry where slug is the key and name is the display value."""

    def clean(self):
        super().clean()
        if self.slug:
            self.slug = self.slug.strip().lower()

    @property
    def key(self) -> str:
        return self.slug

    @property
    def value(self) -> str:
        return self.name

    class Meta:
        verbose_name = "Tag"
        verbose_name_plural = "Tags"
        ordering = ["slug"]


class ContentDiscoverySource(Orderable):
    settings = ParentalKey(
        "govuk.ContentDiscoverySettings",
        on_delete=models.CASCADE,
        related_name="sources",
    )
    name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional display name for this source, for example Technology in government blog.",
    )
    url = models.URLField(
        max_length=500,
        help_text="Remote URL to discover content from, for example a sitemap, feed or API endpoint.",
    )
    disable_tls_verification = models.BooleanField(
        default=False,
        verbose_name="Disable TLS verification",
        help_text="When enabled, certificate verification is skipped for this source.",
    )
    default_tags = StreamField(
        [
            (
                "tag",
                SnippetChooserBlock(
                    "govuk.GovukTag",
                    required=False,
                ),
            )
        ],
        blank=True,
        use_json_field=True,
        help_text="Optional tags to apply to discovered content from this source.",
    )

    panels = [
        FieldPanel("name"),
        FieldPanel("url"),
        FieldPanel("disable_tls_verification"),
        FieldPanel("default_tags"),
    ]

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self) -> str:
        return self.name or self.url

    @staticmethod
    def _extract_tag_id(value) -> int | None:
        if type(value) is int and value > 0:
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.isdigit():
                parsed = int(stripped)
                if parsed > 0:
                    return parsed
        tag_pk = getattr(value, "pk", None)
        if type(tag_pk) is int and tag_pk > 0:
            return tag_pk
        if isinstance(value, dict):
            for key in ("value", "id", "pk"):
                extracted = ContentDiscoverySource._extract_tag_id(value.get(key))
                if extracted:
                    return extracted
        return None

    def get_default_tag_ids(self) -> list[int]:
        tag_ids: list[int] = []
        seen: set[int] = set()

        for block in self.default_tags:
            tag_id = self._extract_tag_id(getattr(block, "value", None))
            if tag_id and tag_id not in seen:
                tag_ids.append(tag_id)
                seen.add(tag_id)

        # Some environments return chooser values as raw IDs in JSON;
        # fall back to raw stream data if resolved block values yielded none.
        if not tag_ids:
            for raw_block in getattr(self.default_tags, "raw_data", []) or []:
                tag_id = self._extract_tag_id(raw_block)
                if tag_id and tag_id not in seen:
                    tag_ids.append(tag_id)
                    seen.add(tag_id)
        return tag_ids

    def get_default_tags(self) -> list["GovukTag"]:
        tag_ids = self.get_default_tag_ids()
        if not tag_ids:
            return []

        tags_by_id = {tag.pk: tag for tag in GovukTag.objects.filter(pk__in=tag_ids)}
        return [tags_by_id[tag_id] for tag_id in tag_ids if tag_id in tags_by_id]


class ExternalContentItemTag(TaggedItemBase):
    content_object = ParentalKey(
        "govuk.ExternalContentItem",
        related_name="tagged_items",
        on_delete=models.CASCADE,
    )
    tag = models.ForeignKey(
        "govuk.GovukTag",
        related_name="external_content_item_tagged_items",
        on_delete=models.CASCADE,
    )

    panels = [
        FieldPanel("tag"),
    ]


class ExternalContentItem(ClusterableModel):
    key = models.CharField(
        max_length=64,
        unique=True,
        editable=False,
        db_index=True,
        help_text="SHA256 hash of the URL.",
    )
    source = models.ForeignKey(
        "govuk.ContentDiscoverySource",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="external_content_items",
    )
    url = models.URLField(
        max_length=500,
        unique=True,
        help_text="Remote URL for the discovered content entry.",
    )
    title = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional title for this external content item.",
    )
    summary = models.TextField(
        blank=True,
        help_text="Optional summary or excerpt.",
    )
    published_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Optional publication date from the source.",
    )
    created_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Optional created date from the source.",
    )
    updated_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Optional updated date from the source.",
    )
    tags = ClusterTaggableManager(through="govuk.ExternalContentItemTag", blank=True)
    hidden = models.BooleanField(
        default=False,
        help_text="Hide this item from external content listings.",
    )
    metadata = models.JSONField(
        blank=True,
        default=dict,
        help_text="Optional source-specific metadata.",
    )
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    panels = [
        FieldPanel("source"),
        FieldPanel("url"),
        FieldPanel("title"),
        FieldPanel("summary"),
        FieldPanel("published_at"),
        FieldPanel("created_at"),
        FieldPanel("updated_at"),
        InlinePanel("tagged_items", heading="Tags", label="Tag"),
        FieldPanel("hidden"),
        FieldPanel("metadata"),
    ]

    class Meta:
        ordering = ["-last_seen_at", "title", "url"]

    @staticmethod
    def build_key(url: str) -> str:
        return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()

    def save(self, *args, **kwargs):
        self.url = self.url.strip()
        self.key = self.build_key(self.url)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.title or self.url

    @classmethod
    def upsert_from_url(cls, *, url: str, source=None, **defaults):
        normalized_url = url.strip()
        item, _ = cls.objects.update_or_create(
            url=normalized_url,
            defaults={"source": source, **defaults},
        )
        if source:
            source_tags = source.get_default_tags()
            if source_tags:
                existing_tag_ids = set(
                    item.tagged_items.values_list("tag_id", flat=True)
                )
                rows_to_add = [
                    ExternalContentItemTag(content_object=item, tag=source_tag)
                    for source_tag in source_tags
                    if source_tag.pk not in existing_tag_ids
                ]
                if rows_to_add:
                    ExternalContentItemTag.objects.bulk_create(
                        rows_to_add,
                        ignore_conflicts=True,
                    )
        return item


class ContentPageTag(TaggedItemBase):
    content_object = ParentalKey(
        "govuk.ContentPage",
        related_name="tagged_items",
        on_delete=models.CASCADE,
    )
    tag = models.ForeignKey(
        "govuk.GovukTag",
        related_name="content_page_tagged_items",
        on_delete=models.CASCADE,
    )

    panels = [
        FieldPanel("tag"),
    ]


class SectionPageTag(TaggedItemBase):
    content_object = ParentalKey(
        "govuk.SectionPage",
        related_name="tagged_items",
        on_delete=models.CASCADE,
    )
    tag = models.ForeignKey(
        "govuk.GovukTag",
        related_name="section_page_tagged_items",
        on_delete=models.CASCADE,
    )

    panels = [
        FieldPanel("tag"),
    ]


class TagListingsPageTag(TaggedItemBase):
    content_object = ParentalKey(
        "govuk.TagListingsPage",
        related_name="tagged_items",
        on_delete=models.CASCADE,
    )
    tag = models.ForeignKey(
        "govuk.GovukTag",
        related_name="tag_listings_page_tagged_items",
        on_delete=models.CASCADE,
    )

    panels = [
        FieldPanel("tag"),
    ]


class ContentPage(Page):
    parent_page_types = [
        "govuk.ContentPage",
        "govuk.SectionPage",
        "govuk.TagListingsPage",
    ]
    subpage_types = [
        "govuk.ContentPage",
        "govuk.SectionPage",
        "govuk.TagListingsPage",
    ]
    enable_hero_styling = models.BooleanField(
        default=False,
        verbose_name="Enable hero styling",
        help_text="When enabled, this page uses hero styling.",
    )
    enable_combined_service_navigation_and_hero_styling = models.BooleanField(
        default=False,
        verbose_name="Enable combined service navigation and hero styling",
        help_text="When enabled, this page uses a combined service navigation and hero styling.",
    )
    hero_title = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional hero heading. If blank, the page title is used.",
    )
    hero_intro = RichTextField(
        blank=True,
        features=["bold", "italic", "link"],
    )
    body = RichTextField(blank=True)
    enable_free_text_heading_navigation = models.BooleanField(
        default=False,
        verbose_name="Enable sidebar heading navigation",
        help_text="Show free text in a two-thirds and one-third layout with an automatic clickable heading list.",
    )
    tags = ClusterTaggableManager(through="govuk.ContentPageTag", blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("hero_title"),
        FieldPanel("hero_intro"),
        FieldPanel("body"),
    ]

    settings_panels = Page.settings_panels + [
        FieldPanel("enable_hero_styling"),
        FieldPanel("enable_combined_service_navigation_and_hero_styling"),
        FieldPanel("enable_free_text_heading_navigation"),
        InlinePanel("tagged_items", heading="Tags", label="Tag"),
    ]


class TagListingsPage(Page):
    enable_hero_styling = models.BooleanField(
        default=False,
        verbose_name="Enable hero styling",
        help_text="When enabled, this page uses hero styling.",
    )
    enable_combined_service_navigation_and_hero_styling = models.BooleanField(
        default=False,
        verbose_name="Enable combined service navigation and hero styling",
        help_text="When enabled, this page uses a combined service navigation and hero styling.",
    )
    hero_title = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional hero heading. If blank, the page title is used.",
    )
    hero_intro = RichTextField(
        blank=True,
        features=["bold", "italic", "link"],
    )
    free_text = RichTextField(blank=True)
    enable_free_text_heading_navigation = models.BooleanField(
        default=False,
        verbose_name="Enable sidebar heading navigation",
        help_text="Show free text in a two-thirds and one-third layout with an automatic clickable heading list.",
    )
    enable_tag_filter = models.BooleanField(
        default=False,
        verbose_name="Enable tag filter",
        help_text="Show a tag filter control above the listings.",
    )
    enable_source_filter = models.BooleanField(
        default=False,
        verbose_name="Enable source filter",
        help_text="Show a source filter control above the listings.",
    )
    tags = ClusterTaggableManager(
        through="govuk.TagListingsPageTag",
        blank=True,
    )

    parent_page_types = [
        "govuk.ContentPage",
        "govuk.SectionPage",
        "govuk.TagListingsPage",
    ]
    subpage_types = [
        "govuk.ContentPage",
        "govuk.SectionPage",
        "govuk.TagListingsPage",
    ]

    content_panels = Page.content_panels + [
        FieldPanel("hero_title"),
        FieldPanel("hero_intro"),
        InlinePanel("tagged_items", heading="Tags to list", label="Tag", min_num=1),
        FieldPanel("free_text"),
    ]

    settings_panels = Page.settings_panels + [
        FieldPanel("enable_hero_styling"),
        FieldPanel("enable_combined_service_navigation_and_hero_styling"),
        FieldPanel("enable_tag_filter"),
        FieldPanel("enable_source_filter"),
        FieldPanel("enable_free_text_heading_navigation"),
    ]

    def get_listing_queryset(self):
        # Keep this as the single data-source entry point so other tagged card
        # sources can be merged in future.
        queryset = ExternalContentItem.objects.filter(hidden=False)
        configured_tag_ids = list(self.tags.values_list("id", flat=True))
        if configured_tag_ids:
            queryset = queryset.filter(tags__id__in=configured_tag_ids)

        return queryset.distinct()

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        queryset = (
            self.get_listing_queryset()
            .annotate(
                sort_updated=Coalesce(
                    "updated_at",
                    "created_at",
                    "published_at",
                    "last_seen_at",
                    "first_seen_at",
                )
            )
            .order_by("-sort_updated", "-id")
        )

        available_tags = list(self.tags.all())
        selected_tag = None
        selected_tag_slug = ""
        if self.enable_tag_filter:
            selected_tag_slug = (request.GET.get("tag") or "").strip().lower()
            if selected_tag_slug:
                selected_tag = next(
                    (tag for tag in available_tags if tag.slug == selected_tag_slug),
                    None,
                )
                if selected_tag is not None:
                    queryset = queryset.filter(tags__id=selected_tag.id)

        available_sources = []
        selected_source_id = ""
        selected_source_label = ""
        source_rows = (
            self.get_listing_queryset()
            .exclude(source__isnull=True)
            .values("source_id", "source__name", "source__url")
            .distinct()
            .order_by("source__name", "source__url")
        )
        for source_row in source_rows:
            source_id = source_row["source_id"]
            if source_id is None:
                continue
            source_label = (
                source_row["source__name"] or source_row["source__url"] or ""
            ).strip()
            if not source_label:
                continue
            available_sources.append(
                {
                    "id": str(source_id),
                    "label": source_label,
                }
            )

        if self.enable_source_filter:
            selected_source_id = (request.GET.get("source") or "").strip()
            selected_source = next(
                (
                    source
                    for source in available_sources
                    if source["id"] == selected_source_id
                ),
                None,
            )
            if selected_source is not None:
                queryset = queryset.filter(source_id=int(selected_source_id))
                selected_source_label = selected_source["label"]
            else:
                selected_source_id = ""

        paginator = Paginator(queryset, 15)
        context["listing_items"] = paginator.get_page(request.GET.get("page"))
        context["available_tags"] = available_tags
        context["available_sources"] = available_sources
        context["selected_tag"] = selected_tag
        context["selected_source_id"] = selected_source_id
        context["selected_source_label"] = selected_source_label
        return context


class SectionPage(Page):
    enable_hero_styling = models.BooleanField(
        default=False,
        verbose_name="Enable hero styling",
        help_text="When enabled, this page uses hero styling.",
    )
    enable_combined_service_navigation_and_hero_styling = models.BooleanField(
        default=False,
        verbose_name="Enable combined service navigation and hero styling",
        help_text="When enabled, this page uses a combined service navigation and hero styling.",
    )
    hero_title = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional hero heading. If blank, the page title is used.",
    )
    hero_intro = RichTextField(
        blank=True,
        features=["bold", "italic", "link"],
    )
    tags = ClusterTaggableManager(through="govuk.SectionPageTag", blank=True)
    rows = StreamField(
        [
            (
                "row",
                blocks.StructBlock(
                    [
                        (
                            "heading",
                            blocks.CharBlock(
                                required=False,
                                help_text="Optional heading for this row section.",
                            ),
                        ),
                        (
                            "cards",
                            blocks.ListBlock(
                                blocks.StructBlock(
                                    [
                                        (
                                            "title",
                                            blocks.CharBlock(
                                                required=True,
                                                max_length=120,
                                            ),
                                        ),
                                        (
                                            "text",
                                            blocks.RichTextBlock(
                                                required=False,
                                                features=[
                                                    "bold",
                                                    "italic",
                                                    "link",
                                                    "ul",
                                                    "ol",
                                                ],
                                            ),
                                        ),
                                        (
                                            "link_text",
                                            blocks.CharBlock(
                                                required=False,
                                                max_length=80,
                                                help_text="Optional button text.",
                                            ),
                                        ),
                                        (
                                            "link_url",
                                            blocks.CharBlock(
                                                required=False,
                                                max_length=500,
                                                help_text="Optional URL for the button, for example /apply or https://example.gov.uk/apply.",
                                            ),
                                        ),
                                        (
                                            "tags",
                                            blocks.ListBlock(
                                                SnippetChooserBlock(
                                                    "govuk.GovukTag",
                                                    required=False,
                                                ),
                                                required=False,
                                                help_text="Optional tags for this card.",
                                            ),
                                        ),
                                    ],
                                    icon="doc-full",
                                    label="Card",
                                ),
                                min_num=1,
                                max_num=15,
                                help_text="Add between 1 and 15 cards in this row.",
                            ),
                        ),
                    ],
                    icon="placeholder",
                    label="Row section",
                ),
            ),
        ],
        blank=True,
        help_text="Add one or more row sections. Each row can contain up to 15 cards.",
    )
    free_text = RichTextField(blank=True)
    enable_free_text_heading_navigation = models.BooleanField(
        default=False,
        verbose_name="Enable sidebar heading navigation",
        help_text="Show free text in a two-thirds and one-third layout with an automatic clickable heading list.",
    )

    parent_page_types = [
        "govuk.ContentPage",
        "govuk.SectionPage",
        "govuk.TagListingsPage",
    ]
    subpage_types = [
        "govuk.ContentPage",
        "govuk.SectionPage",
        "govuk.TagListingsPage",
    ]

    content_panels = Page.content_panels + [
        FieldPanel("hero_title"),
        FieldPanel("hero_intro"),
        FieldPanel("rows"),
        FieldPanel("free_text"),
    ]

    settings_panels = Page.settings_panels + [
        FieldPanel("enable_hero_styling"),
        FieldPanel("enable_combined_service_navigation_and_hero_styling"),
        FieldPanel("enable_free_text_heading_navigation"),
        InlinePanel("tagged_items", heading="Tags", label="Tag"),
    ]


class Feedback(models.Model):
    class FeedbackType(models.TextChoices):
        CORRECTION = "correction", "Correction"
        FEATURE_SUGGESTION = "feature_suggestion", "Feature suggestion"
        BUG_REPORT = "bug_report", "Bug report"
        CONTENT_REQUEST = "content_request", "Content request"
        GENERAL = "general", "General feedback"
        OTHER = "other", "Other"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="feedback_entries",
    )
    name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    feedback_type = models.CharField(
        max_length=40,
        choices=FeedbackType.choices,
        default=FeedbackType.GENERAL,
    )
    comments = models.TextField()
    referrer = models.CharField(max_length=500, blank=True)
    browser = models.CharField(max_length=255, blank=True)
    is_mobile = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        label = self.name or "Unknown user"
        return f"{label} - {self.get_feedback_type_display()}"

    def feedback_type_label(self) -> str:
        return self.get_feedback_type_display()

    feedback_type_label.short_description = "Type"

    def comments_preview(self) -> str:
        return Truncator(self.comments).chars(50)

    comments_preview.short_description = "Feedback"


__all__ = [
    "AuthenticatedRedirectRule",
    "AuthenticatedRedirectSettings",
    "ContentDiscoverySettings",
    "ContentDiscoverySource",
    "ContentPage",
    "ContentPageTag",
    "ExternalContentItem",
    "ExternalContentItemTag",
    "Feedback",
    "FooterSettings",
    "GovukTag",
    "PhaseBannerSettings",
    "SectionPage",
    "SectionPageTag",
    "TagListingsPage",
    "TagListingsPageTag",
]
