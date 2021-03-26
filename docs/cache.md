#

## Database 

### Read Cache 
Frequenty run querries can be offloaded from the database 
- Read query based caching
- Cache Aging, Updates and Invalidation 

!!! TIP
    A Database read cach entry will be invalidated if an INSERT - UPDATE - DELETE query runs against a table referenced by the cached entry. 


### Usage
```python
import asyncio
from aiopyql import data

async def main():

    sqlite_db = await data.Database.create(
        database="testdb",   # if no type specified, default is sqlite
        cache_enabled=True,  # Default False
        cache_length=256     # Default 128 if cache is enabled
    )
```

### Enable / Disable Cache

Enable on existing Database

```python
sqlite_db.enable_cache()
```
Disable Cache & clear cached entries from memory
```python
sqlite_db.disable_cache()
```

## Table Cache


### Key Features

- Row based read cache, which returns cached rows based on table primary key
- 'select *' querries will load both Database & Table Cache
- updates to table also update existing cache entries 
- database cache invalidation is separated from table cache invalidation
- Last-Accessed-Last-Out expiration - frequently accessed data remains cached


### Usage:
```python
await db.create_table(
    'keystore',
    [
        ('key', str, 'UNIQUE NOT NULL'),
        ('value', str)
    ],
    'key',
    cache_enabled=True
    cache_length=256
)
```
Enable Cache on existing table
```python
# turn on
db.tables['keystore'].enable_cache()
```

Disable & Remove cached entries

```python
db.tables['keystore'].disable_cache()
```

### Cache Load Events
- A complete row is accessed via select = '*', with our without conditions
- A complete row is inserted # Complete meaning value for all rows in table

### Cache Update Events
- An update is issued which includes conditions matching a cached row' primary key

#### Cache Delete Events
- A Delete is issued against a row with cached primary key
- Table max_cache_len is reached and the row was the oldest of the last referenced keys


### Forking & Cache Safety
!!! IMPORTANT 
    The Database object can be safely forked by a parent process <b>IF CACHE IS DISABLED</b>

!!! NOTE
    Cache from a forked process cannot be be trusted as consistent with another process when a change occurs, as invalidation does not propagate to all forks. 

Cache can be safely used amoung co-routines within the same asyncio event_loop. 

!!! TIP
    Common examples of forking are WSGI / WSGI web servers which create multiple workers to service requests, each creating a single database connection.
