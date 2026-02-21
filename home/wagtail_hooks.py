from draftjs_exporter.dom import DOM
from django.conf import settings
from django import forms
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse, reverse_lazy
from django.utils.html import escape
from django.utils.http import url_has_allowed_host_and_scheme
from wagtail import hooks
from wagtail.admin import messages
from wagtail.admin.auth import permission_denied, require_admin_access
from wagtail.admin.rich_text.converters.html_to_contentstate import (
    PageLinkElementHandler,
)
from wagtail.admin.rich_text.editors.draftail import features as draftail_features
from wagtail.rich_text.pages import PageLinkHandler
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet
from wagtail.whitelist import check_url

from home.content_discovery import ContentDiscoveryError, sync_content_discovery_source
from home.models import (
    ContentDiscoverySettings,
    ContentDiscoverySource,
    ExternalContentItem,
    GovukTag,
)

GOVUK_BUTTON_FEATURE = "govuk-button"
GOVUK_START_BUTTON_FEATURE = "govuk-start-button"
GOVUK_BUTTON_ENTITY_TYPE = "GOVUK_BUTTON_LINK"
GOVUK_START_BUTTON_ENTITY_TYPE = "GOVUK_START_BUTTON_LINK"
GOVUK_BUTTON_LINKTYPE = "govuk-button"
GOVUK_START_BUTTON_LINKTYPE = "govuk-start-button"
GOVUK_BUTTON_STYLE_ATTR = "data-govuk-button-style"
GOVUK_BUTTON_STYLE_DEFAULT = "default"
GOVUK_BUTTON_STYLE_START = "start"


def _get_govuk_button_attributes(*, is_start: bool) -> dict[str, str]:
    classes = "govuk-button govuk-button--start" if is_start else "govuk-button"
    style = GOVUK_BUTTON_STYLE_START if is_start else GOVUK_BUTTON_STYLE_DEFAULT
    return {
        "class": classes,
        "role": "button",
        "draggable": "false",
        "data-module": "govuk-button",
        GOVUK_BUTTON_STYLE_ATTR: style,
    }


def _build_govuk_button_opening_tag(*, href: str | None, is_start: bool) -> str:
    attrs = _get_govuk_button_attributes(is_start=is_start)
    ordered_attrs: list[str] = []
    if href:
        ordered_attrs.append(f'href="{escape(href)}"')
    ordered_attrs.extend(
        [
            f'class="{escape(attrs["class"])}"',
            f'role="{escape(attrs["role"])}"',
            f'draggable="{escape(attrs["draggable"])}"',
            f'data-module="{escape(attrs["data-module"])}"',
            f'{GOVUK_BUTTON_STYLE_ATTR}="{escape(attrs[GOVUK_BUTTON_STYLE_ATTR])}"',
        ]
    )
    return "<a " + " ".join(ordered_attrs) + ">"


def _govuk_button_entity(props: dict, *, is_start: bool):
    id_ = props.get("id")
    link_props = {}
    link_props["linktype"] = (
        GOVUK_START_BUTTON_LINKTYPE if is_start else GOVUK_BUTTON_LINKTYPE
    )
    if id_ is not None:
        link_props["id"] = id_
    else:
        link_props["url"] = check_url(props.get("url") or "") or "#"
    return DOM.create_element("a", link_props, props["children"])


def govuk_button_entity(props: dict):
    return _govuk_button_entity(props, is_start=False)


def govuk_start_button_entity(props: dict):
    return _govuk_button_entity(props, is_start=True)


class GovukButtonLinkElementHandler(PageLinkElementHandler):
    def get_attribute_data(self, attrs):
        if "id" in attrs:
            return super().get_attribute_data(attrs)
        return {"url": attrs.get("url", "")}


class GovukButtonLinkHandler(PageLinkHandler):
    identifier = GOVUK_BUTTON_LINKTYPE
    is_start = False

    @classmethod
    def expand_db_attributes_many(cls, attrs_list: list[dict]) -> list[str]:
        return [
            _build_govuk_button_opening_tag(
                href=(
                    page.localized.url
                    if page
                    else (check_url(attrs.get("url") or "") or "#")
                ),
                is_start=cls.is_start,
            )
            for attrs, page in zip(attrs_list, cls.get_many(attrs_list))
        ]

    @classmethod
    def extract_references(cls, attrs):
        if attrs.get("id"):
            yield from super().extract_references(attrs)


class GovukStartButtonLinkHandler(GovukButtonLinkHandler):
    identifier = GOVUK_START_BUTTON_LINKTYPE
    is_start = True


@hooks.register("register_rich_text_features")
def register_govuk_button_rich_text_features(features):
    features.register_link_type(GovukButtonLinkHandler)
    features.register_link_type(GovukStartButtonLinkHandler)

    for feature_name in (GOVUK_BUTTON_FEATURE, GOVUK_START_BUTTON_FEATURE):
        if feature_name not in features.default_features:
            features.default_features.append(feature_name)

    link_chooser_urls = {
        "pageChooser": reverse_lazy("wagtailadmin_choose_page"),
        "externalLinkChooser": reverse_lazy("wagtailadmin_choose_page_external_link"),
        "emailLinkChooser": reverse_lazy("wagtailadmin_choose_page_email_link"),
        "phoneLinkChooser": reverse_lazy("wagtailadmin_choose_page_phone_link"),
        "anchorLinkChooser": reverse_lazy("wagtailadmin_choose_page_anchor_link"),
    }
    common_editor_plugin_args = {
        "attributes": ["url", "id", "parentId"],
        "allowlist": {
            "href": "^(http:|https:|mailto:|tel:|#|undefined$)",
        },
        "chooserUrls": link_chooser_urls,
    }

    features.register_editor_plugin(
        "draftail",
        GOVUK_BUTTON_FEATURE,
        draftail_features.EntityFeature(
            {
                "type": GOVUK_BUTTON_ENTITY_TYPE,
                "label": "Btn",
                "description": "Button link",
                **common_editor_plugin_args,
            },
            js=[
                "wagtailadmin/js/page-chooser-modal.js",
                "home/js/draftail-govuk-button.js",
            ],
        ),
    )
    features.register_converter_rule(
        "contentstate",
        GOVUK_BUTTON_FEATURE,
        {
            "from_database_format": {
                f'a[linktype="{GOVUK_BUTTON_LINKTYPE}"]': GovukButtonLinkElementHandler(
                    GOVUK_BUTTON_ENTITY_TYPE
                ),
            },
            "to_database_format": {
                "entity_decorators": {GOVUK_BUTTON_ENTITY_TYPE: govuk_button_entity}
            },
        },
    )

    features.register_editor_plugin(
        "draftail",
        GOVUK_START_BUTTON_FEATURE,
        draftail_features.EntityFeature(
            {
                "type": GOVUK_START_BUTTON_ENTITY_TYPE,
                "label": "Btn",
                "description": "Start button link",
                **common_editor_plugin_args,
            },
            js=[
                "wagtailadmin/js/page-chooser-modal.js",
                "home/js/draftail-govuk-button.js",
            ],
        ),
    )
    features.register_converter_rule(
        "contentstate",
        GOVUK_START_BUTTON_FEATURE,
        {
            "from_database_format": {
                f'a[linktype="{GOVUK_START_BUTTON_LINKTYPE}"]': GovukButtonLinkElementHandler(
                    GOVUK_START_BUTTON_ENTITY_TYPE
                ),
            },
            "to_database_format": {
                "entity_decorators": {
                    GOVUK_START_BUTTON_ENTITY_TYPE: govuk_start_button_entity
                }
            },
        },
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
        "source",
        "hidden",
        "updated_at",
        "last_seen_at",
    ]
    list_filter = ["hidden", "source"]
    search_fields = ["title", "url"]


def _content_discovery_edit_url(site_id: int) -> str:
    return reverse(
        "wagtailsettings:edit", args=("home", "contentdiscoverysettings", site_id)
    )


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
    if not _user_can_change_content_discovery_setting(
        request, site=source.settings.site
    ):
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

    discovery_settings = get_object_or_404(ContentDiscoverySettings, site_id=site_id)
    if not _user_can_change_content_discovery_setting(
        request, site=discovery_settings.site
    ):
        return permission_denied(request)

    fallback_url = _content_discovery_edit_url(site_id)
    redirect_url = _safe_next_url(request, fallback_url=fallback_url)

    sources = list(discovery_settings.sources.all())
    if not sources:
        messages.warning(
            request, "No content discovery sources are configured for this site."
        )
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


@require_admin_access
def clear_content_discovery_site_view(request, site_id: int):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    if not settings.DEBUG:
        return permission_denied(request)

    discovery_settings = get_object_or_404(ContentDiscoverySettings, site_id=site_id)
    if not _user_can_change_content_discovery_setting(
        request, site=discovery_settings.site
    ):
        return permission_denied(request)

    fallback_url = _content_discovery_edit_url(site_id)
    redirect_url = _safe_next_url(request, fallback_url=fallback_url)

    queryset = ExternalContentItem.objects.filter(
        source__settings__site_id=site_id
    ).distinct()
    item_count = queryset.count()
    queryset.delete()

    messages.warning(
        request,
        f"Cleared {item_count} external content item{'s' if item_count != 1 else ''} for this site.",
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
        path(
            "content-discovery/clear/site/<int:site_id>/",
            clear_content_discovery_site_view,
            name="home_content_discovery_clear_site",
        ),
    ]


register_snippet(GovukTagViewSet)
register_snippet(ExternalContentItemViewSet)
