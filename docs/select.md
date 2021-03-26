## Select
Selecting data in aiopyql should feel very familiar to SQL syntax

### Basic Usage

All Rows & Columns in table"
```python
await db.tables['employees'].select('*')
```

All Rows & Specific Columns 
```python
await db.tables['employees'].select(
    'id', 
    'name', 
    'position_id'
)
```

All Rows & Specific Columns with Matching Values
```python
await db.tables['employees'].select(
    'id', 
    'name', 
    'position_id', 
    where={
        'id': 1000
    }
)
```

All Rows & Specific Columns with Multple Matching Values
```python
await db.tables['employees'].select(
    'id', 
    'name', 
    'position_id', 
    where={
        'id': 1000, 
        'name': 'Frank Franklin'
    }
)
```

### Advanced
All Rows & Columns from employees, Combining ALL Rows & Columns of table positions (if foreign keys match)

```python
    # Basic Join
    await db.tables['employees'].select(
        '*', 
        join='positions'
    )
```
```sql
    SELECT *
    FROM 
        employees 
    JOIN positions ON 
        employees.position_id = positions.id
```
```python
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
```

All Rows & Specific Columns from employees, Combining All Rows & Specific Columns of table positions (if foreign keys match)


### Basic Join 

```python
await db.tables['employees'].select(
    'employees.name', 
    'positions.name', 
    join='positions' # # possible only if foreign key relation exists between employees & positions
)
```
```sql
SELECT 
    employees.name,positions.name 
FROM employees 
JOIN positions ON 
    employees.position_id = positions.id
```
```python
    [
        {'employees.name': 'Frank Franklin', 'positions.name': 'Director'}, 
        {'employees.name': 'Eli Doe', 'positions.name': 'Manager'},
        ...
    ]
```
### Basic Join w/ conditions
!!! TIP "join='positions'"
    This syntax is possible if the calling table "await db.tables['employees']" has a foreign-key reference to table 'positions'

```python

await db.tables['employees'].select(
    'employees.name', 
    'positions.name', 
    join='positions',
    where={
        'positions.name': 'Director'}
)
```
```sql

SELECT 
    employees.name,
    positions.name 
FROM 
    employees 
JOIN positions ON 
    employees.position_id = positions.id 
WHERE 
    positions.name='Director'

```
<br>

```python
[
    {
        'employees.name': 'Frank Franklin', 
        'positions.name': 'Director'
    }, 
    {
        'employees.name': 'Elly Doe', 
        'positions.name': 'Director'
    },
    ..
]
```

### Multi-table Join with conditions
```python
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
        'positions.name': 'Director'
    }
)
```
```sql
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
```
```python
[
    {
        'employees.name': 'Frank Franklin', 
        'positions.name': 'Director', 
        'departments.name': 'HR'
    }, 
    {
        'employees.name': 'Elly Doe', 
        'positions.name': 'Director', 
        'departments.name': 'Sales'
    }
]
```

### Considerations

<em>When performing multi-table joins, joining columns must be explicity provided.
<br>The key-value order is not explicity important, but will determine which column name is present in returned rows
</em>

```python
join={'y_table': {'y_table.id': 'x_table.y_id'}}
[
    {'x_table.a': 'val1', 'y_table.id': 'val2'},
    {'x_table.a': 'val1', 'y_table.id': 'val3'}
]

join={'y_table': {'x_table.y_id': 'y_table.id'}}

[
    {'x_table.a': 'val1', 'x_table.y_id': 'val2'},
    {'x_table.a': 'val1', 'x_table.y_id': 'val3'}
]
```


### Operators

The Following operators are supported within the list query syntax

```python
'=', '==', '<>', '!=', '>', '>=', '<', '<=', 'like', 'in', 'not in', 'not like'
```

#### Usage

Operator Syntax Requires a list-of-lists and supports multiple combined conditions

```python
await db.tables['table'].select(
    '*',
    where=[
        [condition1], 
        [condition2], 
        [condition3]
    ]
)
```
```python
await db.tables['table'].select(
    '*',
    where=[
        ['col1', 'like', 'abc*'],             # Wildcards 
        ['col2', '<', 10],                    # Value Comparison
        ['col3', 'not in', ['a', 'b', 'c'] ]  # Inclusion / Exclusion
    ]
)
```

#### Examples

Search for rows which contain specified chars using wild card '*' 
```python
find_employee = await db.tables['employees'].select(
    'id', 
    'name',
    where=[
        ['name', 'like', '*ank*'] # Double Wild Card - Search
    ]
)
```
```sql
SELECT id,name FROM employees WHERE name like '%ank%'
```
```python
[
    {'id': 1016, 'name': 'Frank Franklin'}, 
    {'id': 1018, 'name': 'Joe Franklin'}, 
    {'id': 1034, 'name': 'Dana Franklin'}, 
    {'id': 1036, 'name': 'Jane Franklin'}, 
    {'id': 1043, 'name': 'Eli Franklin'}, 
]
```


Select Rows using Join and exluding rows with sepcific values
```python
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
```
```sql
SELECT * FROM employees 
JOIN positions ON 
    employees.position_id = positions.id  
AND  
    positions.id = employees.position_id 
WHERE 
    positions.name not in ('Manager', 'Intern', 'Rep') 
AND 
    positions.department_id <> 2001
```

### Dictionary Lookup
Bracket indexs can only be used for primary keys and return entire row, if existent

```python
    await db.tables['employees'][1000] 
```

```sql
SELECT * FROM employees WHERE id=1000
```
```python
{'id': 1000, 'name': 'Frank Franklin', 'position_id': 100101}
```


```python
db.tables['employees'][1000]
```
!!! TIP
    As this returns an 'awaitable', sub keys cannot be specified until the object has been 'awaited'
 

```python
# Incorrect
emp_id = await db.tables['employees'][1000]['id']
```

```bash
__main__:1: RuntimeWarning: coroutine was never awaited
RuntimeWarning: Enable tracemalloc to get the object allocation traceback
Traceback (most recent call last):
File "<stdin>", line 1, in <module>
TypeError: 'coroutine' object is not subscriptable
```

```python
# Correct
sel = await db.tables['employees'][1000]
emp_id = sel['id]
```

### Iterate over rows via async for 

Requires client side filtering if results must be reduced

```python
async for row in db.tables['employees']:
    print(row['id'], row['name'])
```
```sql
SELECT * FROM employees
```
```bash
1000 Frank Franklin
1001 Eli Doe
1002 Chris Smith
1003 Clara Carson
```

### List comprehension
```python
sel = [tuple(row['id'], row['name']) async for row in db.tables['employees']]
```
```sql
SELECT * FROM employees
```
```python
[
    (1000, 'Frank Franklin'), 
    (1001, 'Eli Doe'), 
    (1002, 'Chris Smith'), 
    (1003, 'Clara Carson'),
    ...
]
```