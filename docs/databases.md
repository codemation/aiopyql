#

### Database Connection

#### sqlite

```python
import asyncio
from aiopyql import data

async def main():
    sqlite_db = await data.Database.create(
        database="testdb",
        cache_enabled=True
    )
```

#### Postgres

```python
import asyncio
from aiopyql import data

async def main():
    mysql_db = await data.Database.create(
        database='postgres_database',
        user='postgres',
        password='my-secret-pw',
        host='localhost',
        port=5432,
        db_type='postgres'
    )

asyncio.run(main())
```
#### Mysql

```python
import asyncio
from aiopyql import data

async def main():
    mysql_db = await data.Database.create(
        database='mysql_database',
        user='mysqluser',
        password='my-secret-pw',
        host='localhost',
        port=3306,
        db_type='mysql'
    )
asyncio.run(main())
```
### Schema Discovery
Existing tables schemas within databases are loaded when database object is instantiated via Database.create()