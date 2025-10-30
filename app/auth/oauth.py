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

    async def attempt_refresh(self, user_id: str):
        try:
            user_row = self.repo.repo_get_user_internal(user_id)
        except Exception as e:
            print("DB lookup for refresh_token failed:", e)
            return None

        if not user_row or not user_row.refresh_token:
            return None

        # 3. neuen Token bei Keycloak anfordern
        try:
            new_token = await self.oauth.keycloak.refresh_token(
                url=self.oauth.keycloak.client_metadata["token_endpoint"],
                refresh_token=user_row.refresh_token,
            )
        except Exception as e:
            print("Token refresh failed:", e)
            return None

        # Erwartet: new_token hat wieder id_token, access_token, evtl. neuen refresh_token
        new_id_token = new_token.get("id_token")
        new_refresh_token = new_token.get("refresh_token")

        if not new_id_token:
            return None

        # 4. Neues id_token validieren
        try:
            new_claims = jwt.decode(new_id_token, await self.get_jwks())
            new_claims.validate()
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
        return (new_claims, new_id_token)
