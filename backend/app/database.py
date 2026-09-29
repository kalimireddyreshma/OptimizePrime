from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings


settings = get_settings()
engine = create_engine(settings.database_url, echo=False)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    columns_to_add = {
        "clauses": {
            "risk_reason": "TEXT NOT NULL DEFAULT ''",
            "risk_factors": "TEXT NOT NULL DEFAULT '[]'",
            "analysis_source": "TEXT NOT NULL DEFAULT 'RULE_BASED'",
            "memory_status": "TEXT NOT NULL DEFAULT 'unavailable'",
            "exception_detected": "BOOLEAN NOT NULL DEFAULT 0",
            "exception_evidence": "BOOLEAN NOT NULL DEFAULT 0",
        },
        "contracts": {
            "extracted_text": "TEXT NOT NULL DEFAULT ''",
        },
        "human_decisions": {
            "original_recommendation": "TEXT NOT NULL DEFAULT ''",
            "final_text": "TEXT NOT NULL DEFAULT ''",
            "memory_action": "TEXT NOT NULL DEFAULT 'not_attempted'",
            "memory_status": "TEXT NOT NULL DEFAULT ''",
        },
    }
    with engine.begin() as connection:
        inspector = inspect(connection)
        for table_name, columns in columns_to_add.items():
            existing = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, definition in columns.items():
                if column_name not in existing:
                    connection.execute(text(
                        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
                    ))


def get_session() -> Session:
    return Session(engine)
