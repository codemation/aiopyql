## Inserting

Requires key-value pairs - may be input using dict or the following

#### Un-Packing

```python
# Note order_num is not required as auto_increment was specified
trade = {
    'date': '2006-01-05', 
    'trans': 'BUY', 
    'symbol': 'RHAT', 
    'qty': 100.0, 
    'price': 35.14
}

await db.tables['stocks'].insert(**trade)
```

```sql
    INSERT INTO stocks 
        (date, trans, symbol, qty, price) 
    VALUES 
        ("2006-01-05", "BUY", "RHAT", 100, 35.14)
```

#### In-Line

```python
# Note order_num is not required as auto_increment was specified

await db.tables['stocks'].insert(
    date='2006-01-05', 
    trans='BUY',
    symbol='RHAT',
    qty=200.0,
    price=65.14
)
```
!!! NOTE
    order_num is not required as auto_increment was specified

```sql
INSERT INTO stocks 
    (date, trans, symbol, qty, price) 
VALUES 
    ("2006-01-05", "BUY", "RHAT", 200, 65.14)
```

#### JSON

Columns of type string can hold JSON dumpable python dictionaries as JSON strings and are automatically converted back into dicts when read. 

!!! TIP
    Nested Dicts are also Ok, but all items should be JSON compatible data types

```python
tx_data = {
    'type': 'BUY', 
    'condition': {
        'limit': '36.00', 
        'time': 'end_of_trading_day'
    }
}

trade = {
    'order_num': 1, 
    'date': '2006-01-05', 
    'trans': tx_data, # 
    'symbol': 'RHAT', 
    'qty': 100, 
    'price': 35.14, 
    'after_hours': True
}

await db.tables['stocks'].insert(**trade)
```

```sql
INSERT INTO stocks 
    (order_num, date, trans, symbol, 
        qty, price, after_hours) 
VALUES (
    1, 
    "2006-01-05", 
    '{"type": "BUY", "condition": {"limit": "36.00", "time": "end_of_trading_day"}}', 
    "RHAT", 
    100, 
    35.14, 
    True
    )
```
```python
sel = await db.tables['stocks'][1]

print(sel['trans']['condition'])

{'limit': '36.00', 'time': 'end_of_trading_day'}
```