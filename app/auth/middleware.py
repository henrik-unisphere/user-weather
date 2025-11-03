from typing import Awaitable, Callable, Optional, Tuple
from authlib.jose import jwt, JoseError
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

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        request.state.user = None
        request.state.new_id_token = None

        raw_token = request.cookies.get("token")
        if raw_token:
            try:
                claims = await self._decode_claims(raw_token)
                claims.validate()
                request.state.user = self._claims_to_user_dict(claims)

            except ExpiredTokenError:
                try:
                    sub = claims.get("sub")  # claims existiert hier, da decode geklappt hat
                    refreshed: Optional[Tuple[dict, str]] = await self.oauth_wrapper.attempt_refresh(sub)
                    if refreshed:
                        new_claims, new_id_token = refreshed
                        new_claims.validate()
                        request.state.user = self._claims_to_user_dict(new_claims)
                        request.state.new_id_token = new_id_token
                    else:
                        request.state.user = None
                except Exception:
                    request.state.user = None

            except JoseError:
                request.state.user = None
            except Exception:
                request.state.user = None

        response = await call_next(request)

        if request.state.new_id_token:
            response.set_cookie(
                "token",
                request.state.new_id_token,
                httponly=True,
            )
        return response

    def _claims_to_user_dict(self, claims) -> dict[str, object]:  # noqa: ANN001
        return {
            "sub": claims.get("sub"),
            "name": claims.get("name") or claims.get("preferred_username"),
            "email": claims.get("email"),
        }
