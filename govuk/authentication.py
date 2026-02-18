from rest_framework_simplejwt.authentication import JWTStatelessUserAuthentication


class InternalAccessJWTAuthentication(JWTStatelessUserAuthentication):
    """
    Validate bearer tokens issued by Internal Access OIDC.

    Verification is configured through the SIMPLE_JWT settings in
    govuk/settings/base.py (JWKS URL, issuer, and audience).
    """

    token_query_param = "bearer"

    def authenticate(self, request):
        authenticated = super().authenticate(request)
        if authenticated is not None:
            return authenticated

        raw_token = request.query_params.get(self.token_query_param)
        if not raw_token:
            return None

        validated_token = self.get_validated_token(raw_token.encode("utf-8"))
        return self.get_user(validated_token), validated_token
