import asyncio
from aiopyql.exceptions import InvalidInputError

async def async_test(db):
    db = await db
    import random
    try:
        for table in ['employees', 'positions', 'departments', 'keystore', 'stocks']:
            if table in db.tables:
                await db.remove_table(table)
    except Exception as e:
        pass

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

                if isinstance(value, float):
                    assert f"{value:.2f}" == f"{sel[0][col]:.2f}", f"value {selection[0][col]} returned from select is not what was inserted {value}."
                else:
                    assert str(value) == str(sel[0][col]), f"value {selection[0][col]} returned from select is not what was inserted {value}."


    assert str(type(db)) == "<class 'aiopyql.data.Database'>", "failed to create data.Database object)"


    auto_increment = 'AUTO_INCREMENT' if db.type == 'mysql' else 'AUTOINCREMENT'

    await db.create_table(
        'stocks', 
        columns = [    
            ('order_num', int, auto_increment),
            ('date', str),
            ('trans', str),
            ('symbol', str),
            ('qty', int),
            ('price', float),
            ('after_hours', bool)
        ], 
        prim_key='order_num', # Primary Key
        cache_enabled=True
    )
    print(db.tables['stocks'].columns)
    assert 'stocks' in db.tables, "table creation failed"

    ## Test creating table with 'str': str types

    await db.create_table(
        'departments', 
        [    
            ['id', 'int', 'UNIQUE'],
            ['name', 'str']

        ], 
        'id', # Primary Key 
        cache_enabled=True
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
        },
        cache_enabled=True
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
        },
        cache_enabled=True
    )
    assert 'employees' in db.tables, "table creation failed"

    await db.create_table(
        'keystore', 
        [    
            ('env', str, 'UNIQUE NOT NULL'),
            ('val', str)
        ], 
        'env', # Primary Key
        cache_enabled=True 
    )

    assert 'keystore' in db.tables, "table creation failed"

    ##


    colast_names = ['order_num', 'date', 'trans', 'symbol', 'qty', 'price', 'after_hours']
    for col in colast_names:
        assert col in db.tables['stocks'].columns

    # JSON Load test
    tx_data = {'type': 'BUY', 'condition': {'limit': '36.00', 'time': 'end_of_trading_day'}}

    trade = {'date': '2006-01-05', 'trans': tx_data, 'symbol': 'RHAT', 'qty': 100, 'price': 35.14, 'after_hours': True}

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
            db.tables['departments'].insert(**department)
        )
    await asyncio.gather(*new_departments)

    print(await db.tables['departments'][1001])
    
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
            db.tables['positions'].insert(**position)
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
            db.tables['employees'].insert(**employee)
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
        assert len(join_sel) == count, f"expected number of {position}'s' is {count}, found {len(join_sel)} for {join_sel}"
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

    # table migration on foreign key tables
    await db.create_table(
        'departments', 
        [    
            ['id', 'int', 'UNIQUE'],
            ['name', 'str'],
            ['location', 'str']
        ], 
        'id', # Primary Key 
        cache_enabled=True
    )

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

   # Like Operator Usage

    join_sel = await db.tables['employees'].select(
        '*', 
        join={
            'positions': {
                'employees.position_id':'positions.id', 
                'positions.id': 'employees.position_id'
            }
        },
        where=[
            ['positions.name', 'like', 'Dir*']
        ]
    )
    assert len(join_sel) == 4, f"expected number of employee's' is {4}, found {len(join_sel)}"

    # In operator Usage

    join_sel = await db.tables['employees'].select(
        '*', 
        join={
            'positions': {
                'employees.position_id':'positions.id', 
                'positions.id': 'employees.position_id'
            }
        },
        where=[
            [
                'positions.name', 'in', ['Manager', 'Director']
            ]
        ]
    )
    assert len(join_sel) == 12, f"expected number of employee's' is {12}, found {len(join_sel)}"


    # Not in Operator Usage

    join_sel = await db.tables['employees'].select(
        '*', 
        join={
            'positions': {
                'employees.position_id':'positions.id', 
                'positions.id': 'employees.position_id'
            }
        },
        where=[
            [
                'positions.name', 'not in', ['Manager', 'Intern', 'Rep']
            ]
        ]
    )
    assert len(join_sel) == 4, f"expected number of employee's' is {4}, found {len(join_sel)}"

    # Not in Operator Usage

    join_sel = await db.tables['employees'].select(
        '*', 
        join={
            'positions': {
                'employees.position_id':'positions.id', 
                'positions.id': 'employees.position_id'
            }
        },
        where=[
            [
                'positions.name', 'not in', ['Manager', 'Intern', 'Rep']
            ],
            {
                "positions.id": 100101
            }
        ]
    )
    assert len(join_sel) == 1, f"expected number of employee's' is {1}, found {len(join_sel)}"

    # Less Than Operator Usage

    join_sel = await db.tables['employees'].select(
        '*', 
        join={
            'positions': {
                'employees.position_id':'positions.id', 
                'positions.id': 'employees.position_id'
            }
        },
        where=[
            [
                'positions.name', 'not in', ['Manager', 'Intern', 'Rep']
            ],
            [
                'positions.department_id', '<', 2000
            ]
        ]
    )
    assert len(join_sel) == 1, f"expected number of employee's' is {1}, found {len(join_sel)}"   

    # Less Than Operator Usage + 'not in'

    join_sel = await db.tables['employees'].select(
        '*', 
        join={
            'positions': {
                'employees.position_id':'positions.id', 
                'positions.id': 'employees.position_id'
            }
        },
        where=[
            [
                'positions.name', 'not in', ['Manager', 'Intern', 'Rep']
            ],
            [
                'positions.department_id', '<>', 2001 # not equal
            ]
        ]
    )
    assert len(join_sel) == 3, f"expected number of employee's' is {3}, found {len(join_sel)}"  

    delete_department = await db.tables['departments'].delete(
        where=[
            ['id', '<', 2000]
        ]
    )

    find_employee = await db.tables['employees'].select(
        'id', 
        'name',
        where=[
            ['name', 'like', '*ank*']
        ]
    )
    assert len(find_employee) > 0, f"expected at least 1 employee, found {len(find_employee)}"

    
    # * select #
    sel = await db.tables['stocks'].select('*')
    print(sel)
    check_sel('*', sel)

    try:
        sel = await db.tables['stocks'].select('*', where={'doesNotExist': 'doesNotExist'})
    except Exception as e:
        assert type(e) == InvalidInputError, "select should have resulted in exception"

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
    assert len(sel) < 1, f"delete should have removed order_num 1, found {sel}"

    # Update Data
    #await db.tables['stocks'].update(
    #    **{'symbol': 'NFLX', 'trans': {'type': 'SELL'}},
    #    where={'order_num': 2}
    #)
    await db.tables['stocks'].set_item(2, {'symbol': 'NFLX', 'trans': {'type': 'SELL'}},)

    # Select via __getitem__
    sel = await db.tables['stocks'][2]
    print(sel)
    assert sel['trans']['type'] == 'SELL' and sel['symbol'] == 'NFLX', f"values not correctly updated"

    import sys
    
    for table in db.tables:
        print(f"## SIZE OF CACHE - {sys.getsizeof(db.tables[table].cache)} ##")
        print(f"## {table.upper()} CACHE ##")
        print(db.tables[table].cache)
    
    await asyncio.sleep(2)

    await db.close()