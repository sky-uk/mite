import pytest
import sqlite3
import asyncio
from sqlalchemy import create_engine
from mite_db_datapool.db_to_pool import DBIterableDataPool, DBRecyclableIterableDataPool, DataPoolExhausted


@pytest.fixture
def setup_test_db():
    """Set up a test SQLite database and table"""
    conn = sqlite3.connect("testdb.sqlite")
    conn.execute("CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY, value TEXT)")
    conn.execute("DELETE FROM test_table")
    conn.execute("INSERT INTO test_table (value) VALUES ('foo'), ('bar'), ('baz')")
    conn.commit()
    conn.close()
    
    engine = create_engine("sqlite:///testdb.sqlite")
    yield engine
    
    # Cleanup
    import os
    if os.path.exists("testdb.sqlite"):
        os.remove("testdb.sqlite")


@pytest.mark.asyncio
async def test_db_iterable_datapool(setup_test_db):
    """Test DBIterableDataPool functionality"""
    engine = setup_test_db
    pool = DBIterableDataPool(engine, "SELECT * FROM test_table", preload_minimum=3)
    
    checked_out_items = []
    try:
        while True:
            item = await pool.checkout(config={})
            print(f"Checked out: {item.id}, {item.data}")
            checked_out_items.append(item)
    except DataPoolExhausted:
        print("Datapool exhausted as expected.")
    
    # Should have checked out 3 items
    assert len(checked_out_items) == 3
    
    # Verify the data
    values = [item.data['value'] for item in checked_out_items]
    assert 'foo' in values
    assert 'bar' in values
    assert 'baz' in values


@pytest.mark.asyncio
async def test_db_recyclable_iterable_datapool(setup_test_db):
    """Test DBRecyclableIterableDataPool functionality"""
    engine = setup_test_db
    recycle_pool = DBRecyclableIterableDataPool(engine, "SELECT * FROM test_table", preload_minimum=3)
    
    # Checkout items
    items = []
    for _ in range(3):
        item = await recycle_pool.checkout(config={})
        print(f"Checked out: {item.id}, {item.data}")
        items.append(item.id)
    
    assert len(items) == 3
    
    # Check them back in
    for item_id in items:
        await recycle_pool.checkin(item_id)
        print(f"Checked in: {item_id}")
    
    # Try to checkout again - should work since items are recycled
    recycled_items = []
    for _ in range(3):
        item = await recycle_pool.checkout(config={})
        print(f"Checked out again: {item.id}, {item.data}")
        recycled_items.append(item.id)
    
    assert len(recycled_items) == 3


def test_sync_version():
    """Synchronous test using asyncio.run() for compatibility"""
    # Set up database
    conn = sqlite3.connect("testdb_sync.sqlite")
    conn.execute("CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY, value TEXT)")
    conn.execute("DELETE FROM test_table")
    conn.execute("INSERT INTO test_table (value) VALUES ('foo'), ('bar'), ('baz')")
    conn.commit()
    conn.close()
    
    engine = create_engine("sqlite:///testdb_sync.sqlite")
    
    async def run_test():
        pool = DBIterableDataPool(engine, "SELECT * FROM test_table", preload_minimum=3)
        
        items = []
        try:
            while True:
                item = await pool.checkout(config={})
                items.append(item)
        except DataPoolExhausted:
            pass
        
        return items
    
    items = asyncio.run(run_test())
    assert len(items) == 3
    
    # Cleanup
    import os
    if os.path.exists("testdb_sync.sqlite"):
        os.remove("testdb_sync.sqlite")