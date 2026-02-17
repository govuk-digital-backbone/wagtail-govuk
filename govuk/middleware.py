from __future__ import annotations

from django.shortcuts import redirect

from govuk.oidc import ADMIN_OIDC_NEXT_URL_KEY, build_oidc_login_url


class AdminOIDCLoginMiddleware:
    """Force OIDC login for admin routes by redirecting to OIDC."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.admin_prefixes = ("/admin/", "/django-admin/")

    def __call__(self, request):
        if request.path.startswith(self.admin_prefixes) and not request.user.is_authenticated:
            next_url = request.get_full_path()
            request.session[ADMIN_OIDC_NEXT_URL_KEY] = next_url
            return redirect(build_oidc_login_url(next_url))
        return self.get_response(request)
