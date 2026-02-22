from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from wagtail.models import Site

from govuk.middleware import AuthenticatedUserRedirectMiddleware
from govuk.models import AuthenticatedRedirectRule, AuthenticatedRedirectSettings


class AuthenticatedUserRedirectMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = AuthenticatedUserRedirectMiddleware(
            lambda request: HttpResponse("ok")
        )
        self.site = Site.objects.get(is_default_site=True)
        self.user = get_user_model().objects.create_user(
            username="redirect-user",
            password="unused-password",
        )

    def _create_rule(self, source_path: str, destination_path: str):
        settings = AuthenticatedRedirectSettings.for_site(self.site)
        AuthenticatedRedirectRule.objects.create(
            settings=settings,
            source_path=source_path,
            destination_path=destination_path,
        )

    @patch("govuk.middleware.Site.find_for_request")
    def test_authenticated_get_with_matching_rule_redirects(self, mock_find_for_request):
        mock_find_for_request.return_value = self.site
        self._create_rule("/", "/dashboard")
        request = self.factory.get("/")
        request.user = self.user

        response = self.middleware(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/dashboard")

    @patch("govuk.middleware.Site.find_for_request")
    def test_anonymous_user_is_not_redirected(self, mock_find_for_request):
        mock_find_for_request.return_value = self.site
        self._create_rule("/", "/dashboard")
        request = self.factory.get("/")
        request.user = AnonymousUser()

        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")

    @patch("govuk.middleware.Site.find_for_request")
    def test_authenticated_post_is_not_redirected(self, mock_find_for_request):
        mock_find_for_request.return_value = self.site
        self._create_rule("/", "/dashboard")
        request = self.factory.post("/")
        request.user = self.user

        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")
