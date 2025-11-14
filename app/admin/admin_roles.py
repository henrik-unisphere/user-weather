# app/admin/admin_roles.py
from fastapi import APIRouter, Depends, HTTPException
from functools import lru_cache
import zitadel_client as zitadel
from zitadel_client.exceptions import ApiError
from zitadel_client.models import (
    BetaAuthorizationServiceListAuthorizationsRequest,
    BetaAuthorizationServiceCreateAuthorizationRequest,
    BetaAuthorizationServiceUpdateAuthorizationRequest,
    BetaAuthorizationServiceDeleteAuthorizationRequest,
)

from app.auth.auth_dep import require_admin
from app.schemas.user_model import RoleChangeRequest
from app.database.user_alchemy_repo import UserRepository
from app.core.dependencies import get_user_repo
from app.core.settings import settings

router = APIRouter(prefix="/admin/roles", tags=["admin"])


class ZitadelAdminClient:
    """Zitadel Admin client using the official SDK for managing user roles."""

    def __init__(self) -> None:
        # Parse ZITADEL_ISSUER to get base URL
        issuer = settings.ZITADEL_ISSUER.rstrip("/")
        if not issuer.startswith("http://") and not issuer.startswith("https://"):
            issuer = f"https://{issuer}"

        self.project_id = settings.ZITADEL_PROJECT_ID

        # Initialize Zitadel SDK with client credentials
        self.client = zitadel.Zitadel.with_client_credentials(
            issuer,
            settings.ZITADEL_ADMIN_CLIENT_ID,
            settings.ZITADEL_ADMIN_CLIENT_SECRET,
        )

    async def list_user_grants(self, user_id: str) -> list[dict]:
        """List all authorizations (role assignments) for a user."""
        try:
            # Use beta authorizations API
            request = BetaAuthorizationServiceListAuthorizationsRequest(
                user_id=user_id,
                project_id=self.project_id,
            )
            response = self.client.beta_authorizations.list_authorizations(request)

            # Convert to dict format
            if hasattr(response, "authorizations") and response.authorizations:
                return [
                    {
                        "id": auth.id,
                        "userId": auth.user.id if auth.user else user_id,
                        "projectId": auth.project_id or self.project_id,
                        "roleKeys": auth.roles or [],
                    }
                    for auth in response.authorizations
                ]
            return []
        except ApiError as e:
            if "not found" in str(e).lower():
                return []
            raise

    async def add_user_grant(self, user_id: str, role_keys: list[str]) -> dict:
        """Add a user authorization with specified roles."""
        try:
            request = BetaAuthorizationServiceCreateAuthorizationRequest(
                user_id=user_id,
                project_id=self.project_id,
                roles=role_keys,
            )
            response = self.client.beta_authorizations.create_authorization(request)
            return {
                "id": response.id if hasattr(response, "id") else None,
                "userId": user_id,
                "projectId": self.project_id,
                "roleKeys": role_keys,
            }
        except ApiError as e:
            raise Exception(f"Failed to create authorization: {str(e)}")

    async def update_user_grant(self, grant_id: str, role_keys: list[str]) -> dict:
        """Update an existing user authorization with new roles."""
        try:
            request = BetaAuthorizationServiceUpdateAuthorizationRequest(
                id=grant_id,
                roles=role_keys,
            )
            self.client.beta_authorizations.update_authorization(request)
            return {"id": grant_id, "roleKeys": role_keys}
        except ApiError as e:
            raise Exception(f"Failed to update authorization: {str(e)}")

    async def remove_user_grant(self, grant_id: str) -> None:
        """Remove a user authorization completely."""
        try:
            request = BetaAuthorizationServiceDeleteAuthorizationRequest(
                id=grant_id,
            )
            self.client.beta_authorizations.delete_authorization(request)
        except ApiError as e:
            raise Exception(f"Failed to delete authorization: {str(e)}")


@lru_cache()
def get_zitadel_admin() -> ZitadelAdminClient:
    """Dependency to get Zitadel admin client."""
    return ZitadelAdminClient()


@router.post("/assign", summary="Assign/Remove project role for user", dependencies=[Depends(require_admin)])
async def assign_role(
    req: RoleChangeRequest,
    repo: UserRepository = Depends(get_user_repo),
    zitadel_admin: ZitadelAdminClient = Depends(get_zitadel_admin),
) -> dict:
    """
    Assign or remove a role from a user.

    - **user_id**: The Zitadel user ID
    - **role**: The role key (e.g., "admin", "premium", "user")
    - **action**: Either "add" or "remove"
    """

    try:
        # Get existing grants for this user
        grants = await zitadel_admin.list_user_grants(req.user_id)

        # Find grant for our project
        current_grant = None
        for grant in grants:
            if grant.get("projectId") == settings.ZITADEL_PROJECT_ID:
                current_grant = grant
                break

        current_roles = set(current_grant.get("roleKeys", [])) if current_grant else set()

        if req.action == "add":
            # Add the role
            new_roles = sorted(current_roles | {req.role})

            if current_grant:
                # Update existing grant
                await zitadel_admin.update_user_grant(current_grant["id"], new_roles)
            else:
                # Create new grant
                await zitadel_admin.add_user_grant(req.user_id, new_roles)

        elif req.action == "remove":
            if not current_grant or req.role not in current_roles:
                # Nothing to remove
                return {"status": "ok", "message": "Role not assigned", "user_id": req.user_id, "role": req.role}

            new_roles = sorted(current_roles - {req.role})

            if new_roles:
                # Update with remaining roles
                await zitadel_admin.update_user_grant(current_grant["id"], new_roles)
            else:
                # Remove grant entirely if no roles left
                await zitadel_admin.remove_user_grant(current_grant["id"])

        else:
            raise HTTPException(400, f"Invalid action: {req.action}. Must be 'add' or 'remove'")

        # Optional: sync with local database
        if req.role == "premium":
            try:
                repo.repo_set_is_premium(req.user_id, req.action == "add")
            except KeyError:
                pass  # User not in local DB yet

        return {
            "status": "ok",
            "user_id": req.user_id,
            "role": req.role,
            "action": req.action,
            "message": f"Role '{req.role}' {'added to' if req.action == 'add' else 'removed from'} user",
        }

    except ApiError as e:
        raise HTTPException(500, f"Zitadel API error: {str(e)}")
    except Exception as e:
        raise HTTPException(500, f"Error managing roles: {str(e)}")


@router.get("/user/{user_id}", summary="Get user's roles", dependencies=[Depends(require_admin)])
async def get_user_roles(user_id: str, zitadel_admin: ZitadelAdminClient = Depends(get_zitadel_admin)) -> dict:
    """Get all roles assigned to a user for this project."""

    try:
        grants = await zitadel_admin.list_user_grants(user_id)

        # Find grant for our project
        for grant in grants:
            if grant.get("projectId") == settings.ZITADEL_PROJECT_ID:
                return {"user_id": user_id, "project_id": settings.ZITADEL_PROJECT_ID, "roles": grant.get("roleKeys", [])}

        return {"user_id": user_id, "project_id": settings.ZITADEL_PROJECT_ID, "roles": []}

    except ApiError as e:
        raise HTTPException(500, f"Zitadel API error: {str(e)}")
    except Exception as e:
        raise HTTPException(500, f"Error retrieving roles: {str(e)}")
