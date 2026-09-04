from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from scripts.config import DATABASE_URL

# Create SQLAlchemy Database Engine with connection pre-ping healthcheck enabled
engine: Engine = create_engine(DATABASE_URL, pool_pre_ping=True)

def test_connection():
    """Verify active database connectivity with a lightweight test query."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
        print("Database connection test successful!")
    except Exception as e:
        print(f"Database connection failed: {e}")
        raise e

def init_db_schema():
    """Read and execute SQL schema definition DDL file to create Star Schema tables."""
    sql_path = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"
    
    if not sql_path.exists():
        raise FileNotFoundError(f"Schema SQL file not found at: {sql_path}")
        
    with open(sql_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()
        
    with engine.begin() as conn:
        conn.execute(text(schema_sql))
    print("Database schema initialized successfully!")

# Local module testing block
if __name__ == "__main__":
    test_connection()
    init_db_schema()
