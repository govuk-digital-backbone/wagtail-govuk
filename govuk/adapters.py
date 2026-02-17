from __future__ import annotations

from allauth.account.adapter import DefaultAccountAdapter

from govuk.oidc import ADMIN_OIDC_NEXT_URL_KEY


class AccountAdapter(DefaultAccountAdapter):
    def get_login_redirect_url(self, request):
        # Ensure admin logins return to the admin path that triggered auth.
        next_url = request.session.pop(ADMIN_OIDC_NEXT_URL_KEY, None)
        if next_url:
            return next_url
        return super().get_login_redirect_url(request)
