# aioaiopyql
Asyncio ORM(Object-relational mapping) for accessing, inserting, updating, deleting data within RBDMS tables using python

### Instalation

    $ python3 -m venv env

    $ source my-project/bin/activate

Install with PIP

     (env)$ pip install aiopyql-db   

Download & install Library from Github:

    (env)$ git clone https://github.com/codemation/aiopyql.git

Use install script to install the aiopyql into the activated environment libraries

    (env)$ cd aiopyql; sudo ./install.py install

### Compatable Databases - Currently

- mysql
- sqlite

## Getting Started 

### DB connection

        import sqlite3
        from aiopyql import data

        db = data.Database(
            database="testdb"
            )
    
        from aiopyql import data

        db = data.Database(
            database='mysql_database',
            user='mysqluser',
            password='my-secret-pw',
            host='localhost',
            type='mysql'
            )
Existing tables schemas within databases are loaded when database object is instantiated and ready for use immedielty.

### Table Create
Requires List of at least 2 item tuples, max 3

('column_name', type, 'modifiers')

- column_name - str - database column name exclusions apply
- types: str, int, float, byte, bool, None # JSON dumpable dicts fall under str types
- modifiers: NOT NULL, UNIQUE, AUTO_INCREMENT

Note Some differences may apply for column options i.e AUTOINCREMENT(sqlite) vs AUTO_INCREMENT(mysql) - 
See DB documentation for reference.

Note: Unique constraints are not validated by aiopyql but at db, so if modifier is supported it will be added when table is created.

    # Table Create    
    db.create_table(
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

#### Creating Tables with Foreign Keys

    db.create_table(
        'departments', 
        [    
            ('id', int, 'UNIQUE'),
            ('name', str)
        ], 
        'id' # Primary Key 
    )

    db.create_table(
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
        }
    )

    db.create_table(
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
    )

    
### Insert Data
Requires key-value pairs - may be input using dict or the following

Un-packing

    # Note order_num is not required as auto_increment was specified
    trade = {'date': '2006-01-05', 'trans': 'BUY', 'symbol': 'RHAT', 'qty': 100.0, 'price': 35.14}
    await db.tables['stocks'].insert(**trade)

    query:
        INSERT INTO stocks (date, trans, symbol, qty, price) VALUES ("2006-01-05", "BUY", "RHAT", 100, 35.14)

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
        INSERT INTO stocks (date, trans, symbol, qty, price) VALUES ("2006-01-05", "BUY", "RHAT", 200, 65.14)

#### Inserting Special Data 
- Columns of type string can hold JSON dumpable python dictionaries as JSON strings and are automatically converted back into dicts when read. 
- Nested Dicts are also Ok, but all items should be JSON compatible data types


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
        query:
            INSERT INTO stocks (order_num, date, trans, symbol, qty, price, after_hours) VALUES (1, "2006-01-05", '{"type": "BUY", "condition": {"limit": "36.00", "time": "end_of_trading_day"}}', "RHAT", 100, 35.14, True)
        result:
            In:
                db.tables['stocks'][1]['trans']['condition'] # synchronus - run outside of event loop
            Out: #
                {'limit': '36.00', 'time': 'end_of_trading_day'}

        
### Select Data
#### Basic Usage:

All Rows & Columns in table

    await db.tables['employees'].select('*')

All Rows & Specific Columns 

    await db.tables['employees'].select(
        'id', 'name', 'position_id'
        )

All Rows & Specific Columns with Matching Values

    await db.tables['employees'].select(
        'id', 'name', 'position_id', 
        where={'id': 1000}
        )

All Rows & Specific Columns with Multple Matching Values

    await db.tables['employees'].select(
        'id', 'name', 'position_id', 
        where={'id': 1000, 'name': 'Frank Franklin'}
        )

#### Advanced Usage:

All Rows & Columns from employees, Combining ALL Rows & Columns of table positions (if foreign keys match)

    # Basic Join
    await db.tables['employees'].select('*', join='positions')
    query:
        SELECT * FROM employees JOIN positions ON employees.position_id = positions.id
    output:
        [{
            'employees.id': 1000, 'employees.name': 'Frank Franklin', 
            'employees.position_id': 100101, 'positions.name': 'Director', 
            'positions.department_id': 1001},
            ...
        ]
All Rows & Specific Columns from employees, Combining All Rows & Specific Columns of table positions (if foreign keys match)

    # Basic Join 
    await db.tables['employees'].select(
        'employees.name', 
        'positions.name', 
        join='positions'
        )
    query:
        SELECT employees.name,positions.name FROM employees JOIN positions ON employees.position_id = positions.id
    output:
        [
            {'employees.name': 'Frank Franklin', 'positions.name': 'Director'}, 
            {'employees.name': 'Eli Doe', 'positions.name': 'Manager'},
            ...
        ]

All Rows & Specific Columns from employees, Combining All Rows & Specific Columns of table positions (if foreign keys match) with matching 'position.name' value

    # Basic Join with conditions
    await db.tables['employees'].select(
        'employees.name', 
        'positions.name', 
        join='positions',
        where={
            'positions.name': 'Director'}
        )
    query:
        SELECT employees.name,positions.name FROM employees JOIN positions ON employees.position_id = positions.id WHERE positions.name='Director'
    output:
        [
            {'employees.name': 'Frank Franklin', 'positions.name': 'Director'}, 
            {'employees.name': 'Elly Doe', 'positions.name': 'Director'},
            ..
        ]

All Rows & Specific Columns from employees, Combining Specific Rows & Specific Columns of tables positions & departments

Note: join='x_table' will only work if the calling table has a f-key reference to table 'x_table'

    # Multi-table Join with conditions
    await db.tables['employees'].select(
        'employees.name', 
        'positions.name', 
        'departments.name', 
        join={
            'positions': {'employees.position_id': 'positions.id'}, 
            'departments': {'positions.department_id': 'departments.id'}
        }, 
        where={'positions.name': 'Director'})
    query:
        SELECT employees.name,positions.name,departments.name FROM employees JOIN positions ON employees.position_id = positions.id JOIN departments ON positions.department_id = departments.id WHERE positions.name='Director'
    result:
        [
            {'employees.name': 'Frank Franklin', 'positions.name': 'Director', 'departments.name': 'HR'}, 
            {'employees.name': 'Elly Doe', 'positions.name': 'Director', 'departments.name': 'Sales'}
        ]

Special Note: When performing multi-table joins, joining columns must be explicity provided. The key-value order is not explicity important, but will determine which column name is present in returned rows

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


#### Special Examples:
Bracket indexs can only be used for primary keys and return entire row, if existent

    db.tables['employees'][1000] # Synchronus only
    query:
        SELECT * FROM employees WHERE id=1000
    result:
        {'id': 1000, 'name': 'Frank Franklin', 'position_id': 100101}
    
Iterate through table - grab all rows - allowing client side filtering 

    async for row in db.tables['employees']:
        print(row['id], row['name'])
    query:
        SELECT * FROM employees
    result:
        1000 Frank Franklin
        1001 Eli Doe
        1002 Chris Smith
        1003 Clara Carson
    
Using list comprehension

    sel = [(row['id'], row['name']) async for row in db.tables['employees']]
    query:
        SELECT * FROM employees
    result:
        [
            (1000, 'Frank Franklin'), 
            (1001, 'Eli Doe'), 
            (1002, 'Chris Smith'), 
            (1003, 'Clara Carson'),
            ...
        ]


### Update Data

Define update values in-line or un-pack

    await db.tables['stocks'].update(
        symbol='NTAP',trans='SELL', 
        where={'order_num': 1}
        )
    query:
        UPDATE stocks SET symbol = 'NTAP', trans = 'SELL' WHERE order_num=1

Un-Pack

    #JSON capable Data 
    tx_data = {'type': 'BUY', 'condition': {'limit': '36.00', 'time': 'end_of_trading_day'}}
    to_update = {'symbol': 'NTAP', 'trans': tx_data}
    where = {'order_num': 1}

    await db.tables['stocks'].update(
        **to_update, 
        where=where
        )
    query:
        UPDATE stocks SET symbol = 'NTAP', trans = '{"type": "BUY", "condition": {"limit": "36.00", "time": "end_of_trading_day"}}' WHERE order_num=1

Bracket Assigment - Primary Key name assumed inside Brackets for value

    #JSON capable Data 

    tx_data = {'type': 'BUY', 'condition': {'limit': '36.00', 'time': 'end_of_trading_day'}}
    to_update = {'symbol': 'NTAP', 'trans': tx_data, 'qty': 500}

    db.tables['stocks'][2] = to_update # Synchronus only

    query:
        # check that primary_key value 2 exists
        SELECT * FROM stocks WHERE order_num=2

        # update 
        UPDATE stocks SET symbol = 'NTAP', trans = '{"type": "BUY", "condition": {"limit": "36.00", "time": "end_of_trading_day"}}', qty = 500 WHERE order_num=2

    result:
        db.tables['stocks'][2] # Synchronus only
        {
            'order_num': 2, 
            'date': '2006-01-05', 
            'trans': {'type': 'BUY', 'condition': {'limit': '36.00', 'time': 'end_of_trading_day'}}, 
            'symbol': 'NTAP', 
            'qty': 500, 
            'price': 35.16, 
            'after_hours': True
        }


### Delete Data 

    await db.tables['stocks'].delete(
        where={'order_num': 1}
        )

### Other
Table Exists

    'employees' in db
    query:
        show tables
    result:
        True

Primary Key Exists:

    1000 in db.tables['employees']
    query:
        SELECT * FROM employees WHERE id=1000
    result:
        True