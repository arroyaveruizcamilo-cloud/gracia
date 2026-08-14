"""
Migration script: SQLite → PostgreSQL
Usage: python scripts/migrate_to_postgres.py

Requires:
  - DATABASE_URL_SQLITE (env) pointing to current SQLite DB
  - DATABASE_URL_PG (env) pointing to target PostgreSQL
"""

import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import Session

load_dotenv()

SQLITE_URL = os.getenv("DATABASE_URL_SQLITE", "sqlite:///./gracia.db")
PG_URL = os.getenv("DATABASE_URL_PG", "postgresql://user:password@localhost:5432/gracia")


def migrate():
    print("🔄 Connecting to SQLite...")
    sqlite_engine = create_engine(SQLITE_URL)
    sqlite_meta = MetaData()
    sqlite_meta.reflect(bind=sqlite_engine)

    print(f"🔄 Connecting to PostgreSQL: {PG_URL.split('@')[-1].split('/')[0]}...")
    pg_engine = create_engine(PG_URL)
    pg_meta = MetaData()

    # Recreate schema
    from database import Base
    Base.metadata.create_all(bind=pg_engine)

    pg_session = Session(bind=pg_engine)
    sqlite_session = Session(bind=sqlite_engine)

    tables_order = [
        "users", "products", "product_variants", "product_images",
        "coupons", "orders", "order_items", "faqs",
        "messages", "payment_transactions", "notifications",
        "cart_items", "wishlist_items", "banners", "reviews",
        "chat_conversations", "chat_messages",
    ]

    for table_name in tables_order:
        if table_name not in sqlite_meta.tables:
            continue
        table = sqlite_meta.tables[table_name]
        rows = sqlite_session.execute(table.select()).fetchall()
        if not rows:
            print(f"  ⏭️  {table_name}: 0 rows, skipping")
            continue

        pg_table = Base.metadata.tables.get(table_name)
        if pg_table is None:
            print(f"  ⚠️  {table_name}: not in target schema, skipping")
            continue

        columns = [c.name for c in pg_table.columns if c.name in table.columns]
        for row in rows:
            data = {col: getattr(row, col) for col in columns if hasattr(row, col)}
            pg_session.execute(pg_table.insert().values(**data))

        pg_session.commit()
        print(f"  ✅ {table_name}: {len(rows)} rows migrated")

    pg_session.close()
    sqlite_session.close()
    print("\n✅ Migration complete!")
    print("⚠️  Update DATABASE_URL in .env to point to PostgreSQL")


if __name__ == "__main__":
    migrate()
