"""Authentication and identity business logic."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.errors import ConflictError, UnauthorizedError
from researchos.common.security import hash_password, verify_password
from researchos.organizations.models import Organization
from researchos.organizations.service import OrganizationService

from .models import User
from .repository import UserRepository


def _normalize_email(email: str) -> str:
    return email.strip().lower()


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.organizations = OrganizationService(db)

    async def register(
        self, *, email: str, password: str, display_name: str
    ) -> tuple[User, Organization]:
        normalized = _normalize_email(email)
        if await self.users.get_by_email(normalized) is not None:
            raise ConflictError("An account with this email already exists.")

        user = await self.users.create(
            email=normalized,
            password_hash=hash_password(password),
            display_name=display_name.strip(),
        )
        organization = await self.organizations.create_personal_organization(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user, organization

    async def authenticate(self, *, email: str, password: str) -> User:
        """Verify credentials.

        Returns the user on success. On any failure raises a generic 401 that
        does not reveal whether the email exists (PHASE1_DECISIONS P1-D9).
        """

        user = await self.users.get_by_email(_normalize_email(email))
        if user is None:
            # Still run a hash verification against a dummy to reduce timing
            # signal, then fail generically.
            verify_password(password, _DUMMY_HASH)
            raise UnauthorizedError("Invalid credentials.")
        if not verify_password(password, user.password_hash) or not user.is_active:
            raise UnauthorizedError("Invalid credentials.")
        return user


# A precomputed argon2 hash of a random value, used to equalize timing on the
# "user not found" path.
_DUMMY_HASH = hash_password("researchos-dummy-password-for-timing")
