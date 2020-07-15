import data, os, unittest, json, asyncio


class TestData(unittest.TestCase):
    def test_run_mysql_test(self):
        os.environ['DB_USER'] = 'josh'
        os.environ['DB_PASSWORD'] = 'abcd1234'
        os.environ['DB_HOST'] = 'localhost' if not 'DB_HOST' in os.environ else os.environ['DB_HOST']
        os.environ['DB_PORT'] = '3306'
        os.environ['DB_NAME'] = 'joshdb'
        os.environ['DB_TYPE'] = 'mysql'

        env = ['DB_USER','DB_PASSWORD','DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_TYPE']
        conf = ['user','password','host','port', 'db', 'type']
        config = {cnfVal: os.getenv(dbVal).rstrip() for dbVal,cnfVal in zip(env,conf)}
        config['debug'] = True

        # create event loop & start test coro
        loop = asyncio.new_event_loop()

        db = data.Database(
            loop=loop,
            **config
            )

        # Start tests
        loop.run_until_complete(async_test(db))
        test(db)
        loop.close()
        
    def test_run_sqlite_test(self):
        # create event loop & start test coro
        loop = asyncio.new_event_loop()

        db = data.Database(
            database="testdb",
            loop=loop,
            debug=True
            )
        loop.run_until_complete(async_test(db))
        test(db)
        loop.close()
        ref_database = data.Database(
            database="testdb",
            loop=loop,
            debug=True
            )
        print(ref_database.tables)
        colast_names = ['order_num', 'date', 'trans', 'symbol', 'qty', 'price', 'after_hours']
        for col in colast_names:
            assert col in ref_database.tables['stocks'].columns, f"missing column {col}"
        
def test(db):
    """
    Tests synchronus functions which should be run if no event loop exists
    """

    # key - value col insertion using tb[keyCol] = valCol
    db.tables['keystore']['key1'] = 'value1'
    assert 'key1' in db.tables['keystore'], "insertion failed using setitem"
    assert db.tables['keystore']['key1'] == 'value1', "value retrieval failed for key-value table"

    # key - value col update using setitem
    db.tables['keystore']['key1'] = 'newValue1'
    assert db.tables['keystore']['key1'] == 'newValue1', "update failed using setitem"

    # double col insertion using json

    db.tables['keystore']['config1'] = {'a': 1, 'b': 2, 'c': 3}
    assert 'config1' in  db.tables['keystore'], "insertion failed using setitem for json data"


    # Update Data via __setitem__
    db.tables['stocks'][2] = {'symbol': 'NTNX', 'trans': {'type': 'BUY'}}
    # Select via getItem
    sel = db.tables['stocks'][2]
    print(sel)
    assert sel['trans']['type'] == 'BUY' and sel['symbol'] == 'NTNX', f"values not correctly updated"

    # Check 'in' functioning
    assert 2 in db.tables['stocks'], "order 2 should still exist"
    print(sel)

    # Check 'in' functioning for db

    assert 'stocks' in db, "stocks table should still exist here"

async def async_test(db):
    import random
    for table in ['employees', 'positions', 'departments', 'keystore', 'stocks']:
        if table in db.tables:
            await db.run(f'drop table {table}')

    def check_sel(requested, selection):
        request_items = []
        if requested == '*':
            request_items = trade.keys()
        else:
            for request in requested:
                assert request in trade, f'{request} is not a valid column in {trade}'
                request_items.append(request)
        
        for col, value in trade.items():
            if col in request_items:
                assert len(selection) > 0, f"selection should be greater than lenth 0, data was inserted"
                assert col in selection[0], f"missing column '{col}' in select return"
                assert str(value) == str(sel[0][col]), f"value {selection[0][col]} returned from select is not what was inserted {value}."


    assert str(type(db)) == "<class 'data.Database'>", "failed to create data.Database object)"

    await db.create_table(
        'stocks', 
        [    
            ('order_num', int, 'AUTO_INCREMENT' if db.type == 'mysql' else 'AUTOINCREMENT'),
            ('date', str),
            ('trans', str),
            ('symbol', str),
            ('qty', int),
            ('price', float),
            ('after_hours', bool)
        ], 
        'order_num' # Primary Key 
    )
    print(db.tables['stocks'].columns)
    assert 'stocks' in db.tables, "table creation failed"

     
    await db.create_table(
        'departments', 
        [    
            ('id', int, 'UNIQUE'),
            ('name', str)

        ], 
        'id' # Primary Key 
    )
    assert 'departments' in db.tables, "table creation failed"

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
        }
    )
    assert 'positions' in db.tables, "table creation failed"

    await db.create_table(
        'employees', 
        [    
            ('id', int, 'UNIQUE'),
            ('name', str),
            ('position_id', int),

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
    assert 'employees' in db.tables, "table creation failed"

    await db.create_table(
        'keystore', 
        [    
            ('env', str, 'UNIQUE NOT NULL'),
            ('val', str)
        ], 
        'env' # Primary Key 
    )

    assert 'keystore' in db.tables, "table creation failed"

    ##


    colast_names = ['order_num', 'date', 'trans', 'symbol', 'qty', 'price', 'after_hours']
    for col in colast_names:
        assert col in db.tables['stocks'].columns

    # JSON Load test
    tx_data = {'type': 'BUY', 'condition': {'limit': '36.00', 'time': 'end_of_trading_day'}}

    trade = {'order_num': 1, 'date': '2006-01-05', 'trans': tx_data, 'symbol': 'RHAT', 'qty': 100, 'price': 35.14, 'after_hours': True}

    # pre insert * select # trade
    sel = await db.tables['stocks'].select('*')
    assert not len(sel) > 0, "no values should exist yet"


    await db.tables['stocks'].insert(**trade)
    #    OR
    # db.tables['stocks'].insert(
    #     date='2006-01-05', # Note order_num was not required as auto_increment was specified
    #     trans='BUY',
    #     symbol='NTAP',
    #     qty=100.0,
    #     price=35.14,
    #     after_hours=True
    # )
    import uuid
    # create departments
    
    departments = [
        {'id': 1001, 'name': 'HR'},
        {'id': 2001, 'name': 'Sales'},
        {'id': 3001, 'name': 'Support'},
        {'id': 4001, 'name': 'Marketing'}
    ]
    new_departments = []
    for department in departments:
        new_departments.append(
            asyncio.create_task(
                db.tables['departments'].insert(**department)
            )
        )
    await asyncio.gather(*new_departments)
    
    positions = [
        {'id': 100101, 'name': 'Director', 'department_id': 1001},
        {'id': 100102, 'name': 'Manager', 'department_id': 1001},
        {'id': 100103, 'name': 'Rep', 'department_id': 1001},
        {'id': 100104, 'name': 'Intern', 'department_id': 1001},
        {'id': 200101, 'name': 'Director', 'department_id': 2001},
        {'id': 200102, 'name': 'Manager', 'department_id': 2001},
        {'id': 200103, 'name': 'Rep', 'department_id': 2001},
        {'id': 200104, 'name': 'Intern', 'department_id': 2001},
        {'id': 300101, 'name': 'Director', 'department_id': 3001},
        {'id': 300102, 'name': 'Manager', 'department_id': 3001},
        {'id': 300103, 'name': 'Rep', 'department_id': 3001},
        {'id': 300104, 'name': 'Intern', 'department_id': 3001},
        {'id': 400101, 'name': 'Director', 'department_id': 4001},
        {'id': 400102, 'name': 'Manager', 'department_id': 4001},
        {'id': 400103, 'name': 'Rep', 'department_id': 4001},
        {'id': 400104, 'name': 'Intern', 'department_id': 4001}
    ]
    
    def get_random_name():
        name = ''
        first_names = ['Jane', 'Jill', 'Joe', 'John', 'Chris', 'Clara', 'Dale', 'Dana', 'Eli', 'Elly', 'Frank', 'George']
        last_names = ['Adams', 'Bale', 'Carson', 'Doe', 'Franklin','Smith', 'Wallace', 'Jacobs']
        random_first, random_last = random.randrange(len(first_names)-1), random.randrange(len(last_names)-1)
        return f"{first_names[random_first]} {last_names[random_last]}"
    employees = []
    def add_employee(employee_id, count, position_id):
        emp_id = employee_id
        for _ in range(count):
            employees.append({'id': emp_id, 'name': get_random_name(), 'position_id': position_id})
            emp_id+=1
    employee_id = 1000
    new_positions = []
    for position in positions:
        print(position)
        new_positions.append(
            asyncio.create_task(
                db.tables['positions'].insert(**position)
            )
        )
        if position['name'] == 'Director':
            add_employee(employee_id, 1, position['id'])
            employee_id+=1
        elif position['name'] == 'Manager':
            add_employee(employee_id, 2, position['id'])
            employee_id+=2
        elif position['name'] == 'Rep':
            add_employee(employee_id, 4, position['id'])
            employee_id+=4
        else:
            add_employee(employee_id, 8, position['id'])
            employee_id+=8
    await asyncio.gather(*new_positions)
    
    new_employees = []
    for employee in employees:
        new_employees.append(
            asyncio.create_task(
                db.tables['employees'].insert(**employee)
            )
        )
    await asyncio.gather(*new_employees)
    # Select Data

    # join selects

    for position, count in [('Director', 4), ('Manager', 8), ('Rep', 16), ('Intern', 32)]:
        join_sel = await db.tables['employees'].select(
            '*', 
            join={
                'positions': {'employees.position_id': 'positions.id'},
                'departments': {'positions.department_id': 'departments.id'}
                },
            where={
                'positions.name': position
                }
            )
        assert len(join_sel) == count, f"expected number of {position}'s' is {count}, found {len(join_sel)}"
    for department in ['HR', 'Marketing', 'Support', 'Sales']:
        for position, count in [('Director', 1),('Manager', 2), ('Rep', 4), ('Intern', 8)]:
            join_sel = await db.tables['employees'].select(
                '*', 
                join={
                    'positions': {'employees.position_id': 'positions.id'},
                    'departments': {'positions.department_id': 'departments.id'}
                    },
                where={
                    'positions.name': position,
                    'departments.name': department
                    }
                )
            assert len(join_sel) == count, f"expected number of {position}'s' is {count}, found {len(join_sel)}"

    # join select - testing default key usage if not provided
    for position, count in [('Director', 4),('Manager', 8), ('Rep', 16), ('Intern', 32)]:
        join_sel = await db.tables['employees'].select(
            '*', 
            join='positions',
            where={'positions.name': position}
            )
        assert len(join_sel) == count, f"expected number of {position}'s' is {count}, found {len(join_sel)}"

    # join select - testing multiple single table conditions
    join_sel = await db.tables['employees'].select(
            '*', 
            join={
                'positions': {
                            'employees.position_id':'positions.id', 
                            'positions.id': 'employees.position_id'
                            }
                }
    )
    assert len(join_sel) == 60, f"expected number of employee's' is {60}, found {len(join_sel)}"

    
    # * select #
    sel = await db.tables['stocks'].select('*')
    print(sel)
    check_sel('*', sel)

    try:
        sel = await db.tables['stocks'].select('*', where={'doesNotExist': 'doesNotExist'})
    except Exception as e:
        assert type(e) == data.InvalidInputError, "select should have resulted in exception"

    # Iter Check
    sel = [row async for row in db.tables['stocks']]
    check_sel('*', sel)
    print(f"iter check ")

    # Partial insert

    partial_trade = {'date': '2006-01-05', 'trans': tx_data, 'price': 35.16,'qty': None, 'after_hours': True}

    await db.tables['stocks'].insert(**partial_trade)

    # * select # 
    sel = await db.tables['stocks'].select('*')
    print(sel)
    check_sel('*', sel)

    # * select NULL check # 
    sel = await db.tables['stocks'].select('*', where={'qty': None})
    print(sel)
    assert len(sel) > 0, "we should find at least 1 row with a NULL qty" 
    
    # * select + where # 
    sel = await db.tables['stocks'].select('*', where={'symbol':'RHAT'})
    print(sel)
    check_sel('*', sel)

    # single select 
    sel = await db.tables['stocks'].select('price', where={'symbol':'RHAT'})
    check_sel(['price'], sel)
    print(sel)
    # multi-select 
    sel = await db.tables['stocks'].select('price', 'date', where={'symbol':'RHAT'})
    check_sel(['price', 'date'], sel)
    print(sel)
    
    # Update Data
    tx_old = {'type': 'BUY', 'condition': {'limit': '36.00', 'time': 'end_of_trading_day'}}
    tx_data['type'] = 'SELL'
    
    await db.tables['stocks'].update(
        symbol='NTAP',trans=tx_data,
        after_hours=False, qty=101, 
        where={'order_num': 1, 'after_hours': True, 'trans': tx_old})
    sel = await db.tables['stocks'].select('*', where={'order_num': 1})
    sel = sel[0]
    print(sel)
    assert sel['trans']['type'] == 'SELL' and sel['symbol'] == 'NTAP', f"values not correctly updated"





    # update data - use None Value
    await db.tables['stocks'].update(
        symbol=None,trans=tx_data,
        after_hours=False, qty=101, 
        where={'qty': 101})

    # * select NULL check # 
    sel = await db.tables['stocks'].select('*', where={'qty': 101, 'symbol': None})
    print(sel)
    assert len(sel) > 0, "we should find at least 1 row with a NULL symbol" 


    # Delete Data 

    await db.tables['stocks'].delete(where={'order_num': 1, 'after_hours': False})
    sel = await db.tables['stocks'].select('*', where={'order_num': 1, 'after_hours': False})
    print(sel)
    assert len(sel) < 1, "delete should have removed order_num 1"


