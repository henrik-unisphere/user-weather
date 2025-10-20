from __future__ import annotations
from typing import Dict, List
from pathlib import Path
import json
import os
import threading
from pydantic import EmailStr
from app.schemas.user_model import User, UserUpdate, UserNames


def _norm(email: str | EmailStr) -> str:
    return str(email).strip().lower()


class UserRepository:
    def __init__(self, data_path: Path) -> None:
        self._path = data_path
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _load_unlocked(self) -> Dict[str, User]:
        """JSON lesen → Dict[email_lower -> User]"""
        if not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        users: Dict[str, User] = {}
        for item in raw:
            u = User.model_validate(item)
            users[_norm(u.email)] = u
        return users

    def _save_unlocked(self, users: Dict[str, User]) -> None:
        """Dict → JSON atomar schreiben"""
        payload: List[dict] = [u.model_dump() for u in users.values()]
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self._path)

    def repo_list_users(self) -> list[User]:
        with self._lock:
            users = self._load_unlocked()
            return list(users.values())

    def repo_get_user(self, email: str | EmailStr) -> User:
        key = _norm(email)
        with self._lock:
            users = self._load_unlocked()
            return users.get(key)

    def repo_create_user(self, user: User) -> User:
        key = _norm(user.email)
        with self._lock:
            users = self._load_unlocked()
            if key in users:
                raise ValueError("conflict")
            users[key] = user
            self._save_unlocked(users)
            return user

    def repo_patch_user(self, email: str | EmailStr, upd: UserUpdate) -> User:
        changes = upd.model_dump(exclude_unset=True)
        if not changes:
            raise ValueError("empty")  # API → 400
        key = _norm(email)
        with self._lock:
            users = self._load_unlocked()
            u = users.get(key)
            if not u:
                raise KeyError("not_found")  # API → 404
            if "first_name" in changes:
                u.first_name = changes["first_name"]
            if "last_name" in changes:
                u.last_name = changes["last_name"]
            users[key] = u
            self._save_unlocked(users)
            return u

    def repo_replace_user(self, email: str | EmailStr, names: UserNames) -> User:
        fn, ln = names.first_name.strip(), names.last_name.strip()
        if not fn or not ln:
            raise ValueError("blank")  # API → 400
        key = _norm(email)
        with self._lock:
            users = self._load_unlocked()
            u = users.get(key)
            if not u:
                raise KeyError("not_found")  # API → 404 (oder Upsert-Variante bauen)
            u.first_name, u.last_name = fn, ln
            users[key] = u
            self._save_unlocked(users)
            return u

    def repo_delete_user(self, email: str | EmailStr) -> User:
        key = _norm(email)
        with self._lock:
            users = self._load_unlocked()
            u = users.pop(key, None)
            if not u:
                raise KeyError("not_found")  # API → 404
            self._save_unlocked(users)
            return u
