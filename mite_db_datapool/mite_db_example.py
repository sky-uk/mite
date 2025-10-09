import sqlite3

from sqlalchemy import create_engine

from mite import ensure_average_separation
from mite_db_datapool.db_to_pool import DBIterableDataPool

# Step 1: Create a test SQLite database and table
conn = sqlite3.connect("/Users/mae312/sky-id-mite-nft/mite_id/mite_id/db_folder/test.db")
conn.execute("CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY, value TEXT)")
conn.execute("DELETE FROM test_table")
conn.execute("INSERT INTO test_table (value) VALUES ('mite1'), ('mite2'), ('mite3')")
conn.commit()
conn.close()

# Step 2: Set up SQLAlchemy engine
engine = create_engine("sqlite:///testdb.sqlite")

# Step 3: Test DBIterableDataPool
db_datapool = DBIterableDataPool(engine, "SELECT * FROM test_table", preload_minimum=3)


async def db_journey(ctx, item_id, row):
    async with ensure_average_separation(1):
        print("running journey", item_id, row)


def scenario():
    return [["db_folder:db_journey", db_datapool, lambda s, e: 1]]
