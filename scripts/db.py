from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from scripts.config import DATABASE_URL

# 1. Create SQLAlchemy Engine for PostgreSQL
engine: Engine = create_engine(DATABASE_URL, pool_pre_ping=True)

def test_connection():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
            print("Database connection successful!")
    except Exception as e:
        print(f"Database connection failed: {e}")
        raise e


def init_db_schema():
    sql_path = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"
    
    if not sql_path.exists():
        raise FileNotFoundError(f"Schema file not found at: {sql_path}")
        
    with open(sql_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()
        
    print("Initializing database schema from sql/schema.sql...")
    with engine.begin() as conn:
        conn.execute(text(schema_sql))
    print("Database schema initialized successfully!")


if __name__ == "__main__":
    test_connection()
    init_db_schema()
