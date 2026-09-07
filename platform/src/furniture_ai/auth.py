import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from furniture_ai.db import now
from furniture_ai.errors import DomainError
from furniture_ai.models import Audit, LoginSession, RateBucket, User

PASSWORDS = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
DUMMY_HASH = PASSWORDS.hash(secrets.token_urlsafe(32))
COOKIE = "furniture_session"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def rate_limit(factory, key: str, limit: int, window: int):
    stamp = now()
    bucket = int(stamp // window)
    with factory.begin() as db:
        insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
        stmt = insert(RateBucket).values(
            key=digest(key), period=bucket, count=1, expires_at=(bucket + 2) * window
        )
        count = db.execute(
            stmt.on_conflict_do_update(
                index_elements=[RateBucket.key, RateBucket.period], set_={"count": RateBucket.count + 1}
            ).returning(RateBucket.count)
        ).scalar_one()
    if count > limit:
        raise DomainError("RATE_LIMITED", "Too many requests. Try again later.", 429)


def require_origin(request: Request):
    if request.headers.get("origin") != request.app.state.settings.public_origin:
        raise DomainError("ORIGIN_REJECTED", "Use the configured application origin.", 403)


def current_user(request: Request) -> User:
    token = request.cookies.get(COOKIE, "")
    if not 32 <= len(token) <= 128:
        raise DomainError("UNAUTHENTICATED", "Please sign in.", 401)
    with request.app.state.sessions() as db:
        user = db.scalar(
            select(User)
            .join(LoginSession)
            .where(
                LoginSession.token_hash == digest(token),
                LoginSession.expires_at > now(),
                User.active.is_(True),
            )
        )
    if user is None:
        raise DomainError("UNAUTHENTICATED", "Your session expired. Please sign in.", 401)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        require_origin(request)
    rate_limit(
        request.app.state.sessions, f"user:{user.id}", request.app.state.settings.requests_per_minute, 60
    )
    return user


def audit(db, user, action: str, resource_id: str):
    db.add(Audit(tenant_id=user.tenant_id, actor_id=user.id, action=action, resource_id=resource_id))


def check_password(encoded: str, password: str) -> bool:
    try:
        return PASSWORDS.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False
