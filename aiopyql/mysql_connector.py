from collections import deque
from aiomysql import create_pool
from aiopyql.utilities import flatten, no_blanks, inner, TableColumn
from aiopyql.exceptions import InvalidColumnType
import json, time

row_return_type = tuple

TRANSLATION = {
    'int': int,
    'double': float,
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
        config = []
        for i in ' '.join(column.split(',')).split(' '):
            if not i == '' and not i == '\n':
                config.append(i.rstrip())
        column = config
        field = inner(column[0], '`','`')
        typ = None
        for k, v in TRANSLATION.items():
            if k in column[1]:
                typ = v
                break
        if typ == None:
            raise InvalidColumnType(column[1], f"invalid type provided for column, supported types {list(TRANSLATION.keys())}")
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
async def process_query_no_commit(db, conn, query_id, query):
    results = []
    db.log.debug(f"{db.db_name} - execute: {query}")
    await conn[0].execute(query)
    result = await conn[0].fetchall()          
    for row in result:
        results.append(row)
    return result
def process_query_commit(db, conn, conn_id, query_id, query):
    db.querries_to_commit[conn_id].append(
        (query_id, query, conn[0].execute(query))
    )

async def submit_commit_pool(db, conn, conn_id):
    if len(db.querries_to_commit[conn_id]) > 0:
        db.log.debug(f"queue empty, commiting: {db.querries_to_commit[conn_id]}")
        await db.commit_querries(
            conn[1],
            db.querries_to_commit[conn_id]
        )
        db.querries_to_commit[conn_id] = deque()


async def migrate_table(db, new_table):
    log = db.log

    def get_dependent_tables(table_name):
        dependent_tables = []
        for table in db.tables:
            if db.tables[table].foreign_keys:
                for f_key, f_config in db.tables[table].foreign_keys.items():
                    log.debug(f"{table} get_dependent_tables: fkey_config: {f_config}")
                    if table_name == f_config['table']:
                        dependent_tables.append(table)
        log.debug(f"## dependent_tables: {dependent_tables}")
        for table in dependent_tables:
            dependent_tables += get_dependent_tables(table)
        return dependent_tables
    dependent_tables = get_dependent_tables(new_table.name)
    log.debug(f"dependent_tables: {dependent_tables}")
    tables_to_migrate = [ new_table.name ] + dependent_tables

    table_copies = {}

    # create copies of table & dependent tables
    for table in tables_to_migrate:
        table_copies[table] = await db.tables[table].select('*')
    
    log.warning(f"migrate table starting on tables {tables_to_migrate} due to '{new_table.name}' schema change")

    backup_name = f"{db.db_name}_backup_{time.time()}"
    log.warning(f"creating backup {backup_name} before migration")

    with open(backup_name, 'w') as backup:
        backup.write(
            json.dumps(table_copies)
        )

    new_table_cols = [col for col in new_table.columns]

    await db.run(
        f'ALTER TABLE {new_table.name} RENAME TO {new_table.name}_old'
    )

    # create new table
    await new_table.create_schema()

    db.tables[new_table.name] = new_table

    try:
        tables_to_migrate.reverse()
        for table in tables_to_migrate:
            if not table == new_table.name:
                await db.run(f'drop table {table}')
                await db.tables[table].create_schema()
        tables_to_migrate.reverse()
        for table in tables_to_migrate:
            for row in table_copies[table]:
                if table == new_table.name:
                    migrated_row = {k: v for k,v in row.items() if k in new_table_cols}
                    await db.tables[table].insert(**migrated_row)
                else:
                    await db.tables[table].insert(**row)

        await db.run(
            f'DROP TABLE {new_table.name}_old'
        )
    except Exception as e:
        log.exception(f"error migrating table {new_table.name} - {repr(e)}")
        raise e