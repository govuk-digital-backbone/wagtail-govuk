from django.http import JsonResponse
from django.urls import reverse
from rest_framework import serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from wagtail.api.conf import APIField
from wagtail.api.v2.router import WagtailAPIRouter
from wagtail.api.v2.views import PagesAPIViewSet
from wagtail.documents.api.v2.views import DocumentsAPIViewSet
from wagtail.images.api.v2.views import ImagesAPIViewSet

from govuk.authentication import InternalAccessJWTAuthentication

AUTH_QUERY_PARAMETERS = frozenset({"bearer"})


class PagePrivacyField(serializers.Field):
    def __init__(self, **kwargs):
        kwargs.setdefault("read_only", True)
        kwargs.setdefault("source", "*")
        super().__init__(**kwargs)

    def to_representation(self, page):
        restrictions = []
        for restriction in page.view_restrictions.all():
            restriction_data = {
                "id": restriction.id,
                "type": restriction.restriction_type,
            }
            if restriction.restriction_type == restriction.GROUPS:
                restriction_data["groups"] = [
                    {"id": group.id, "name": group.name}
                    for group in restriction.groups.all()
                ]
            restrictions.append(restriction_data)

        return {
            "restricted": bool(restrictions),
            "restrictions": restrictions,
        }


class AuthenticatedAPIViewSetMixin:
    authentication_classes = [InternalAccessJWTAuthentication]
    permission_classes = [IsAuthenticated]


class WagtailPages(AuthenticatedAPIViewSetMixin, PagesAPIViewSet):
    permission_classes = [AllowAny]
    meta_fields = PagesAPIViewSet.meta_fields + [
        APIField("privacy", serializer=PagePrivacyField()),
    ]
    listing_default_fields = PagesAPIViewSet.listing_default_fields + ["privacy"]
    known_query_parameters = PagesAPIViewSet.known_query_parameters.union(
        AUTH_QUERY_PARAMETERS
    )

    def get_queryset(self):
        return super().get_queryset().prefetch_related("view_restrictions__groups")


class WagtailImages(AuthenticatedAPIViewSetMixin, ImagesAPIViewSet):
    known_query_parameters = ImagesAPIViewSet.known_query_parameters.union(
        AUTH_QUERY_PARAMETERS
    )


class WagtailDocuments(AuthenticatedAPIViewSetMixin, DocumentsAPIViewSet):
    known_query_parameters = DocumentsAPIViewSet.known_query_parameters.union(
        AUTH_QUERY_PARAMETERS
    )


api_router = WagtailAPIRouter("wagtailapi")
api_router.register_endpoint("pages", WagtailPages)
api_router.register_endpoint("images", WagtailImages)
api_router.register_endpoint("documents", WagtailDocuments)


def _build_v2_endpoint_links(request):
    links = {}
    for endpoint_name in api_router._endpoints:
        listing_path = reverse(f"{api_router.url_namespace}:{endpoint_name}:listing")
        listing_url = request.build_absolute_uri(listing_path)
        links[endpoint_name] = {
            "listing": listing_url,
            "detail": f"{listing_url}{{id}}/",
        }
    return links


def api_root_view(request):
    return JsonResponse(
        {
            "versions": {
                "v2": request.build_absolute_uri(reverse("api_v2_root")),
            }
        }
    )


def api_v2_root_view(request):
    return JsonResponse(
        {
            "version": "v2",
            "endpoints": _build_v2_endpoint_links(request),
        }
    )
