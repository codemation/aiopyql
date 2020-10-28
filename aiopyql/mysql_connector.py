from aiomysql import create_pool
from aiopyql.utilities import flatten, no_blanks, inner, TableColumn
import json
def get_db_manager():
    """
    returns async generator which manages context
    of the async db connection 
    """
    async def mysql_connect(*args, **kwds):
        pool = await create_pool(*args, **kwds)
        try:
            async with pool.acquire() as conn:
                yield conn
        except Exception as e:
            pass
        pool.close()
        await pool.wait_closed()
    return mysql_connect

def get_cursor_manager(database):
    """
    returns async generator which manages context of cursor
    or passes db connection, as well as processes db commit
    for changes
    """
    async def mysql_cursor(commit=False):
        async for db in database.connect(**database.connect_config):
            async with db.cursor() as c:
                try:
                    yield (c, db)
                except Exception as e:
                    database.log.exception(f"error yielding cursor {repr(e)}")
            if commit:
                await db.commit() 
        return                
    return mysql_cursor
def show_tables(database):
    pass
async def load_tables(db):
    tables_in_db_coro = await db.get("show tables")
    def describe_table_to_col(column):
        TYPE_TRANSLATE = {'tinyint': bool, 'int': int, 'text': str, 'double': float, 'varchar': str}
        config = []
        for i in ' '.join(column.split(',')).split(' '):
            if not i == '' and not i == '\n':
                config.append(i.rstrip())
        column = config
        field = inner(column[0], '`','`')
        typ = None
        for k, v in TYPE_TRANSLATE.items():
            if k in column[1]:
                typ = v
                break
        if typ == None:
            raise InvalidColumnType(column[1], f"invalid type provided for column, supported types {list(TYPE_TRANSLATE.keys())}")
        """
        Null = 'NOT NULL ' if column[2] == 'NO' else ''
        Key = 'PRIMARY KEY ' if column[3] == 'PRI' else ''
        Default = '' # TOODOO - check if this needs implementing
        """
        extra = ' '.join(column[2:])
        return TableColumn(field, typ, extra)
    for table, in tables_in_db_coro:
        cols_in_table = []
        table_schemas = await db.get(f'show create table {table}')
        for _, schema in table_schemas:
            schema = flatten(schema.split(f'CREATE TABLE `{table}`')[1])
            col_config = inner(schema).split(', ')
            cols_in_table = []
            foreign_keys = None
            for cfg in col_config:
                if not 'FOREIGN KEY' in cfg:
                    if not 'PRIMARY KEY' in cfg:
                        if not 'KEY' in cfg:
                            cols_in_table.append(describe_table_to_col(cfg))
                    else:
                        primary_key = inner(inner(cfg.split('PRIMARY KEY')[1]), '`', '`')
                else:
                    if foreign_keys == None:
                        foreign_keys = {}
                    local_key, ref = cfg.split('FOREIGN KEY')[1].split('REFERENCES')
                    local_key = inner(inner(local_key), '`', '`')
                    parent_table, mods = ref.split(')')
                    parent_table, parent_key = parent_table.split('(')
                    foreign_keys[no_blanks(local_key)] = {
                        'table': no_blanks(inner(parent_table, '`', '`')), 
                        'ref': no_blanks(inner(parent_key, '`', '`')),
                        'mods': mods.rstrip()
                            }
        table = inner(table, '`', '`')
        await db.create_table(table, cols_in_table, primary_key, foreign_keys=foreign_keys, existing=True)
def validate_where_input(db, tables, where):
    for table in tables:
        for col_name, col in table.columns.items():
            if not col_name in where:
                continue
            if not col.type == bool:
                #JSON handling
                if col.type == str and type(where[col_name]) == dict:
                    where[col_name] = f"'{col.type(json.dumps(where[col_name]))}'"
                    continue
                where[col_name] = col.type(where[col_name]) if not where[col_name] in [None, 'NULL'] else 'NULL'
                continue
            # Bool column Type
            try:
                where[col_name] = col.type(int(where[col_name])) if table.database.type == 'mysql' else int(col.type(int(where[col_name])))
            except Exception as e:
                #Bool Input is string
                if 'true' in where[col_name].lower():
                    where[col_name] = True if table.database.type == 'mysql' else 1
                elif 'false' in where[col_name].lower():
                    where[col_name] = False if table.database.type == 'mysql' else 0
                else:
                    db.log.error(f"Unsupported value {where[col_name]} provide for column type {col.type}")
                    del(where[col_name])
                    continue
    return where