from django import forms
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse
from django.utils.http import url_has_allowed_host_and_scheme
from wagtail import hooks
from wagtail.admin import messages
from wagtail.admin.auth import permission_denied, require_admin_access
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from home.content_discovery import ContentDiscoveryError, sync_content_discovery_source
from home.models import (
    ContentDiscoverySettings,
    ContentDiscoverySource,
    ExternalContentItem,
    GovukTag,
)


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


class ExternalContentItemViewSet(SnippetViewSet):
    model = ExternalContentItem
    icon = "link"
    add_to_admin_menu = True
    menu_label = "External content"
    menu_name = "external-content"
    menu_order = 210
    list_display = [
        "title",
        "url",
        "key",
        "source",
        "created_at",
        "updated_at",
        "hidden",
        "last_seen_at",
    ]
    list_filter = ["hidden", "source"]
    search_fields = ["title", "url", "key"]


def _content_discovery_edit_url(site_id: int) -> str:
    return reverse("wagtailsettings:edit", args=("home", "contentdiscoverysettings", site_id))


def _safe_next_url(request, *, fallback_url: str) -> str:
    next_url = (request.POST.get("next") or "").strip()
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return fallback_url


def _user_can_change_content_discovery_setting(request, *, site) -> bool:
    permission_policy = ContentDiscoverySettings.get_permission_policy()
    return permission_policy.user_has_permission_for_instance(
        request.user,
        "change",
        site,
    )


@require_admin_access
def sync_content_discovery_source_view(request, source_id: int):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    source = get_object_or_404(
        ContentDiscoverySource.objects.select_related("settings__site"),
        pk=source_id,
    )
    if not _user_can_change_content_discovery_setting(request, site=source.settings.site):
        return permission_denied(request)

    fallback_url = _content_discovery_edit_url(source.settings.site_id)
    redirect_url = _safe_next_url(request, fallback_url=fallback_url)

    try:
        result = sync_content_discovery_source(source)
    except ContentDiscoveryError as exc:
        messages.error(request, f"Sync failed for '{source}': {exc}")
    else:
        messages.success(
            request,
            (
                f"Synced '{source}'. "
                f"Processed {result.total_entries}, created {result.created}, "
                f"updated {result.updated}, skipped {result.skipped}."
            ),
        )
    return redirect(redirect_url)


@require_admin_access
def sync_content_discovery_site_view(request, site_id: int):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    settings = get_object_or_404(ContentDiscoverySettings, site_id=site_id)
    if not _user_can_change_content_discovery_setting(request, site=settings.site):
        return permission_denied(request)

    fallback_url = _content_discovery_edit_url(site_id)
    redirect_url = _safe_next_url(request, fallback_url=fallback_url)

    sources = list(settings.sources.all())
    if not sources:
        messages.warning(request, "No content discovery sources are configured for this site.")
        return redirect(redirect_url)

    totals = {"entries": 0, "created": 0, "updated": 0, "skipped": 0}
    failed_sources: list[str] = []
    for source in sources:
        try:
            result = sync_content_discovery_source(source)
        except ContentDiscoveryError as exc:
            failed_sources.append(f"{source}: {exc}")
            continue

        totals["entries"] += result.total_entries
        totals["created"] += result.created
        totals["updated"] += result.updated
        totals["skipped"] += result.skipped

    if failed_sources:
        messages.error(
            request,
            "Some sources failed to sync: " + "; ".join(failed_sources),
        )
    if totals["entries"] or not failed_sources:
        messages.success(
            request,
            (
                f"Synced {len(sources) - len(failed_sources)} of {len(sources)} sources. "
                f"Processed {totals['entries']} entries, created {totals['created']}, "
                f"updated {totals['updated']}, skipped {totals['skipped']}."
            ),
        )
    return redirect(redirect_url)


@hooks.register("register_admin_urls")
def register_content_discovery_admin_urls():
    return [
        path(
            "content-discovery/sync/source/<int:source_id>/",
            sync_content_discovery_source_view,
            name="home_content_discovery_sync_source",
        ),
        path(
            "content-discovery/sync/site/<int:site_id>/",
            sync_content_discovery_site_view,
            name="home_content_discovery_sync_site",
        ),
    ]


register_snippet(GovukTagViewSet)
register_snippet(ExternalContentItemViewSet)
