from __future__ import annotations

from urllib.parse import urlencode

from django.conf import settings

ADMIN_OIDC_NEXT_URL_KEY = "oidc_next_url"


def build_oidc_login_url(next_url: str | None = None) -> str:
    prefix = settings.SOCIALACCOUNT_OPENID_CONNECT_URL_PREFIX
    provider_id = getattr(settings, "OIDC_PROVIDER_ID", "internal-access")
    base_url = f"/accounts/{prefix}/{provider_id}/login/"
    if next_url:
        return f"{base_url}?{urlencode({'next': next_url})}"
    return base_url
