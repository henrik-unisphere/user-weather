from typing import Awaitable, Callable
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, Response
from authlib.jose import jwt
from app.auth.oauth import OAuthWrapper
from app.auth.settings import settings
from app.user_alchemy_repo import UserRepository


class JWTMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, oauth_wrapper: OAuthWrapper) -> None:  # noqa: ANN001
        super().__init__(app)
        self._jwks = None  # Cache
        self.oauth_wrapper = oauth_wrapper

    async def _decode_claims(self, token: str):
        jwks = await self.oauth_wrapper.get_jwks()
        claims = jwt.decode(token, jwks)
        # claims.validate() wirft bei abgelaufenem Token eine Exception
        return claims

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        request.state.user = None
        request.state.new_id_token = None  # falls refreshed

        raw_token = request.cookies.get("token")

        if raw_token:
            try:
                # Versuch 1: Token normal validieren
                claims = await self._decode_claims(raw_token)
                claims.validate()  # ok -> nicht abgelaufen
                request.state.user = self._claims_to_user_dict(claims)

            except Exception as e:
                # Token evtl. abgelaufen -> versuchen zu refreshen
                print("Token validation failed, trying refresh:", e)
                refreshed = await self.oauth_wrapper.attempt_refresh(request, raw_token)
                if refreshed is not None:
                    # refreshed enthält (claims, new_id_token)
                    claims, new_id_token = refreshed
                    request.state.user = self._claims_to_user_dict(claims)
                    request.state.new_id_token = new_id_token
                else:
                    request.state.user = None

        # Jetzt eigentliche App ausführen
        response = await call_next(request)

        # Falls wir ein neues id_token haben -> Cookie aktualisieren
        if request.state.new_id_token:
            response.set_cookie(
                "token",
                request.state.new_id_token,
                httponly=True,
                # secure=True,
                # samesite="lax",
            )

        return response

    def _claims_to_user_dict(self, claims) -> dict[str, object]:
        return {
            "sub": claims.get("sub"),
            "name": claims.get("name") or claims.get("preferred_username"),
            "email": claims.get("email"),
            "roles": claims.get("realm_access", {}).get("roles", []),
            "raw_claims": claims,
        }
