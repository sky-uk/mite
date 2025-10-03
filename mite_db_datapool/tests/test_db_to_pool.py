from sqlalchemy import create_engine
from mite_db_datapool.db_to_pool import DBIterableDataPool, DBRecyclableIterableDataPool, DataPoolExhausted

import sqlite3
import asyncio

# Step 1: Create a test SQLite database and table
conn = sqlite3.connect("testdb.sqlite")
conn.execute("CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY, value TEXT)")
conn.execute("DELETE FROM test_table")
conn.execute("INSERT INTO test_table (value) VALUES ('foo'), ('bar'), ('baz')")
conn.commit()
conn.close()

# Step 2: Set up SQLAlchemy engine
engine = create_engine("sqlite:///testdb.sqlite")

# Step 3: Test DBIterableDataPool
pool = DBIterableDataPool(engine, "SELECT * FROM test_table", preload_minimum=3)

async def test_checkout():
    print("Testing DBIterableDataPool:")
    try:
        while True:
            item = await pool.checkout(config={})
            print(item.id, item.data)
    except DataPoolExhausted:
        print("Datapool exhausted.")

asyncio.run(test_checkout())

# Step 4: Test DBRecyclableIterableDataPool
recycle_pool = DBRecyclableIterableDataPool(engine, "SELECT * FROM test_table", preload_minimum=3)

async def test_recycle():
    print("\nTesting DBRecyclableIterableDataPool:")
    items = []
    for _ in range(3):
        item = await recycle_pool.checkout(config={})
        print("Checked out:", item.id, item.data)
        items.append(item.id)
    for item_id in items:
        await recycle_pool.checkin(item_id)
        print("Checked in:", item_id)
    # Try to checkout again
    for _ in range(3):
        item = await recycle_pool.checkout(config={})
        print("Checked out again:", item.id, item.data)

asyncio.run(test_recycle())