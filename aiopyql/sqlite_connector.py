from collections import deque
from aiosqlite import connect
from aiopyql.utilities import flatten, no_blanks, inner, TableColumn
from aiopyql.exceptions import InvalidColumnType
import json

row_return_type = tuple

TRANSLATION = {
    'integer': int,
    'text': str,
    'real': float,
    'boolean': bool,
    'blob': bytes,
    'varchar': str,
}
def get_table_schema(table):
    constraints = ''
    cols = '('
    for col_name,col in table.columns.items():
        for k,v in TRANSLATION.items():
            if col.type == v:
                if len(cols) > 1:
                    cols = f'{cols}, '
                if col_name == table.prim_key and (k=='text' or k=='blob'):
                    cols = f'{cols}{col.name} VARCHAR(36)'
                else:
                    cols = f'{cols}{col.name} {k.upper()}'
                if col_name == table.prim_key:
                    cols = f'{cols} PRIMARY KEY'
                    if col.mods is not None and 'primary key' in col.mods.lower():
                        cols = f"{cols} {''.join(col.mods.upper().split('PRIMARY KEY'))}"
                    else:
                        cols = f"{cols} {col.mods.upper()}"
                else:
                    if col.mods is not None:
                        cols = f'{cols} {col.mods}'
                break
    if not table.foreign_keys == None:
        for local_key, foreign_key in table.foreign_keys.items():
            comma = ', ' if len(constraints) > 0 else ''
            constraints = f"{constraints}{comma}FOREIGN KEY({local_key}) REFERENCES {foreign_key['table']}({foreign_key['ref']}) {foreign_key['mods']}"
    comma = ', ' if len(constraints) > 0 else ''
    schema = f"CREATE TABLE {table.name} {cols}{comma}{constraints})"
    return schema

def get_db_manager():
    async def sqlite_connect(*args, **kwds):
        async with connect(*args, **kwds) as conn:
            try:
                yield conn
            except Exception as e:
                if conn:
                    await conn.rollback()
            finally:
                pass
    return sqlite_connect


def get_cursor_manager(database):
    """
    returns async generator which manages context of cursor
    or passes db connection, as well as processes db commit
    for changes
    """
    async def sqlite_cursor(commit=False):
        async for db in database.connect(**database.connect_config):
            yield db
            if commit:
                await db.commit()
        return                
    return sqlite_cursor

def show_tables(database):
    pass


async def load_tables(db):
    # query to get list of tables
    tables_in_db_coro = await db.get("select name, sql from sqlite_master where type = 'table'")

    def describe_table_to_col_sqlite(col_config):
        config = []
        for i in ' '.join(col_config.split(',')).split(' '):
            if not i == '' and not i == '\n':
                config.append(i.rstrip())

        field, typ, extra = config[0], config[1], ' '.join(config[2:])
        return TableColumn(
            field, 
            TRANSLATION[typ.lower() if not 'VARCHAR' in typ else 'varchar'], 
            extra)
    table_schemas = await db.get("select name, sql from sqlite_master where type = 'table'")
    for t in table_schemas:
        if 'sqlite' in t[1]:
            continue
        name = t[0]
        schema = t[1]
        config = schema.split(f'CREATE TABLE {name}')[1]
        config = flatten(config)
        col_config = inner(config).split(', ')
        cols_in_table = []
        foreign_keys = None
        for cfg in col_config:
            if not 'FOREIGN KEY' in cfg:
                cols_in_table.append(describe_table_to_col_sqlite(cfg))
            else:
                if foreign_keys == None:
                    foreign_keys = {}
                local_key, ref = cfg.split('FOREIGN KEY')[1].split('REFERENCES')
                local_key = inner(local_key)
                parent_table, mods = ref.split(')')
                parent_table, parent_key = parent_table.split('(')
                foreign_keys[no_blanks(local_key)] = {
                    'table': no_blanks(parent_table), 
                    'ref': no_blanks(parent_key),
                    'mods': mods.rstrip()
                        }
        # Create tables
        primary_key = None
        for col_item in cols_in_table: 
            if 'PRIMARY KEY' in col_item.mods.upper():
                primary_key = col_item.name
        await db.create_table(t[0], cols_in_table, primary_key, foreign_keys=foreign_keys, existing=True)
        if not foreign_keys == None:
            db.foreign_keys = True
            foreign_keys_pre_query = 'PRAGMA foreign_keys=true'
            if not foreign_keys_pre_query in db.pre_query:
                db.pre_query.append(foreign_keys_pre_query)

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
                where[col_name] = int(col.type(int(where[col_name])))
            except Exception as e:
                #Bool Input is string
                if 'true' in where[col_name].lower():
                    where[col_name] = 1
                elif 'false' in where[col_name].lower():
                    where[col_name] = 0
                else:
                    db.log.error(f"Unsupported value {where[col_name]} provide for column type {col.type}")
                    del(where[col_name])
                    continue
    return where

async def process_query_no_commit(db, conn, query_id, query):
    results = []
    async with conn.execute(query) as cursor:
        async for row in cursor:
            results.append(row)
    return results
def process_query_commit(db, conn, conn_id, query_id, query):
    db.querries_to_commit[conn_id].append(
        (query_id, query, conn.execute(query))
    )
async def submit_commit_pool(db, conn, conn_id):
    if len(db.querries_to_commit[conn_id]) > 0:
        db.log.debug(f"queue empty, commiting: {db.querries_to_commit[conn_id]}")
        await db.commit_querries(
            conn,
            db.querries_to_commit[conn_id]
        )
        db.querries_to_commit[conn_id] = deque()