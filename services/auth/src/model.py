from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped
from sqlalchemy import String
from typing import Optional


class AuthBase(DeclarativeBase):
    pass


class User(AuthBase):
    __tablename__ = "user_account"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_name: Mapped[str] = mapped_column(String(24))
    password: Mapped[str] = mapped_column(String(64))  
    user_name: Mapped[Optional[str]]

    def __repr__(self) -> str:
        return (
            f"User("
            f"id={self.id!r}, "
            f"account_name={self.account_name!r}, "
            f"password={self.password!r}, "
            f"user_name={self.user_name!r})"
        )