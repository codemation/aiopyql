![](./images/logo.png)

# 
A fast and easy-to-use asyncio ORM(Object-relational Mapper) for performing C.R.U.D. ops within RBDMS tables using python. 

[![PyPI version](https://badge.fury.io/py/aiopyql.svg)](https://badge.fury.io/py/aiopyql)

#
## Key Features
- asyncio ready 
- database / table query cache
- SQL-like query syntax
- Automatic schema discovery / migrations

#
### Instalation
```bash
$ virtualenv -p python3.7 aiopyql-env

$ source aiopyql-env/bin/activate
```
```bash
(aiopyql-env)$ pip install aiopyql
```
#
### Compatable Databases
- postgres - via [asyncpg](https://github.com/MagicStack/asyncpg)
- mysql - via [aiomysql](https://github.com/aio-libs/aiomysql)
- sqlite - via [aiosqlite](https://github.com/omnilib/aiosqlite)

#
## Getting Started 
```python
import asyncio
from aiopyql import data

async def main():

    #sqlite connection
    sqlite_db = await data.Database.create(
        database="testdb"
    )
    
    # create table
    await db.create_table(
        'keystore',
        [
            ('key', str, 'UNIQUE NOT NULL'),
            ('value', str)
        ],
        'key',
        cache_enabled=True
    )

    # insert
    await db.tables['keystore'].insert(
        key='foo',
        value={'bar': 30}
    )
    
    # update
    await db.tables['keystore'].update(
        value={'bar': 31},
        where={'key': 'foo'}
    )

    # delete
    await db.tables['keystore'].delete(
        where={'key': 'foo'}
    )
loop = asyncio.new_event_loop()
loop.run_until_complete(main())
```
#
## Recipies
See other usage examples in [recipies](https://github.com/codemation/aiopyql/blob/master/recipies).
<br>
- [FastAPI](https://github.com/codemation/aiopyql/blob/master/recipies/fastapi_aiopyql.py)

#
## Postgres

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

loop = asyncio.new_event_loop()
loop.run_until_complete(main())
```
#
## Mysql

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

loop = asyncio.new_event_loop()
loop.run_until_complete(main())
```
#
## Idea / Suggestion / Issue
- Submit an Issue
- Create a Pull request 