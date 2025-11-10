from typing import Awaitable, Callable
from authlib.jose import jwt
from authlib.jose.errors import ExpiredTokenError
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth.oauth import OAuthWrapper


class JWTMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, oauth_wrapper: OAuthWrapper) -> None:  # noqa: ANN001
        super().__init__(app)
        self.oauth_wrapper = oauth_wrapper

    async def _decode_claims(self, token: str):  # noqa: ANN202
        jwks = await self.oauth_wrapper.get_jwks()
        return jwt.decode(token, jwks)

    def _bearer_from_header(self, request: Request) -> str | None:
        auth = request.headers.get("Authorization")
        if not auth:
            return None
        parts = auth.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()
        return None

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        request.state.user = None
        request.state.new_id_token = None

        # 1) Token aus Header (M2M) oder 2) Cookie (Browser)
        header_token = self._bearer_from_header(request)
        id_token = header_token or request.cookies.get("id_token")

        if id_token:
            try:
                claims = await self._decode_claims(id_token)
                # validate() kann ExpiredTokenError werfen
                claims.validate()
                request.state.user = self._claims_to_user_dict(claims)
                print(f"=== MIDDLEWARE: User authenticated: {request.state.user}")

            except ExpiredTokenError:
                # Nur Browser-Flow (Cookie) automatisch refreshen, nicht M2M
                if not header_token:
                    try:
                        sub = claims.get("sub")  # claims existiert, weil decode() klappte
                        refreshed = await self.oauth_wrapper.attempt_refresh(sub)
                        if refreshed:
                            new_claims, new_id_token = refreshed
                            new_claims.validate()
                            request.state.user = self._claims_to_user_dict(new_claims)
                            request.state.new_id_token = new_id_token
                    except Exception:
                        request.state.user = None
                else:
                    # Header-Token abgelaufen -> keine Auto-Refresh-Logik
                    request.state.user = None

            except Exception as e:
                # Ungültiges Token, Signature, etc.
                print(f"=== MIDDLEWARE: Token validation failed: {e}")
                request.state.user = None

        # Pipeline weiterführen
        response = await call_next(request)

        # Wenn wir per Browser-Flow (kein Header) refreshed haben: Cookie setzen
        if request.state.new_id_token and not header_token:
            response.set_cookie(
                "id_token",
                request.state.new_id_token,
                httponly=True,
            )

        return response

    def _claims_to_user_dict(self, claims) -> dict:  # noqa: ANN001
        # Extract Zitadel roles from project-specific claim
        zitadel_roles = claims.get("urn:zitadel:iam:org:project:roles", {})
        roles = list(zitadel_roles.keys()) if isinstance(zitadel_roles, dict) else []

        return {
            "sub": claims.get("sub"),
            "name": claims.get("preferred_username"),
            "email": claims.get("email"),
            "roles": roles,
        }
