import json
from rest_framework.authtoken.models import Token
from django.http import HttpResponseForbidden

PROTECTED_PREFIXES = (
    "/media/test_case/",
    "/media/test_case_robot/",
)

class ProtectedMediaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # Only intercept the two protected folders
        if any(path.startswith(prefix) for prefix in PROTECTED_PREFIXES):

            # CASE 1: Logged-in admin/UI user (session auth) — allow directly
            if request.user.is_authenticated and request.user.is_active:
                return self.get_response(request)

            # CASE 2: API/external server — validate Bearer token
            auth_header = request.META.get("HTTP_AUTHORIZATION", "")

            if not auth_header.lower().startswith("bearer "):
                return HttpResponseForbidden(
                    json.dumps({"detail": "Authentication required."}),
                    content_type="application/json",
                )

            token_key = auth_header.split(" ", 1)[1].strip()

            try:
                token = Token.objects.select_related("user").get(key=token_key)
                if not token.user.is_active:
                    raise Token.DoesNotExist
            except Token.DoesNotExist:
                return HttpResponseForbidden(
                    json.dumps({"detail": "Invalid or expired token."}),
                    content_type="application/json",
                )

        return self.get_response(request)