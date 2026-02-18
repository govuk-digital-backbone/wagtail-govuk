from django.db import models
from wagtail import blocks
from wagtail.admin.panels import FieldPanel
from wagtail.contrib.settings.models import BaseSiteSetting, register_setting
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Page


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


class ContentPage(Page):
    parent_page_types = ["home.ContentPage", "home.SectionPage"]
    subpage_types = ["home.ContentPage", "home.SectionPage"]
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

    content_panels = Page.content_panels + [
        FieldPanel("enable_hero_styling"),
        FieldPanel("enable_combined_service_navigation_and_hero_styling"),
        FieldPanel("hero_title"),
        FieldPanel("hero_intro"),
        FieldPanel("body"),
    ]


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

    parent_page_types = ["home.ContentPage", "home.SectionPage"]
    subpage_types = ["home.ContentPage", "home.SectionPage"]

    content_panels = Page.content_panels + [
        FieldPanel("enable_hero_styling"),
        FieldPanel("enable_combined_service_navigation_and_hero_styling"),
        FieldPanel("hero_title"),
        FieldPanel("hero_intro"),
        FieldPanel("rows"),
        FieldPanel("free_text"),
    ]
