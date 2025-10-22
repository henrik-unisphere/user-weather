from __future__ import annotations
from typing import Optional
from pydantic import EmailStr
from app.schemas.user_model import User, UserUpdate, UserNames
import psycopg


def _norm(email: str | EmailStr) -> str:
    return str(email).strip().lower()


DDL = """
CREATE TABLE IF NOT EXISTS public.users (
    email      text PRIMARY KEY,
    first_name text NOT NULL,
    last_name  text NOT NULL
);
"""


class UserRepository:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        # Tabelle sicherstellen
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(DDL)
            conn.commit()

    @staticmethod
    def _row_to_user(row: Optional[tuple]) -> Optional[User]:
        if not row:
            return None
        email, first_name, last_name = row
        return User(email=email, first_name=first_name, last_name=last_name)

    def repo_list_users(self) -> list[User]:
        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute("SELECT email, first_name, last_name FROM public.users ORDER BY email;")
            return [self._row_to_user(r) for r in cur.fetchall()]

    def repo_get_user(self, email: str | EmailStr) -> Optional[User]:
        key = _norm(email)
        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT email, first_name, last_name FROM public.users WHERE email = %s;",
                (key,),
            )
            return self._row_to_user(cur.fetchone())

    def repo_create_user(self, user: User) -> User:
        key = _norm(user.email)
        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.users (email, first_name, last_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (email) DO NOTHING
                RETURNING email, first_name, last_name;
                """,
                (key, user.first_name, user.last_name),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError("conflict")
            conn.commit()
            return self._row_to_user(row)

    def repo_patch_user(self, email: str | EmailStr, upd: UserUpdate) -> User:
        changes = upd.model_dump(exclude_unset=True)
        if not changes:
            raise ValueError("empty")

        sets, params = [], []
        if "first_name" in changes:
            sets.append("first_name = %s")
            params.append(changes["first_name"])
        if "last_name" in changes:
            sets.append("last_name = %s")
            params.append(changes["last_name"])
        if not sets:
            raise ValueError("empty")

        params.append(_norm(email))
        sql = f"UPDATE public.users SET {', '.join(sets)} WHERE email = %s RETURNING email, first_name, last_name;"

        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            row = cur.fetchone()
            if not row:
                raise KeyError("not_found")
            conn.commit()
            return self._row_to_user(row)

    def repo_replace_user(self, email: str | EmailStr, names: UserNames) -> User:
        fn, ln = names.first_name.strip(), names.last_name.strip()
        if not fn or not ln:
            raise ValueError("blank")

        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE public.users
                   SET first_name = %s, last_name = %s
                 WHERE email = %s
             RETURNING email, first_name, last_name;
                """,
                (fn, ln, _norm(email)),
            )
            row = cur.fetchone()
            if not row:
                raise KeyError("not_found")
            conn.commit()
            return self._row_to_user(row)

    def repo_delete_user(self, email: str | EmailStr) -> User:
        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute(
                "DELETE FROM public.users WHERE email = %s RETURNING email, first_name, last_name;",
                (_norm(email),),
            )
            row = cur.fetchone()
            if not row:
                raise KeyError("not_found")
            conn.commit()
            return self._row_to_user(row)
