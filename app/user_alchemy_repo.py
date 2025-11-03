import os
from typing import Optional
from sqlalchemy import String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
from sqlalchemy.exc import IntegrityError
from pydantic import EmailStr
from app.schemas.user_model import User, UserUpdate, UserNames


def _norm(email: str | EmailStr) -> str:
    return str(email).strip().lower()


class Base(DeclarativeBase):
    pass


class UserORM(Base):
    __tablename__ = "users"
    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False)
    refresh_token: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    def to_model(self) -> User:
        return User(user_id=self.user_id, email=self.email, first_name=self.first_name, last_name=self.last_name)


class UserRepository:
    def __init__(self, dsn: Optional[str] = None) -> None:
        self._dsn = dsn or os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:secret@localhost:5432/appdb")
        self._engine = create_engine(self._dsn, echo=False, future=True)
        Base.metadata.create_all(self._engine)

    def repo_list_users(self) -> list[User]:
        with Session(self._engine) as s:
            rows = s.scalars(select(UserORM).order_by(UserORM.user_id)).all()
            return [u.to_model() for u in rows]

    def repo_get_user(self, user_id: str) -> Optional[User]:
        with Session(self._engine) as s:
            row = s.get(UserORM, user_id)
            return row.to_model() if row else None

    def repo_create_user(self, user: User, refresh_token: str | None = None) -> User:
        obj = UserORM(
            user_id=user.user_id,
            email=_norm(user.email),
            first_name=user.first_name,
            last_name=user.last_name,
            refresh_token=refresh_token,
        )
        with Session(self._engine) as s:
            s.add(obj)
            try:
                s.commit()
            except IntegrityError:
                s.rollback()
                raise ValueError("conflict")
            return obj.to_model()

    def repo_patch_user(self, user_id: str, upd: UserUpdate) -> User:
        changes = upd.model_dump(exclude_unset=True)
        if not changes:
            raise ValueError("empty")
        with Session(self._engine) as s:
            obj = s.get(UserORM, user_id)
            if not obj:
                raise KeyError("not_found")
            if "first_name" in changes:
                obj.first_name = changes["first_name"]
            if "last_name" in changes:
                obj.last_name = changes["last_name"]
            s.commit()
            s.refresh(obj)
            return obj.to_model()

    def repo_replace_user(self, user_id: str, names: UserNames) -> User:
        fn, ln = names.first_name.strip(), names.last_name.strip()
        if not fn or not ln:
            raise ValueError("blank")
        with Session(self._engine) as s:
            obj = s.get(UserORM, user_id)
            if not obj:
                raise KeyError("not_found")
            obj.first_name, obj.last_name = fn, ln
            s.commit()
            s.refresh(obj)
            return obj.to_model()

    def repo_delete_user(self, user_id: str) -> User:
        with Session(self._engine) as s:
            obj = s.get(UserORM, user_id)
            if not obj:
                raise KeyError("not_found")
            s.delete(obj)
            s.commit()
            return obj.to_model()

    def repo_set_refresh_token(self, user_id: str, refresh_token: Optional[str]) -> None:
        with Session(self._engine) as s:
            obj = s.get(UserORM, user_id)
            if not obj:
                raise KeyError("not_found")
            obj.refresh_token = refresh_token
            s.commit()

    def repo_get_user_internal(self, user_id: str) -> Optional[UserORM]:
        """Interner Zugriff (z.B. Middleware), gibt das ORM-Objekt zurück, inkl. refresh_token."""
        with Session(self._engine) as s:
            row = s.get(UserORM, user_id)
            # wir geben hier absichtlich NICHT to_model(), weil wir refresh_token brauchen
            if not row:
                return None
            # wichtig: row ist nicht mehr gültig nach Session-Ende -> wir holen die Daten raus
            return UserORM(
                user_id=row.user_id,
                email=row.email,
                first_name=row.first_name,
                last_name=row.last_name,
                refresh_token=row.refresh_token,
            )
