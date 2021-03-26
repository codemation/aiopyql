## Table


### Creating a Table
```python
database.create_table(self, 
    name: str, 
    columns: list, 
    prim_key: str,
    foreign_keys: Optional[dict] = None,
    cache_enabled: Optional[bool] = False,
    max_cache_len: Optional[int] = 125
```
### Columns

Requires List of min 2 item tuples, max 3
```python
('column_name', int|str|float|bytes, 'modifiers')
```

- column_name - str - database column name exclusions apply
- types: str, int, float, byte, bool, None # JSON dumpable dicts fall under str types
- modifiers: NOT NULL, UNIQUE, AUTO_INCREMENT
!!! TIP
    Some Column modifiers apply for column options i.e 

        AUTOINCREMENT  (sqlite|postgres)
        AUTO_INCREMENT (mysql)

    See DB documentation for reference.
### Example - Basic
``` python
await db.create_table(
    'keystore',
    [
        ('key', str, 'UNIQUE NOT NULL'),
        ('value', str)
    ],
    'key',
    cache_enabled=True
)
```

### Example - Foreign w/ Key


```python
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
    },
    cache_enabled=True,
    cache_length=256
)
```
!!! NOTE
    Unique constraints are not validated by aiopyql but at db, so if modifier is supported it will be added when table is created.

### Migrations
Changes to existing table schemas via db.create_table() will trigger a table migration which takes place automatically in 3 phases
!!! INFO "Phase 1"
    Database backup is created for current schema, created in JSON to a file with timestamp
!!! INFO "Phase 2"
    Existing table is dropped, and new table is created with updated schema
!!! Success "Phase 3"
    Backup is restored into newly created table