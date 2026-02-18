from django.db import models
from wagtail import blocks
from wagtail.admin.panels import FieldPanel
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Page


class BaseContentPage(Page):
    body = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("body"),
    ]

    class Meta:
        abstract = True


class ContentPage(BaseContentPage):
    parent_page_types = ["home.ContentPage", "home.SectionPage"]
    subpage_types = ["home.ContentPage", "home.SectionPage"]


class SectionPage(Page):
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
        FieldPanel("hero_title"),
        FieldPanel("hero_intro"),
        FieldPanel("rows"),
        FieldPanel("free_text"),
    ]
