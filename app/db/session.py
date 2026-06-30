from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,       # checks connection health before using it
    pool_size=10,             # keep 10 connections open
    max_overflow=20,          # allow 20 extra connections under load
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """
    FastAPI dependency. Yields a DB session per request,
    and guarantees it closes when the request finishes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()