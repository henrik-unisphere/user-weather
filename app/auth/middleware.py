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
        request.state.new_access_token = None

        # 1) Token aus Header (M2M) oder 2) Cookie (Browser)
        header_token = self._bearer_from_header(request)
        access_token = header_token or request.cookies.get("access_token")

        if access_token:
            try:
                claims = await self._decode_claims(access_token)
                # validate() kann ExpiredTokenError werfen
                claims.validate()
                request.state.user = self._claims_to_user_dict(claims)

            except ExpiredTokenError:
                # Nur Browser-Flow (Cookie) automatisch refreshen, nicht M2M
                if not header_token:
                    try:
                        sub = claims.get("sub")  # claims existiert, weil decode() klappte
                        refreshed = await self.oauth_wrapper.attempt_refresh(sub)
                        if refreshed:
                            new_claims, new_access_token = refreshed
                            new_claims.validate()
                            request.state.user = self._claims_to_user_dict(new_claims)
                            request.state.new_access_token = new_access_token
                    except Exception:
                        request.state.user = None
                else:
                    # Header-Token abgelaufen -> keine Auto-Refresh-Logik
                    request.state.user = None

            except Exception:
                # Ungültiges Token, Signature, etc.
                request.state.user = None

        # Pipeline weiterführen
        response = await call_next(request)

        # Wenn wir per Browser-Flow (kein Header) refreshed haben: Cookie setzen
        if request.state.new_access_token and not header_token:
            response.set_cookie(
                "access_token",
                request.state.new_access_token,
                httponly=True,
            )

        return response

    def _claims_to_user_dict(self, claims) -> dict:  # noqa: ANN001
        realm_roles = list((claims.get("realm_access") or {}).get("roles") or [])
        return {
            "sub": claims.get("sub"),
            "name": claims.get("name") or claims.get("preferred_username"),
            "email": claims.get("email"),
            "roles": realm_roles,
            # optional nützlich für M2M-Erkennung:
            # "azp": claims.get("azp"),
            # "preferred_username": claims.get("preferred_username"),
        }
