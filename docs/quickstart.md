## Getting Started 
```python
import asyncio
from aiopyql import data

async def main():

    #sqlite connection
    sqlite_db = await data.Database.create(
        database="testdb",
        cache_enabled=True
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
asyncio.run(main())
```