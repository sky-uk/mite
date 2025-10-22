import sqlite3

from db_to_pool import DBIterableDataPool
from sqlalchemy import create_engine

from mite import ensure_average_separation

# Step 1: Create a test SQLite database and table (local file)
DB_PATH = "example_test.db"
conn = sqlite3.connect(DB_PATH)
conn.execute("CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY, value TEXT)")
conn.execute("DELETE FROM test_table")
conn.execute("INSERT INTO test_table (value) VALUES ('mite1'), ('mite2'), ('mite3')")
conn.commit()
conn.close()

# Step 2: Set up SQLAlchemy engine (same file)
engine = create_engine(f"sqlite:///{DB_PATH}")

# Step 3: Test DBIterableDataPool
db_datapool = DBIterableDataPool(
    engine, "SELECT * FROM test_table", preload_minimum=3, max_size=2
)


async def db_journey(ctx, item_id, row):
    async with ensure_average_separation(1):
        print("running journey", item_id, row)


def scenario():
    return [["db_folder:db_journey", db_datapool, lambda s, e: 1]]


# Simple test to see it working
if __name__ == "__main__":
    print(f"✓ DataPool created with {len(db_datapool._data)} items")
    for i, (item_id, data) in enumerate(db_datapool._data):
        print(f"  Item {i}: {data}")
