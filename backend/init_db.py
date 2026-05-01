"""
ValUprop.in — Database Initialisation
backend/init_db.py

Run once to create all tables:
  python init_db.py

For PostgreSQL production:
  Set DATABASE_URL in .env first:
  DATABASE_URL=postgresql://user:password@host:5432/valuprop
"""

from database import engine, Base
import models  # noqa: F401 — imports all table definitions

print("Creating database tables…")
Base.metadata.create_all(bind=engine)
print("✓ Tables created successfully.")
print()
print("Tables:")
from sqlalchemy import inspect
inspector = inspect(engine)
for table in inspector.get_table_names():
    cols = [c["name"] for c in inspector.get_columns(table)]
    print(f"  {table}: {', '.join(cols)}")
