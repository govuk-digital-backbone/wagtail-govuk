from django.conf import settings
from django.urls import include, path
from django.contrib import admin

from wagtail.admin import urls as wagtailadmin_urls
from wagtail import urls as wagtail_urls
from wagtail.documents import urls as wagtaildocs_urls

from allauth.account.decorators import secure_admin_login
from allauth.account.views import LogoutView
from govuk.views import (
    assets_alias_view,
    oidc_login_redirect,
    profile_view,
    wagtail_logout_redirect,
)

admin.autodiscover()
admin.site.login = secure_admin_login(admin.site.login)

urlpatterns = [
    path("login/", oidc_login_redirect, name="account_login"),
    path("accounts/login/", oidc_login_redirect),
    path("admin/logout/", wagtail_logout_redirect, name="wagtailadmin_logout"),
    path("django-admin/", admin.site.urls),
    path("admin/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    path("assets/<path:path>", assets_alias_view, name="assets_alias"),
    path("accounts/profile/", profile_view, name="account_profile"),
    path("accounts/logout/", LogoutView.as_view(), name="account_logout"),
    path("accounts/", include("allauth.urls")),
    # path("search/", search_views.search, name="search"),
]


if settings.DEBUG:
    from django.conf.urls.static import static
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    # Serve static and media files from development server
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns = urlpatterns + [
    # For anything not caught by a more specific rule above, hand over to
    # Wagtail's page serving mechanism. This should be the last pattern in
    # the list:
    path("", include(wagtail_urls)),
    # Alternatively, if you want Wagtail pages to be served from a subpath
    # of your site, rather than the site root:
    #    path("pages/", include(wagtail_urls)),
]
