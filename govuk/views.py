from django.contrib.auth import logout as django_logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib.staticfiles.views import serve as staticfiles_serve
from django.shortcuts import render
from django.views.decorators.http import require_POST

from govuk.oidc import ADMIN_OIDC_NEXT_URL_KEY, build_oidc_login_url

@login_required
def profile_view(request):
    return render(request, "accounts/profile.html")


def assets_alias_view(request, path):
    return staticfiles_serve(request, f"assets/{path}", insecure=True)


def oidc_login_redirect(request):
    next_url = request.GET.get("next") or request.session.get(ADMIN_OIDC_NEXT_URL_KEY)
    return redirect(build_oidc_login_url(next_url))


@require_POST
def wagtail_logout_redirect(request):
    django_logout(request)
    return redirect("/")
