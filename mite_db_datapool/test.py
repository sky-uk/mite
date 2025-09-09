from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base


from sqlalchemy import create_engine, inspect

from sqlalchemy import create_engine, inspect

engine = create_engine('sqlite:///test.db') 
inspector = inspect(engine)
table_name = 'mite' 

columns = inspector.get_columns(table_name)
for col in columns:
    print(col)