# aiopyql
A fast and easy-to-use asyncio ORM(Object-relational Mapper) for performing C.R.U.D. ops within RBDMS tables using python. 

## Key Features
- fast
- asyncio ready 
- database / table query cache
- SQL-like query syntax
- Schema discovery 

### Instalation

    $ virtualenv -p python3.7 aiopyql-env

    $ source aiopyql-env/bin/activate

#### Install with PIP

     (aiopyql-env)$ pip install aiopyql

#### Download & install Library from repo:

    (aiopyql-env)$ git clone https://github.com/codemation/aiopyql.git

Use install script to install the aiopyql into the activated environment libraries

    (aiopyql-env)$ cd aiopyql; sudo ./install.py install

### Compatable Databases

- mysql
- sqlite

## Getting Started 

A Database object can be created both in and out of an event loop, but the Database.create() factory coro ensures
load_tables() is processed to load existing tables. 

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

## Recipies
See other usage examples in [recipies](https://github.com/codemation/aiopyql/blob/master/recipies).
<br>
- [FastAPI](https://github.com/codemation/aiopyql/blob/master/recipies/fastapi_aiopyql.py)

## Mysql
<br>
Note: if no type specified, default is sqlite

    import asyncio
    from aiopyql import data

    async def main():
        mysql_db = await data.Database.create(
            database='mysql_database',
            user='mysqluser',
            password='my-secret-pw',
            host='localhost',
            port=3306,
            type='mysql'
        )

    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())

Existing tables schemas within databases are loaded when database object is instantiated via .create and ready for use immedielty. 

## Database Read Cache 
Database read cache provides read query based caching. This cache is accessed when a duplicate query is received before any table changes. This is capable of providing relief for more expensive & less explicit querries that might span multiple tables ( via table joins ). 

A Database read cach entry will be invalidated if an INSERT - UPDATE - DELETE query runs against a table referenced by the cached entry. 


### Usage

    import asyncio
    from aiopyql import data

    async def main():

        sqlite_db = await data.Database.create(
            database="testdb",   # if no type specified, default is sqlite
            cache_enabled=True,  # Default False
            cache_length=256     # Default 128 if cache is enabled
        )

Enable on existing Database

    sqlite_db.enable_cache()

Disable Cache & clear cached entries from memory

    sqlite_db.disable_cache()

## Table Cache
<br>
Key Features:
<br>

- Row based read cache, which returns cached rows based on table primary key
- 'select *' querries will load both Database & Table Cache
- updates to table also update existing cache entries 
- database cache invalidation is separated from table cache invalidation
- Last-Accessed-Last-Out expiration - frequently accessed data remains cached

### Usage:

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
Enable Cache on existing table

    # turn on
    db.tables['keystore'].enable_cache()

Disable & Remove cached entries

    db.tables['keystore'].disable_cache()


#### Cache Load Events
- A complete row is accessed via select = '*', with our without conditions
- A complete row is inserted # Complete meaning value for all rows in table

#### Cache Update Events
- An update is issued which includes conditions matching a cached row' primary key

#### Cache Delete Events
- A Delete is issued against a row with cached primary key
- Table max_cache_len is reached and the row was the oldest of the last referenced keys

### Forking & Cache Safety
The Database object can be safely forked by a parent process IF CACHE IS DISABLED. Cache from one process should be be trusted as consistent with another process when a change occurs, as invalidation does not propagate to all forks. 
<br><br>
Cache can be safely used amoung co-routines within the same event_loop. 

## Table Create
<br>

### Usage

    db.create_table(
        'table_name',
        [
            ('col_name', <col_type[int,str,float,byte, bool]>, 'col_mods'),
            .
            ..
        ],
        prim_key='<col_name>',
        foreign_keys={
            '<col_name>': {
                'table': '<ref_table_name>'
                'ref': '<ref_table_column>',
                'mods': 'ON UPDATE CASCADE'
            }
        },
        cache_enabled = True | False(default),
        max_cache_len = 125(default)
    )

Requires List of at least 2 item tuples, max 3

('column_name', type, 'modifiers')

- column_name - str - database column name exclusions apply
- types: str, int, float, byte, bool, None # JSON dumpable dicts fall under str types
- modifiers: NOT NULL, UNIQUE, AUTO_INCREMENT

Some Column modifiers apply for column options i.e 

    AUTOINCREMENT  (sqlite)
    AUTO_INCREMENT (mysql)
    
See DB documentation for reference.

Optional:
    
    cache_enabled = True | False (Default)
    
    max_cache_len = 125 (Default)

Note: Unique constraints are not validated by aiopyql but at db, so if modifier is supported it will be added when table is created.

    # Table Create    
    await db.create_table(
        'stocks', 
        [    
            ('order_num', int, 'AUTO_INCREMENT'),
            ('date', str),
            ('trans', str),
            ('symbol', str),
            ('qty', float),
            ('price', str)
        ], 
        'order_num' # Primary Key 
    )
    
    mysql> describe stocks;
    +-----------+---------+------+-----+---------+----------------+
    | Field     | Type    | Null | Key | Default | Extra          |
    +-----------+---------+------+-----+---------+----------------+
    | order_num | int(11) | NO   | PRI | NULL    | auto_increment |
    | date      | text    | YES  |     | NULL    |                |
    | trans     | text    | YES  |     | NULL    |                |
    | condition | text    | YES  |     | NULL    |                |
    | symbol    | text    | YES  |     | NULL    |                |
    | qty       | double  | YES  |     | NULL    |                |
    | price     | text    | YES  |     | NULL    |                |
    +-----------+---------+------+-----+---------+----------------+
    6 rows in set (0.00 sec)

## Creating Tables with Foreign Keys
<br>

    await db.create_table(
        'departments', 
        [    
            ('id', int, 'UNIQUE'),
            ('name', str)
        ], 
        'id' # Primary Key 
    )

    await db.create_table(
        'positions', 
        [    
            ('id', int, 'UNIQUE'),
            ('name', str),
            ('department_id', int)
        ], 
        'id', # Primary Key
        foreign_keys={
            'department_id': {
                'table': 'departments', 
                'ref': 'id',
                'mods': 'ON UPDATE CASCADE ON DELETE CASCADE'
            }
        },
        cache_enabled=True,
        cache_length=128
    )

    await db.create_table(
        'employees', 
        [    
            ('id', int, 'UNIQUE'),
            ('name', str),
            ('position_id', int)
        ], 
        'id', # Primary Key
        foreign_keys={
            'position_id': {
                'table': 'positions', 
                'ref': 'id',
                'mods': 'ON UPDATE CASCADE ON DELETE CASCADE'
            }
        }
        cache_enabled=True,
        cache_length=256
    )
    
## Insert Data
<br>

Requires key-value pairs - may be input using dict or the following

Un-packing

    # Note order_num is not required as auto_increment was specified
    trade = {'date': '2006-01-05', 'trans': 'BUY', 'symbol': 'RHAT', 'qty': 100.0, 'price': 35.14}
    await db.tables['stocks'].insert(**trade)

    query:
        INSERT INTO stocks 
            (date, trans, symbol, qty, price) 
        VALUES 
            ("2006-01-05", "BUY", "RHAT", 100, 35.14)

In-Line

    # Note order_num is not required as auto_increment was specified
    await db.tables['stocks'].insert(
        date='2006-01-05', 
        trans='BUY',
        symbol='RHAT',
        qty=200.0,
        price=65.14
    )

    query:
        INSERT INTO stocks 
            (date, trans, symbol, qty, price) 
        VALUES 
            ("2006-01-05", "BUY", "RHAT", 200, 65.14)

## Inserting Special Data
<br>
Columns of type string can hold JSON dumpable python dictionaries as JSON strings and are automatically converted back into dicts when read. 

Nested Dicts are also Ok, but all items should be JSON compatible data types

    tx_data = {
        'type': 'BUY', 
        'condition': {
            'limit': '36.00', 
            'time': 'end_of_trading_day'
        }
    }

    trade = {
        'order_num': 1, 'date': '2006-01-05', 
        'trans': tx_data, # 
        'symbol': 'RHAT', 
        'qty': 100, 'price': 35.14, 'after_hours': True
    }

    await db.tables['stocks'].insert(**trade)

<br>

    INSERT INTO 
        stocks 
        (
            order_num, date, trans, symbol, 
            qty, price, after_hours
        ) 
        VALUES 
            (
                1, "2006-01-05", 
                '{"type": "BUY", "condition": {"limit": "36.00", "time": "end_of_trading_day"}}', 
                "RHAT", 100, 35.14, True
            )
<br>

    sel = await db.tables['stocks'][1]
    print(sel['trans']['condition'])

<br>

    {'limit': '36.00', 'time': 'end_of_trading_day'}

        
## Select Data
<br><br>
All Rows & Columns in table

    await db.tables['employees'].select('*')

All Rows & Specific Columns 

    await db.tables['employees'].select(
        'id', 
        'name', 
        'position_id'
        )

All Rows & Specific Columns with Matching Values

    await db.tables['employees'].select(
        'id', 
        'name', 
        'position_id', 
        where={
            'id': 1000
        }
    )

All Rows & Specific Columns with Multple Matching Values

    await db.tables['employees'].select(
        'id', 
        'name', 
        'position_id', 
        where={
            'id': 1000, 
            'name': 'Frank Franklin'
        }
    )

## Advanced Usage:
<br><br>
All Rows & Columns from employees, Combining ALL Rows & Columns of table positions (if foreign keys match)

    # Basic Join
    await db.tables['employees'].select('*', join='positions')

<br>

    SELECT *
    FROM 
        employees 
    JOIN positions ON 
        employees.position_id = positions.id
    
<br>

    [
        {
            'employees.id': 1000, 
            'employees.name': 'Frank Franklin', 
            'employees.position_id': 100101, 
            'positions.name': 'Director', 
            'positions.department_id': 1001
        },
        ...
    ]

All Rows & Specific Columns from employees, Combining All Rows & Specific Columns of table positions (if foreign keys match)

### Basic Join 

    await db.tables['employees'].select(
        'employees.name', 
        'positions.name', 
        join='positions' # # possible only if foreign key relation exists between employees & positions
        )
<br>

    SELECT 
        employees.name,positions.name 
    FROM employees 
    JOIN positions ON 
        employees.position_id = positions.id
<br>

    [
        {'employees.name': 'Frank Franklin', 'positions.name': 'Director'}, 
        {'employees.name': 'Eli Doe', 'positions.name': 'Manager'},
        ...
    ]


<br>
    
### Basic Join with conditions

join='positions' will only work if the calling table "await db.tables['employees']" has a foreign-key reference to table 'positions'

    await db.tables['employees'].select(
        'employees.name', 
        'positions.name', 
        join='positions', # made possible if foreign key relation exists between employees & positions
        where={
            'positions.name': 'Director'}
        )
<br>

    SELECT 
        employees.name,
        positions.name 
    FROM 
        employees 
    JOIN positions ON 
        employees.position_id = positions.id 
    WHERE 
        positions.name='Director'

<br>

    [
        {'employees.name': 'Frank Franklin', 'positions.name': 'Director'}, 
        {'employees.name': 'Elly Doe', 'positions.name': 'Director'},
        ..
    ]


### Multi-table Join with conditions

    await db.tables['employees'].select(
        'employees.name', 
        'positions.name', 
        'departments.name', 
        join={
            'positions': {
                'employees.position_id': 'positions.id'
                }, 
            'departments': {
                'positions.department_id': 'departments.id'
                }
        }, 
        where={
            'positions.name': 'Director'}
        )
<br>

    SELECT 
        employees.name,positions.name,
        departments.name 
    FROM employees 
    JOIN positions ON 
        employees.position_id = positions.id 
    JOIN departments ON 
        positions.department_id = departments.id 
    WHERE 
        positions.name='Director'
<br>

    [
        {'employees.name': 'Frank Franklin', 'positions.name': 'Director', 'departments.name': 'HR'}, 
        {'employees.name': 'Elly Doe', 'positions.name': 'Director', 'departments.name': 'Sales'}
    ]

Special Note: When performing multi-table joins, joining columns must be explicity provided. 
<br>The key-value order is not explicity important, but will determine which column name is present in returned rows


    join={'y_table': {'y_table.id': 'x_table.y_id'}}
    result:
        [
            {'x_table.a': 'val1', 'y_table.id': 'val2'},
            {'x_table.a': 'val1', 'y_table.id': 'val3'}
        ]
OR

    join={'y_table': {'x_table.y_id': 'y_table.id'}}
    result:
        [
            {'x_table.a': 'val1', 'x_table.y_id': 'val2'},
            {'x_table.a': 'val1', 'x_table.y_id': 'val3'}
        ]

## Operators
<br><br>
The Following operators are supported within the list query syntax

    '=', '==', '<>', '!=', '>', '>=', '<', '<=', 'like', 'in', 'not in', 'not like'

Operator Syntax Requires a list-of-lists and supports multiple combined conditions


    await db.tables['table'].select(
        '*',
        where=[[condition1], [condition2], [condition3]]
    )

<br>

    await db.tables['table'].select(
        '*',
        where=[
            ['col1', 'like', 'abc*'],               # Wildcards 
            ['col2', '<', 10],                      # Value Comparison
            ['col3', 'not in', ['a', 'b', 'c'] ]    # Inclusion / Exclusion
        ]
    )

### List Syntax - Examples:

Search for rows which contain specified chars using wild card '*' 

    find_employee = await db.tables['employees'].select(
        'id', 
        'name',
        where=[
            ['name', 'like', '*ank*'] # Double Wild Card - Search
        ]
    )
<br>

        SELECT id,name FROM employees WHERE name like '%ank%'
<br>

    [
        {'id': 1016, 'name': 'Frank Franklin'}, 
        {'id': 1018, 'name': 'Joe Franklin'}, 
        {'id': 1034, 'name': 'Dana Franklin'}, 
        {'id': 1036, 'name': 'Jane Franklin'}, 
        {'id': 1043, 'name': 'Eli Franklin'}, 
    ]


Delete Rows matching value comparison


    delete_department = await db.tables['departments'].delete(
        where=[
            ['id', '<', 2000] # Value Comparison
        ]
    )
<br>
        DELETE FROM departments WHERE id < 2000
<br>

Select Rows using Join and exluding rows with sepcific values

    join_sel = db.tables['employees'].select(
        '*', 
        join={
            'positions': {
                'employees.position_id':'positions.id', 
                'positions.id': 'employees.position_id'
            }
        },
        where=[
            [
                'positions.name', 'not in', ['Manager', 'Intern', 'Rep'] # Exclusion within Join
            ],
            [
                'positions.department_id', '<>', 2001                    # Exclusion via NOT EQUAL
            ]
        ]
    )
<br>

    SELECT * FROM employees 
    JOIN positions ON 
        employees.position_id = positions.id  
    AND  
        positions.id = employees.position_id 
    WHERE 
        positions.name not in ('Manager', 'Intern', 'Rep') 
    AND 
        positions.department_id <> 2001


## Special Examples:
<br><br>
Bracket indexs can only be used for primary keys and return entire row, if existent

    await db.tables['employees'][1000] 

<br>

    SELECT * FROM employees 
    WHERE id=1000
<br>

    {'id': 1000, 'name': 'Frank Franklin', 'position_id': 100101}

Note: As  db.tables['employees'][1000] returns an 'awaitable', sub keys cannot be specified until the object has been 'awaited'
 
    # Incorrect
    emp_id = await db.tables['employees'][1000]['id']
<br>

    __main__:1: RuntimeWarning: coroutine was never awaited
    RuntimeWarning: Enable tracemalloc to get the object allocation traceback
    Traceback (most recent call last):
    File "<stdin>", line 1, in <module>
    TypeError: 'coroutine' object is not subscriptable
<br>

    # Correct
    sel = await db.tables['employees'][1000]
    emp_id = sel['id]

    
### Iterate through table - grab all rows - allowing client side filtering 

    async for row in db.tables['employees']:
        print(row['id], row['name'])
<br>

    SELECT * FROM employees
<br>

    1000 Frank Franklin
    1001 Eli Doe
    1002 Chris Smith
    1003 Clara Carson
    
### Using list comprehension

    sel = [tuple(row['id'], row['name']) async for row in db.tables['employees']]
<br>

    SELECT * FROM employees
<br>

    [
        (1000, 'Frank Franklin'), 
        (1001, 'Eli Doe'), 
        (1002, 'Chris Smith'), 
        (1003, 'Clara Carson'),
        ...
    ]

## Update Data

<br><br>

#### In-line

    await db.tables['stocks'].update(
        symbol='NTAP',
        trans='SELL', 
        where={'order_num': 1}
    )

<br>
    
    UPDATE stocks 
    SET 
        symbol = 'NTAP', 
        trans = 'SELL' 
    WHERE 
        order_num=1

#### Un-Pack

    # JSON Serializable Data 

    tx_data = {
        'type': 'BUY', 
        'condition': {
            'limit': '36.00', 
            'time': 'end_of_trading_day'
        }
    }

    to_update = {
        'symbol': 'NTAP', 
        'trans': tx_data # dict
        }

    await db.tables['stocks'].update(
        **to_update, 
        where={'order_num': 1}
        )
<br>

    UPDATE stocks 
    SET 
        symbol = 'NTAP', 
        trans = '{"type": "BUY", "condition": {"limit": "36.00", "time": "end_of_trading_day"}}' 
    WHERE 
        order_num=1

#### Using set_item

    await db.tables['table'].set_item('primary_key': {'column': 'value'})

<br>

    #JSON Serializable Data 

    tx_data = {
        'type': 'BUY', 
        'condition': {
            'limit': '36.00', 
            'time': 'end_of_trading_day'
            }
        }
    to_update = {
        'symbol': 'NTAP', 
        'trans': tx_data, # dict
        'qty': 500}

    await db.tables['stocks'].set_item(2, to_update)
<br>
    
    # two resulting db querries
    # checks that primary_key value 2 exists

    SELECT * FROM stocks WHERE order_num=2

    # update 

    UPDATE stocks 
    SET
        symbol = 'NTAP', 
        trans = '{"type": "BUY", "condition": {"limit": "36.00", "time": "end_of_trading_day"}}', 
        qty = 500 
    WHERE order_num=2

<br>

    await db.tables['stocks'][2]
        
    # beutified
    {
        'order_num': 2, 
        'date': '2006-01-05', 
        'trans': {
            'type': 'BUY', 
            'condition': {
                'limit': '36.00', 
                'time': 'end_of_trading_day'
            }
        }, 
        'symbol': 'NTAP', 
        'qty': 500, 
        'price': 35.16, 
        'after_hours': True
    }


## Delete Data 
<br><br>

    await db.tables['stocks'].delete(
        where={'order_num': 1}
    )