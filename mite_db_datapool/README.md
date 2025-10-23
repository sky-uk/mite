# Database -> DataPool for Mite 

## Overview

This module provides database-backed data pools for Mite testing scenarios. It allows you to load test data directly from databases and use it in your load testing journeys.

## Why SQLAlchemy?

We chose **SQLAlchemy** over **pyodbc** for several reasons:

- **Database Agnostic**: Works with SQLite, PostgreSQL, MySQL, SQL Server, Oracle, etc.
- **Connection Pooling**: Built-in connection management and pooling
- **Simpler API**: Clean, Pythonic interface for database operations  
- **Better Error Handling**: More informative error messages
- **No Driver Dependencies**: SQLAlchemy handles driver selection automatically
- **URL-based Configuration**: Easy connection string format

## Files

### `db_to_pool.py`
Core implementation containing:
- `DBIterableDataPool`: Load data once, consume sequentially (burned data)
- `DBRecyclableIterableDataPool`: Load data once, reuse infinitely
- Memory protection with `max_size` parameter to prevent OOM with large datasets

### `mite_db_example.py`  
Working example showing:
- SQLite database creation with test data
- DataPool setup and configuration
- Integration with Mite journey functions
- Basic load testing scenario


## Testing

Run the example:
```bash
# From mite directory
python mite_db_datapool/mite_db_example.py
```

Run unit tests:
```bash
pytest test/test_db_to_pool.py -v
```