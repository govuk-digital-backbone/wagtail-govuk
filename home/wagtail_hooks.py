from django import forms
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from home.models import GovukTag


class GovukTagForm(forms.ModelForm):
    class Meta:
        model = GovukTag
        fields = ["slug", "name"]
        labels = {
            "slug": "Key",
            "name": "Value",
        }
        help_texts = {
            "slug": "Lowercase tag key, for example housing-benefit.",
            "name": "Human-readable label, for example Housing benefit.",
        }

    def clean_slug(self) -> str:
        slug = self.cleaned_data["slug"]
        return slug.strip().lower()


class GovukTagViewSet(SnippetViewSet):
    model = GovukTag
    form_class = GovukTagForm
    icon = "tag"
    add_to_admin_menu = True
    menu_label = "Tags"
    menu_name = "govuk-tags"
    menu_order = 200
    list_display = ["key", "value"]
    search_fields = ["slug", "name"]


register_snippet(GovukTagViewSet)
