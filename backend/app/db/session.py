from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
from app.db.base import Base

connect_args = {"check_same_thread": False, "timeout": 60} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all(target_engine=None) -> None:
    """Create all tables in the database."""
    # Import all models to ensure they are registered with Base.metadata
    import app.models  # noqa: F401

    e = target_engine or engine
    Base.metadata.create_all(bind=e)
    
    columns_to_add = [
        ("audit_log", "org_id", "VARCHAR DEFAULT ''"),
        ("clinical_claims", "cycle_assignment", "VARCHAR DEFAULT ''"),
        ("conflicts", "claim_a_id", "VARCHAR DEFAULT ''"),
        ("conflicts", "claim_b_id", "VARCHAR DEFAULT ''"),
        ("conflicts", "hospital_a", "VARCHAR DEFAULT ''"),
        ("conflicts", "hospital_b", "VARCHAR DEFAULT ''"),
        ("conflicts", "date_a", "DATE"),
        ("conflicts", "date_b", "DATE"),
        ("conflicts", "source_a", "VARCHAR DEFAULT ''"),
        ("conflicts", "source_b", "VARCHAR DEFAULT ''"),
        ("conflicts", "value_a", "VARCHAR DEFAULT ''"),
        ("conflicts", "value_b", "VARCHAR DEFAULT ''"),
        ("conflicts", "display_text", "TEXT DEFAULT ''"),
        ("conflicts", "acknowledged_at", "DATETIME"),
        ("documentation_gaps", "resolving_claim_id", "VARCHAR"),
        ("documentation_gaps", "resolved_at", "DATETIME"),
        ("documentation_gaps", "acknowledged_by", "VARCHAR"),
        ("documentation_gaps", "acknowledged_at", "DATETIME"),
        ("documentation_gaps", "note", "TEXT"),
    ]
    try:
        with e.connect() as conn:
            for table, col, col_type in columns_to_add:
                try:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                    conn.commit()
                except Exception:
                    pass
    except Exception:
        pass
