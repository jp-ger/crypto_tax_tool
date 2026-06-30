from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from crypto_tax_tool.settings import get_settings


class Base(DeclarativeBase):
    pass


def get_engine():
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{settings.db_path}", future=True)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, future=True)


def init_session_factory() -> None:
    SessionLocal.configure(bind=get_engine())


def get_session() -> Generator[Session, None, None]:
    if SessionLocal.kw.get("bind") is None:
        init_session_factory()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
