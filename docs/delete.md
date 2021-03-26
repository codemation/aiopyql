## Delete

### Basic Usage

```python
    await db.tables['stocks'].delete(
        where={'order_num': 1}
    )
```

### List Syntax Filtering
Delete Rows matching value comparison
```python
delete_department = await db.tables['departments'].delete(
    where=[
        ['id', '<', 2000] # Value Comparison
    ]
)
```
```sql
DELETE FROM departments WHERE id < 2000
```

