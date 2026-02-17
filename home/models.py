from wagtail.admin.panels import FieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Page


class BaseContentPage(Page):
    body = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("body"),
    ]

    class Meta:
        abstract = True


class HomePage(BaseContentPage):
    subpage_types = ["home.ContentPage"]


class ContentPage(BaseContentPage):
    parent_page_types = ["home.HomePage", "home.ContentPage"]
    subpage_types = ["home.ContentPage"]
