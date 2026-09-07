import time
import uuid
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


def now() -> float:
    return time.time()


def uid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


def make_engine(url: str):
    options = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        path = url.removeprefix("sqlite:///")
        if path not in {":memory:", ""}:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        options["connect_args"] = {"check_same_thread": False, "timeout": 30}
    else:
        options.update(pool_size=5, max_overflow=5, pool_recycle=900)
    engine = create_engine(url, **options)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def sqlite_setup(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")

    return engine


def sessions(engine):
    return sessionmaker(engine, expire_on_commit=False)
