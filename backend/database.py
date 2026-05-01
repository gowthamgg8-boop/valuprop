"""
ValUprop.in — Database Configuration
backend/database.py
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./valuprop_dev.db"   # SQLite for local dev; swap to PostgreSQL for production
)

# PostgreSQL production URL format:
# postgresql://user:password@your-rds-endpoint.ap-south-1.rds.amazonaws.com:5432/valuprop

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
