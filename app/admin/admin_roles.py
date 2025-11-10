from fastapi import APIRouter, Depends
from app.auth.auth_dep import require_admin
from app.admin.kc_admin import (
    get_admin_access_token,
    fetch_role_repr,
    add_realm_role_to_user,
    remove_realm_role_from_user,
)
from app.database.user_alchemy_repo import UserRepository
from app.core.dependencies import get_user_repo
from app.schemas.user_model import RoleChangeRequest


router = APIRouter(prefix="/admin/roles", tags=["admin"])


@router.post("/assign", summary="Assign/Remove realm role for user", dependencies=[Depends(require_admin)])
async def assign_role(req: RoleChangeRequest, repo: UserRepository = Depends(get_user_repo)) -> dict:
    admin_token = await get_admin_access_token()
    role_repr = await fetch_role_repr(req.role, admin_token)

    if req.action == "add":
        await add_realm_role_to_user(req.user_id, role_repr, admin_token)
    else:
        await remove_realm_role_from_user(req.user_id, role_repr, admin_token)

    # 🔁 Optional: DB-Flag spiegeln (nur für 'premium')
    if req.role == "premium":
        try:
            repo.repo_set_is_premium(req.user_id, req.action == "add")
        except KeyError:
            # falls User lokal noch nicht existiert: ignorieren oder anlegen – hier ignorieren
            pass

    return {"status": "ok", "user_id": req.user_id, "role": req.role, "action": req.action}
