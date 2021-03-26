## Update


### In-Line

```python
await db.tables['stocks'].update(
    symbol='NTAP',
    trans='SELL', 
    where={'order_num': 1}
)
```
```sql
UPDATE stocks 
SET 
    symbol = 'NTAP', 
    trans = 'SELL' 
WHERE 
    order_num=1
```

### JSON Serializable Data 

```python
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
```
```sql
UPDATE stocks 
SET 
    symbol = 'NTAP', 
    trans = '{"type": "BUY", "condition": {"limit": "36.00", "time": "end_of_trading_day"}}' 
WHERE 
    order_num=1
```


###  Using set_item()
```python
await db.tables['table'].set_item(
    'primary_key': {'column': 'value'}
)
```
```python
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
```
```sql    
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
```
```python
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
```