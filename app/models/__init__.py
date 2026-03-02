# Import all models here so Alembic autogenerate picks them up via Base.metadata
from app.models.click import Click
from app.models.link import Link
from app.models.refresh_token import RefreshToken
from app.models.user import RoleEnum, User

__all__ = ["User", "RoleEnum", "Link", "Click", "RefreshToken"]
