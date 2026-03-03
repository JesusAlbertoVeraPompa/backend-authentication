from rest_framework.throttling import AnonRateThrottle


class LoginThrottle(AnonRateThrottle):
    scope = "login"

    def get_cache_key(self, request, view):
        email = request.data.get("email")
        ident = self.get_ident(request)

        if not email:
            return None

        return f"throttle_login_{email}_{ident}"
