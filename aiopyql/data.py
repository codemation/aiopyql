from contextlib import contextmanager
from collections import namedtuple
import json, re, logging
import asyncio

#Used for grouping columns with database class
TableColumn = namedtuple('col', ['name', 'type', 'mods'])


def get_db_manager(db_connect, db_type):
    """
    returns async generator which manages context
    of the async db connection 
    """
    async def connect(*args, **kwds):
        async with db_connect(*args, **kwds) as conn:
            try:
                yield conn
            except Exception as e:
                try:
                    logging.debug(f'failed to yeild connection with params {kwds} using {db_connect} result {conn} {repr(e)}')
                except Exception:
                    pass
                if conn:
                    await conn.rollback()
            finally:
                return
    return connect
def get_cursor_manager(connect_db, db_type, params={}):
    """
    returns async generator which manages context of cursor
    or passes db connection, as well as processes db commit
    for changes
    """
    async def cursor(commit=False):
        connect_params = params
        async for db in connect_db(**connect_params):
            if db_type == 'sqlite':
                yield db
            if db_type == 'mysql':
                async with db.cursor() as c:
                    try:
                        yield c
                    except Exception as e:
                        print(f"error yielding cursor {repr(e)}")
                    finally:
                        pass
            if commit:
                await db.commit()
        return
                            
    return cursor
def flatten(s):
    return re.sub('\n',' ', s)
def no_blanks(s):
    return re.sub(' ', '', s)
def inner(s, l='(', r=')'):
    if not l in s or not r in s:
        return s
    string_map = [(ind, t) for ind, t in enumerate(s)]
    left, right = False, False
    inside = {}
    for ind, t in string_map:
        if left == False:
            if t == l:
                left = True
                inside['left'] =  ind
            continue
        if right == False:
            if t == r:
                inside['right'] = ind
    return s[inside['left']+1:inside['right']]


class Database:
    """
        Intialize with db connector & name of database. If database exists, it will be used else a new db will be created \n

Sqlite3: Default

        from aiopyql import data

        db = data.Database(
            database="testdb"
            )
    
Mysql

        from aiopyql import data

        db = data.Database(
            database='mysql_database',
            user='mysqluser',
            password='my-secret-pw',
            host='localhost',
            type='mysql'
            )
        
    """
    @classmethod
    async def create(cls, **kw):
        db = Database(**kw)
        await db.load_tables()
        return db
    def __init__(self, **kw):
        #self.loop = asyncio.new_event_loop()
        self.loop = asyncio.get_event_loop() if not 'loop' in kw else kw['loop']
        #self.loop = kw['loop'] if 'loop' in kw else asyncio.new_event_loop()
        self.type = 'sqlite' if not 'type' in kw else kw['type']
        if self.type == 'sqlite':
            import aiosqlite
            self.connect = get_db_manager(aiosqlite.connect, self.type)
        if self.type == 'mysql':
            import aiomysql
            self.connect = get_db_manager(aiomysql.connect, self.type)
        self.debug = 'DEBUG' if 'debug' in kw else None
        self.log = kw['logger'] if 'logger' in kw else None
        self.setup_logger(self.log, level=self.debug)
        self.connect_params =  ['user', 'password', 'database', 'db', 'host', 'port']
        self.connect_config = {}
        for k,v in kw.items():
            if k in self.connect_params:
                self.connect_config[k] = v if not k == 'port' else int(v)     
        if not 'database' in kw:
            if not 'db' in kw:
                raise InvalidInputError(kw, "missing field for 'database' or 'db' ")
        self.db_name = kw['database'] if 'database' in kw else kw['db']
        self.cursor = get_cursor_manager(self.connect, self.type, params = self.connect_config)
        if self.type == 'sqlite':
            self.foreign_keys = False
        self.pre_query = [] # SQL commands Ran before each for self.get self.run query 
        self.tables = {}
        if 'loop' in kw:
            self._run_async_tasks(
                self.load_tables()
            )
    def _run_async_tasks(self, *args):
        return self.loop.run_until_complete(asyncio.gather(*args))

    def __contains__(self, table):
        if self.type == 'sqlite':
            tables_in_db_coro = self.get("select name, sql from sqlite_master where type = 'table'")
        else:
            tables_in_db_coro = self.get("show tables")
        tables_in_db_result = self._run_async_tasks(tables_in_db_coro)[0]
        print(f"tables_in_db_result: {tables_in_db_result}")
        if len(tables_in_db_result) == 0:
            return False
        return table in [i[0] for i in tables_in_db_result]
    def setup_logger(self, logger=None, level=None):
        if logger == None:
            level = logging.DEBUG if level == 'DEBUG' else logging.ERROR
            logging.basicConfig(
                        level=level,
                        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                        datefmt='%m-%d %H:%M'
            )
            self.log = logging.getLogger()
            self.log.setLevel(level)
        else:
            self.log = logger
    async def execute(self, query, commit=False):
        results = []
        query = f"{';'.join(self.pre_query + [query])}"
        query = query.split(';') if ';' in query else [query]
        async for conn in self.cursor(commit=commit):
            for q in query:
                if self.type == 'sqlite':
                    try:
                        async with conn.execute(q) as cursor:
                            async for row in cursor:
                                results.append(row)
                    except Exception as e:
                        results.append(repr(e))
                if self.type == 'mysql':
                    # MYSQL conn should be iterated over for results
                    await conn.execute(q)
                    async for row in conn:
                        results.append(row)
        return results
            
    async def run(self, query):
        """
        Run query with commit
        """
        return await self.execute(query, commit=True)
    async def get(self, query, commit=False):
        """
        Run query with optional commit. Typically used for select query. 
        Default:
            commit=False
        """
        return await self.execute(query, commit=False)
    async def load_tables(self):
        if self.type == 'sqlite':
            tables_in_db_coro = await self.get("select name, sql from sqlite_master where type = 'table'")
        else:
            tables_in_db_coro = await self.get("show tables")
        if self.type == 'sqlite':
            def describe_table_to_col_sqlite(col_config):
                config = []
                for i in ' '.join(col_config.split(',')).split(' '):
                    if not i == '' and not i == '\n':
                        config.append(i.rstrip())
                TYPE_TRANSLATE = {
                    'varchar': str,
                    'integer': int,
                    'text': str,
                    'real': float,
                    'boolean': bool,
                    'blob': bytes 
                }
                field, typ, extra = config[0], config[1], ' '.join(config[2:])
                return TableColumn(
                    field, 
                    TYPE_TRANSLATE[typ.lower() if not 'VARCHAR' in typ else 'varchar'], 
                    extra)
            table_schemas = await self.get("select name, sql from sqlite_master where type = 'table'")
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
                await self.create_table(t[0], cols_in_table, primary_key, foreign_keys=foreign_keys, existing=True)
                if not foreign_keys == None:
                    self.foreign_keys = True
                    foreign_keys_pre_query = 'PRAGMA foreign_keys=true'
                    if not foreign_keys_pre_query in self.pre_query:
                        self.pre_query.append(foreign_keys_pre_query)


        if self.type == 'mysql':
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
                table_schemas = await self.get(f'show create table {table}')
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
                await self.create_table(table, cols_in_table, primary_key, foreign_keys=foreign_keys, existing=True)
    async def create_table(self, name, columns, prim_key=None, **kw):
        """
        Usage:
            db.create_table(
                'stocks_new_tb2', 
                [
                    ('order_num', int, 'AUTOINCREMENT'),
                    ('date', str, None),
                    ('trans', str, None),
                    ('symbol', str, None),
                    ('qty', float, None),
                    ('price', str, None)
                    ], 
                'order_num', # Primary Key
                foreign_keys={'trans': {'table': 'transactions', 'ref': 'txId'}} 
            )
        """
        #Convert tuple columns -> named_tuples
        cols = []
        for c in columns:
            # Allows for len(2) tuple input ('name', int) --> converts to TableColumn('name', int, None)
            if not isinstance(c, TableColumn):
                cols.append(TableColumn(*c) if len(c) > 2 else TableColumn(*c, ''))
            else:
                cols.append(c)
        self.tables[name] = Table(name, self, cols, prim_key, **kw)
        if not 'existing' in kw:
            await self.tables[name].create_schema()
        return f"table {name} created"
        


class Table:
    def __init__(self, name, database, columns, prim_key = None, **kw):
        self.name = name
        self.database = database
        self.types = {int,str,float,bool,bytes}
        self.TRANSLATION = {
            'integer': int,
            'text': str,
            'real': float,
            'boolean': bool,
            'blob': bytes 
        }
        self.columns = {}
        for c in columns:
            if not c.type in self.types:
                raise InvalidColumnType(f"input type: {type(c.type)} of {c}", f"invalid type provided for column, supported types {self.types}")
            if c.name in self.columns:
                raise InvalidInputError(f"duplicate column name {c.name} provided", f"column names may only be specified once for table objects")
            self.columns[c.name] = c
        if prim_key is not None:
            self.prim_key = prim_key if prim_key in self.columns else None
        self.foreign_keys = kw['foreign_keys'] if 'foreign_keys' in kw else None
            
        #self.create_schema()
    def get_schema(self):
        constraints = ''
        cols = '('
        for col_name,col in self.columns.items():
            for k,v in self.TRANSLATION.items():
                if col.type == v:
                    if len(cols) > 1:
                        cols = f'{cols}, '
                    if col_name == self.prim_key and (k=='text' or k=='blob'):
                        cols = f'{cols}{col.name} VARCHAR(36)'
                    else:
                        cols = f'{cols}{col.name} {k.upper()}'
                    if col_name == self.prim_key:
                        cols = f'{cols} PRIMARY KEY'
                        if col.mods is not None and 'primary key' in col.mods.lower():
                            cols = f"{cols} {''.join(col.mods.upper().split('PRIMARY KEY'))}"
                        else:
                            cols = f"{cols} {col.mods.upper()}"
                    else:
                        if col.mods is not None:
                            cols = f'{cols} {col.mods}'
        if not self.foreign_keys == None:
            for local_key, foreign_key in self.foreign_keys.items():
                comma = ', ' if len(constraints) > 0 else ''
                constraints = f"{constraints}{comma}FOREIGN KEY({local_key}) REFERENCES {foreign_key['table']}({foreign_key['ref']}) {foreign_key['mods']}"
        comma = ', ' if len(constraints) > 0 else ''
        schema = f"CREATE TABLE {self.name} {cols}{comma}{constraints})"
        return schema
    async def create_schema(self):
        return await self.database.run(self.get_schema())
    def _process_input(self, kw):
        tables = [self]
        if 'join' in kw:
            if isinstance(kw['join'], dict):
                for table in kw['join']:
                    if table in self.database.tables:
                        tables.append(self.database.tables[table])
            else:
                if kw['join'] in self.database.tables:
                    tables.append(self.database.tables[kw['join']])
        def verify_input(where):
            for table in tables:
                for col_name, col in table.columns.items():
                    if col_name in where:
                        if not col.type == bool:
                            #JSON handling
                            if col.type == str and type(where[col_name]) == dict:
                                where[col_name] = f"'{col.type(json.dumps(where[col_name]))}'"
                                continue
                            where[col_name] = col.type(where[col_name]) if not where[col_name] == None else 'NULL'
                        else:
                            try:
                                where[col_name] = col.type(int(where[col_name])) if table.database.type == 'mysql' else int(col.type(int(where[col_name])))
                            except:
                                #Bool Input is string
                                if 'true' in where[col_name].lower():
                                    where[col_name] = True if table.database.type == 'mysql' else 1
                                elif 'false' in where[col_name].lower():
                                    where[col_name] = False if table.database.type == 'mysql' else 0
                                else:
                                    self.database.log.warning(f"Unsupported value {where[col_name]} provide for column type {col.type}")
                                    del(where[col_name])
                                    continue
            return where
        kw = verify_input(kw)
        if 'where' in kw:
            kw['where'] = verify_input(kw['where'])
        return kw

    def __where(self, kw):
        where_sel = ''
        index = 0
        kw = self._process_input(kw)
        if 'where' in kw:
            and_value = 'WHERE '
            for col_name,v in kw['where'].items():
                if '.' in col_name:
                    table, column = col_name.split('.')
                else:
                    table, column = self.name, col_name
                if not column in self.database.tables[table].columns:
                    raise InvalidInputError(f"{column} is not a valid column in table {table}", "invalid column specified for 'where'")
                table = self.database.tables[table]
                eq = '=' if not v == 'NULL' else ' IS '
                #json check
                if v == 'NULL' or table.columns[column].type == str and '{"' and '}' in v:
                    where_sel = f"{where_sel}{and_value}{col_name}{eq}{v}"
                else:
                    val = v if table.columns[column].type is not str else f"'{v}'"
                    where_sel = f"{where_sel}{and_value}{col_name}{eq}{val}"
                and_value = ' AND '
        return where_sel
    def _join(self, kw):
        join = ''
        if not 'join' in kw:
            return join
        for join_table, condition in kw['join'].items():
            if not join_table in self.database.tables:
                error = f"{join_table} does not exist in database"
                raise InvalidInputError(error, f"valid tables {list(t for t in self.database.tables)}")
            count = 0
            for col1, col2 in condition.items():
                for col in [col1, col2]:
                    if not '.' in col:
                        usage = "join usage: join={'table1': {'table1.col': 'this.col'} } or  join={'table1': {'this.col': 'table1.col'} }"
                        raise InvalidInputError(f"column {col} missing expected '.'", usage)
                    table, column = col.split('.')
                    if not table in self.database.tables:
                        error = f"table {table} does not exist in database"
                        raise InvalidInputError(error, f"valid tables {list(t for t in self.database.tables)}")
                    if not column in self.database.tables[table].columns:
                        error = f"column {column} is not a valid column in table {table}"
                        raise InvalidColumnType(error, f"valid column types {self.database.tables[table].columns}")
                join_and = ' AND ' if count > 0 else f'JOIN {join_table} ON'
                join = f'{join}{join_and} {col1} = {col2} '
                count+=1
        return join

    async def select(self, *selection, **kw):
        """
        Usage: returns list of dictionaries for each selection in each row. 
            tb = db.tables['stocks_new_tb2']

            sel = tb.select('order_num',
                            'symbol', 
                            where={'trans': 'BUY', 'qty': 100})
            sel = tb.select('*')
            # Iterate through table
            sel = [row for row in tb]
            # Using Primary key only
            sel = tb[0] # select * from <table> where <table_prim_key> = <val>
        """


        if 'join' in kw and isinstance(kw['join'], str):
            if kw['join'] in [self.foreign_keys[k]['table'] for k in self.foreign_keys]:
                for local_key, foreign_key in self.foreign_keys.items():
                    if foreign_key['table'] == kw['join']:
                        kw['join'] = {
                            foreign_key['table']: {
                                f"{self.name}.{local_key}": f"{foreign_key['table']}.{foreign_key['ref']}"}
                                }
            else:
                error = f"join table {kw['join']} specified without specifying matching columns or tables do not share keys"
                raise InvalidInputError(error, f"valid foreign_keys {self.foreign_keys}")
        if '*' in selection:
            selection = '*'
            if 'join' in kw:
                if isinstance(kw['join'], dict):
                    col_refs = {}
                    links = {}
                    keys = []
                    for table in [self.name] + list(kw['join'].keys()):
                        if table in self.database.tables:
                            for col in self.database.tables[table].columns:
                                column = self.database.tables[table].columns[col]
                                if table in kw['join']:
                                    cont = False
                                    for col1, col2 in kw['join'][table].items():
                                        if f'{table}.{col}' == f'{col2}':
                                            cont = True
                                            if col1 in links:
                                                keys.append(links[col1])
                                                links[col2] = links[col1]
                                                break
                                            links[col2] = col1
                                            keys.append(col1)
                                            break
                                    if cont:
                                        continue
                                col_refs[f'{table}.{column.name}'] =  column
                                keys.append(f'{table}.{column.name}')
            else:
                col_refs = self.columns
                keys = list(self.columns.keys())
        else:
            col_refs = {}
            keys = []
            for col in selection:
                if not col in self.columns:
                    if '.' in col:
                        table, column = col.split('.')
                        if table in self.database.tables and column in self.database.tables[table].columns:
                            col_refs[col] = self.database.tables[table].columns[column]
                            keys.append(col)
                            continue
                    raise InvalidColumnType(f"column {col} is not a valid column", f"valid column types {self.columns}")
                col_refs[col] = self.columns[col]
                keys.append(col)
            selection = ','.join(selection)
        join = ''
        if 'join' in kw:
            join = self._join(kw)        
        where_sel = self.__where(kw)
        orderby = ''
        if 'orderby' in kw:
            if not kw['orderby'] in self.columns:
                raise InvalidInputError(f"orderby input {kw['orderby']} is not a valid column name", f"valid columns {self.columns}")
            orderby = ' ORDER BY '+ kw['orderby']
        query = 'SELECT {select_item} FROM {name} {join}{where}{order}'.format(
            select_item = selection,
            name = self.name,
            join=join,
            where = where_sel,
            order = orderby
        )
        rows = await self.database.get(query)

        #dictonarify each row result and return
        to_return = []
        if not rows == None:
            for row in rows:
                r_dict = {}
                for i,v in enumerate(row):
                    try:
                        if not v == None and col_refs[keys[i]].type == str and '{"' and '}' in v:
                                r_dict[keys[i]] = json.loads(v)
                        else:
                            r_dict[keys[i]] = v if not col_refs[keys[i]].type == bool else bool(v)
                    except Exception as e:
                        self.database.log.exception(f"error processing results on row {row} index {i} value {v} with {keys}")
                        assert False
                to_return.append(r_dict)
        return to_return
    async def insert(self, **kw):
        """
        Usage:
            db.tables['stocks_new_tb2'].insert(
                date='2006-01-05',
                trans={
                    'type': 'BUY', 
                    'conditions': {'limit': '36.00', 'time': 'EndOfTradingDay'}, #JSON
                'tradeTimes':['16:30:00.00','16:30:01.00']}, # JSON
                symbol='RHAT', 
                qty=100.0,
                price=35.14)
        """
        cols = '('
        vals = '('
        #checking input kw's for correct value types

        kw = self._process_input(kw)

        for col_name, col in self.columns.items():
            if not col_name in kw:
                if not col.mods == None:
                    if 'NOT NULL' in col.mods and not 'INCREMENT' in col.mods:
                        raise InvalidInputError(f'{col_name} is a required field for INSERT in table {self.name}', "correct and try again")
                continue
            if len(cols) > 2:
                cols = f'{cols}, '
                vals = f'{vals}, '
            cols = f'{cols}{col_name}'
            #json handling
            if kw[col_name]== 'NULL' or kw[col_name] == None or col.type == str and '{"' and '}' in kw[col_name]:
                new_val = kw[col_name]
            else:
                new_val = kw[col_name] if col.type is not str else f'"{kw[col_name]}"'
            vals = f'{vals}{new_val}'

        cols = cols + ')'
        vals = vals + ')'

        query = f'INSERT INTO {self.name} {cols} VALUES {vals}'
        self.database.log.debug(query)
        return await self.database.run(query)
    async def set_item(self, key, values):
        async def set_item_coro():
            if not await self[key] == None:
                if not isinstance(values, dict) and len(self.columns.keys()) == 2:
                    return await self.update(**{self.__get_val_column(): values}, where={self.prim_key: key})
                return await self.update(**values, where={self.prim_key: key})
            if not isinstance(values, dict) and len(self.columns.keys()) == 2:
                return await self.insert(**{self.prim_key: key, self.__get_val_column(): values})
            if len(self.columns.keys()) == 2 and isinstance(values, dict) and not self.prim_key in values:
                return await self.insert(**{self.prim_key: key, self.__get_val_column(): values})
            if len(values) == len(self.columns):
                return await self.insert(**values)
        return await set_item_coro()
    async def update(self,**kw):
        """
        Usage:
            db.tables['stocks'].update(symbol='NTAP',trans='SELL', where={'order_num': 1})
        """
        
        kw = self._process_input(kw)

        cols_to_set = ''
        for col_name, col_val in kw.items():
            if col_name.lower() == 'where':
                continue
            if len(cols_to_set) > 1:
                cols_to_set = f'{cols_to_set}, '
            #JSON detection
            if col_val == 'NULL' or self.columns[col_name].type == str and '{"' and '}' in col_val:
                column_value = col_val
            else:
                column_value = col_val if self.columns[col_name].type is not str else f"'{col_val}'"
            cols_to_set = f'{cols_to_set}{col_name} = {column_value}'

        where_sel = self.__where(kw)
        query = 'UPDATE {name} SET {cols_vals} {where}'.format(
            name=self.name,
            cols_vals=cols_to_set,
            where=where_sel
        )
        self.database.log.debug(query)
        return await self.database.run(query)
    async def delete(self, all_rows=False, **kw):
        """
        Usage:
            db.tables['stocks'].delete(where={'order_num': 1})
            db.tables['stocks'].delete(all_rows=True)
        """
        try:
            where_sel = self.__where(kw)
        except Exception as e:
            return repr(e)
        if len(where_sel) < 1 and not all_rows:
            error = "where statment is required with DELETE, otherwise specify .delete(all_rows=True)"
            raise InvalidInputError(error, "correct & try again later")
        query = "DELETE FROM {name} {where}".format(
            name=self.name,
            where=where_sel
        )
        return await self.database.run(query)
    def __get_val_column(self):
        if len(self.columns.keys()) == 2:
            for key in list(self.columns.keys()):
                if not key == self.prim_key:
                    return key

    def __getitem__(self, key_val):
        """
        returns is_key_in_table() coro if event loop is running 
        otherwise executes in new event loop and returns
        """
        async def is_key_in_table():
            val = await self.select('*', where={self.prim_key: key_val})
            if not val == None and len(val) > 0:
                if len(self.columns.keys()) == 2:
                    return val[0][self.__get_val_column()] # returns 
                return val[0]
            return None
        if 'running=True' in str(self.database.loop):
            self.database.log.debug(f"__getitem__ called with running event loop {self.database.loop}")
            return is_key_in_table()
        else:
            #self.database.log.debug(f"__getitem__ - {self.database.loop}")
            val = self.database._run_async_tasks(
                self.select('*', where={self.prim_key: key_val})
            )[0]
            self.database.log.debug(f"__getitem__  {val}")
            if not val == None and len(val) > 0:
                if len(self.columns.keys()) == 2:
                    return val[0][self.__get_val_column()] # returns 
                return val[0]
            return None

    def __setitem__(self, key, values):
        """
        returns set_item() coro if event loop is running 
        otherwise executes in new event loop and returns
        """
        async def set_item_coro():
            if not await self[key] == None:
                if not isinstance(values, dict) and len(self.columns.keys()) == 2:
                    return await self.update(**{self.__get_val_column(): values}, where={self.prim_key: key})
                return await self.update(**values, where={self.prim_key: key})
            if not isinstance(values, dict) and len(self.columns.keys()) == 2:
                return await self.insert(**{self.prim_key: key, self.__get_val_column(): values})
            if len(self.columns.keys()) == 2 and isinstance(values, dict) and not self.prim_key in values:
                return await self.insert(**{self.prim_key: key, self.__get_val_column(): values})
            if len(values) == len(self.columns):
                return await self.insert(**values)
        if 'running=True' in str(self.database.loop):
            self.database.log.debug(f"__getitem__ called with running event loop {self.database.loop}")
            error = "unable to use [] bracket syntax inside a running event loop as __setitem__ is not awaitable,  use tb.insert( tb.update("
            raise NotImplementedError(error)
        return self.database._run_async_tasks(set_item_coro())[0]

    def __contains__(self, key):
        if self[key] == None:
            return False
        return True
    def __iter__(self):
        def gen():
            for row in self.databse._run_async_tasks(self.select('*'))[0]:
                yield row
        if 'running=True' in str(self.database.loop):
            self.database.log.debug(f"__iter__ called with running event loop {self.database.loop}")
            error = "unable to use __iter__ in a running event loop,  use async for in <coro> instead"
            raise NotImplementedError(error)
        return gen()
    def __aiter__(self):
        async def gen():
            for row in await self.select('*'):
                yield row
        return gen()
class Error(Exception):
    pass
class InvalidInputError(Error):
    def __init__(self, invalid_input, message):
        self.invalid_input = invalid_input
        self.message = message
class InvalidColumnType(Error):
    def __init__(self, invalid_type, message):
        self.invalid_type = invalid_type
        self.message = message
#   TOODOO:
# - Add support for creating column indexes per tables
# - Determine if views are needed and add support
# - Support for transactions?