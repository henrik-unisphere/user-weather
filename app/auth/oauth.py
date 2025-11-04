from typing import Tuple
import httpx
from authlib.integrations.starlette_client import OAuth
from authlib.jose import JsonWebKey, KeySet, jwt

from app.auth.settings import settings
from app.user_alchemy_repo import UserRepository


class OAuthWrapper:
    def __init__(self, repo: UserRepository) -> None:
        self.repo = repo
        self._jwks: KeySet | None = None
        self.oauth = OAuth()
        self.oauth.register(
            name="keycloak",
            server_metadata_url=f"{settings.KEYCLOAK_ISSUER}/.well-known/openid-configuration",
            client_id=settings.KEYCLOAK_CLIENT_ID,
            client_secret=settings.KEYCLOAK_CLIENT_SECRET,
            client_kwargs={"scope": "openid email profile"},
        )

    async def get_jwks(self) -> KeySet:
        if self._jwks is not None:
            return self._jwks

        async with httpx.AsyncClient() as client:
            disc = await client.get(f"{settings.KEYCLOAK_ISSUER}/.well-known/openid-configuration")
            disc.raise_for_status()
            discovery = disc.json()

            jwks_resp = await client.get(discovery["jwks_uri"])
            jwks_resp.raise_for_status()

            self._jwks = JsonWebKey.import_key_set(jwks_resp.json())
        return self._jwks

    async def attempt_refresh(self, user_id: str) -> Tuple[dict, str]:
        try:
            user_row = self.repo.repo_get_user_internal(user_id)
        except Exception as e:
            print("DB lookup for refresh_token failed:", e)
            return None

        if not user_row or not user_row.refresh_token:
            return None

        try:
            metadata = await self.oauth.keycloak.load_server_metadata()
            token_endpoint_url = metadata.get("token_endpoint")
            print(token_endpoint_url)
            print(user_row.refresh_token)
            data = {
                "client_id": f"{settings.KEYCLOAK_CLIENT_ID}",
                "grant_type": "refresh_token",
                "refresh_token": user_row.refresh_token,
                "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
            }
            print(data)
            async with httpx.AsyncClient() as client:
                disc = await client.post(token_endpoint_url, data=data)
                disc.raise_for_status()
                result = disc.json()

        except Exception as e:
            print("Token refresh failed:", e)
            return None

        # Erwartet: new_token hat wieder id_token, access_token, evtl. neuen refresh_token
        new_access_token = result.get("access_token")
        new_refresh_token = result.get("refresh_token")

        if not new_access_token:
            return None

        # 4. Neues id_token validieren
        try:
            new_claims = jwt.decode(new_access_token, await self.get_jwks())
            new_claims.validate()

            roles = (new_claims.get("realm_access") or {}).get("roles") or []
            is_premium = "premium" in roles
            try:
                self.repo.repo_set_is_premium(user_id, is_premium)  # ← Flag aktualisieren
            except Exception as e:
                print("Failed to update is_premium:", e)

        except Exception as e:
            print("Refreshed token invalid:", e)
            return None

        # 5. Refresh-Token ggf. rotieren
        if new_refresh_token:
            try:
                self.repo.repo_set_refresh_token(user_id, new_refresh_token)
            except Exception as e:
                print("Failed to update refresh token in DB:", e)

        # 6. return an dispatch()
        return (new_claims, new_access_token)
