import sqlite3
import subprocess
import sys
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine

from mite_db_datapool.db_to_pool import (
    DataPoolExhausted,
    DBIterableDataPool,
    DBRecyclableIterableDataPool,
)


def test_db_to_pool_no_warning_on_import():
    # subprocess, not importlib.reload: reload() would mutate shared class state
    # in place and corrupt later tests in this process (see mite_http precedent)
    result = subprocess.run(
        [
            sys.executable,
            "-W",
            "error::FutureWarning",
            "-c",
            "import mite_db_datapool.db_to_pool",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_db_iterable_datapool_warns_on_use():
    # Stub engine: .connect() context manager -> .execute(...).fetchall() == []
    # so populate() sets db_exhausted=True after one iteration, never touching a
    # real DB. Do NOT use preload_minimum=0/max_size=0 to avoid DB access —
    # `if preload_minimum:` treats 0 as falsy and takes the DB-draining else branch.
    stub_engine = MagicMock()
    stub_conn = stub_engine.connect.return_value.__enter__.return_value
    stub_conn.execute.return_value.fetchall.return_value = []

    with pytest.warns(FutureWarning, match="mite_db_datapool will require"):
        DBIterableDataPool(stub_engine, "SELECT * FROM test_table")


@pytest.fixture
def setup_test_db():
    """Set up a test SQLite database and table"""
    conn = sqlite3.connect("testdb.sqlite")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY, value TEXT)"
    )
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


@pytest.fixture
def setup_large_test_db():
    """Set up a test SQLite database with more data for max_size testing"""
    conn = sqlite3.connect("testdb_large.sqlite")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS large_table (id INTEGER PRIMARY KEY, value TEXT)"
    )
    conn.execute("DELETE FROM large_table")

    # Insert 100 rows for testing max_size functionality
    values = [(f"item_{i}",) for i in range(100)]
    conn.executemany("INSERT INTO large_table (value) VALUES (?)", values)
    conn.commit()
    conn.close()

    engine = create_engine("sqlite:///testdb_large.sqlite")
    yield engine

    # Cleanup
    import os

    if os.path.exists("testdb_large.sqlite"):
        os.remove("testdb_large.sqlite")


@pytest.mark.asyncio
async def test_db_iterable_datapool(setup_test_db):
    """Test basic DBIterableDataPool functionality"""
    engine = setup_test_db
    pool = DBIterableDataPool(engine, "SELECT * FROM test_table", preload_minimum=3)

    checked_out_items = []
    try:
        while True:
            item = await pool.checkout(config={})
            checked_out_items.append(item)
    except DataPoolExhausted:
        pass

    assert len(checked_out_items) == 3


@pytest.mark.asyncio
async def test_db_recyclable_iterable_datapool(setup_test_db):
    """Test basic DBRecyclableIterableDataPool functionality"""
    engine = setup_test_db
    recycle_pool = DBRecyclableIterableDataPool(
        engine, "SELECT * FROM test_table", preload_minimum=3
    )

    # Checkout items
    items = []
    for _ in range(3):
        item = await recycle_pool.checkout(config={})
        items.append(item.id)

    # Check them back in
    for item_id in items:
        await recycle_pool.checkin(item_id)

    # Try to checkout again - should work since items are recycled
    recycled_items = []
    for _ in range(3):
        item = await recycle_pool.checkout(config={})
        recycled_items.append(item.id)

    assert len(recycled_items) == 3


def test_max_size_limits_data_loading(setup_large_test_db):
    """Test that max_size prevents OOM with large datasets"""
    engine = setup_large_test_db

    pool = DBIterableDataPool(
        engine,
        "SELECT * FROM large_table",
        preload_minimum=3,  # Wants to load 3 items
        max_size=2,  # Limit to 2 items even though 100 are available
    )

    assert len(pool._data) == 2


def test_infinite_loop_prevention(setup_large_test_db):
    """Test that preload_minimum > max_size doesn't cause infinite loop (critical fix)"""
    import time

    start_time = time.time()

    pool = DBIterableDataPool(
        setup_large_test_db,
        "SELECT * FROM large_table",
        preload_minimum=50,  # Want 50
        max_size=10,  # Limited to 10
    )

    end_time = time.time()

    assert end_time - start_time < 1.0  # Should complete quickly
    assert pool.preload_minimum == 10  # Auto-adjusted
    assert len(pool._data) == 10


@pytest.mark.asyncio
async def test_recyclable_with_max_size(setup_large_test_db):
    """Test recyclable pool respects max_size"""
    engine = setup_large_test_db

    recycle_pool = DBRecyclableIterableDataPool(
        engine, "SELECT * FROM large_table", preload_minimum=3, max_size=2
    )

    assert len(recycle_pool._data) == 2
    assert len(recycle_pool._available) == 2

    # Test checkout/checkin cycle
    item = await recycle_pool.checkout(config={})
    assert len(recycle_pool._available) == 1

    await recycle_pool.checkin(item.id)
    assert len(recycle_pool._available) == 2
