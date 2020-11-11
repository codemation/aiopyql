import json
from typing import Optional
from aiopyql.cache import Cache
from aiopyql.exceptions import InvalidColumnType, InvalidInputError

class Table:
    def __init__(
        self, 
        name: str, 
        database, 
        columns: list, 
        prim_key: str,
        foreign_keys: dict = None,
        cache_enabled: Optional[bool] = False,
        max_cache_len: Optional[int] = 125
    ):
        self.name = name
        self.database = database
        self.log = self.database.log
        self.types = {int,str,float,bool,bytes}
        self.TRANSLATION = {
            'integer': int,
            'text': str,
            'real': float,
            'boolean': bool,
            'blob': bytes 
        }
        
        self.cache_enabled = cache_enabled
        self.max_cache_len = max_cache_len
        self.cache = None
        if self.cache_enabled:
            self.enable_cache()

        self.columns = {}
        for c in columns:
            if not c.type in self.types:
                raise InvalidColumnType(
                    f"input type: {type(c.type)} of {c}", 
                    f"invalid type provided for column, supported types {self.types}"
                )
            if c.name in self.columns:
                raise InvalidInputError(
                    f"duplicate column name {c.name} provided", 
                    f"column names may only be specified once for table objects"
                )
            self.columns[c.name] = c
        if prim_key is not None:
            self.prim_key = prim_key if prim_key in self.columns else None
        self.foreign_keys = foreign_keys
    def __str__(self):
        return f"{self.database.db_name} {self.name}"
    def enable_cache(self):
        """
        enables cache if cache is None
        does not run if cache exists, should be disabled first via .disable_cache
        """
        if self.cache == None:
            self.cache_enabled = True
            self.cache = Cache(self)
        else:
            self.log.error("enable_cache called while cache exists, first disable & then enable")
    def disable_cache(self, **kw):
        if not self.cache == None:
            self.cache = None
            self.cache_enabled = False
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
    def get_tables_from_input(self, kw):
        tables = [self]
        if 'join' in kw:
            if isinstance(kw['join'], dict):
                for table in kw['join']:
                    if table in self.database.tables:
                        tables.append(self.database.tables[table])
            else:
                if kw['join'] in self.database.tables:
                    tables.append(self.database.tables[kw['join']])
        return tables
    def _process_input(self, kw):
        tables = self.get_tables_from_input(kw)
        kw = self.database._validate_where_input(tables, kw)
        if 'where' in kw:
            kw['where'] = self.database._validate_where_input(tables, kw['where'])
        return kw
    def _validate_table_column(self, col_name, no_raise=False):
        dot_table = False
        if isinstance(col_name, str) and '.' in col_name:
            dot_table = True
            table, column = col_name.split('.')
        else:
            table, column = self.name, col_name
        if ( not column in self.database.tables[table].columns and
            not (no_raise and not dot_table) ):
            raise InvalidInputError(
                f"{column} is not a valid column in table {table}", 
                "invalid column specified for 'where'")
        return table, column
    def __where(self, kw):
        where_sel = ''
        kw = self._process_input(kw)
        if not 'where' in kw:
            return where_sel
        and_value = 'WHERE '

        supported_operators = {'=', '==', '<>', '!=', '>', '>=', '<', '<=', 'like', 'in', 'not in', 'not like'}
        if isinstance(kw['where'], list):
            for condition in kw['where']:
                if not type(condition) in [dict, list]:
                    raise InvalidInputError(
                        f"{condition} is not a valid type within where=[]", 
                        "invalid subcondition type within where=[], expected type(list, dict)"
                        )
                if isinstance(condition, list):
                    if not len(condition) == 3:
                        cond_len = len(condition)
                        raise InvalidInputError(
                            f"{condition} has {cond_len} items, expected 3", 
                            f"{condition} has {cond_len} items, expected 3"
                    )
                    condition1 = f"{condition[0]}"
                    operator = condition[1]
                    condition2 = condition[2]

                    table, column = None, None
                    # expecting comparison operators
                    if not operator in supported_operators:
                        raise InvalidInputError(
                            f"Invalid operator {operator} within {condition}", f"supported operators [{supported_operators}]"
                        )
                    for i, value in enumerate([condition1, condition2]):
                        if i == 0:
                            table, column = self._validate_table_column(value)
                            pass
                        if i == 1 and 'in' in operator:
                            # in operators should be proceeded by a list of values
                            if not isinstance(condition2, list):
                                raise InvalidInputError(
                                    f"Invalid use of operator '{operator}' within {condition}", 
                                    f"'in' should be proceeded by ['list', 'of', 'values'] not {type(condition2)} - {condition2}"
                                )
                            if self.database.tables[table].columns[column].type == str:
                                condition2 = [f"'{cond}'" for cond in condition2]
                            else:
                                condition2 = [str(cond) for cond in condition2]
                            condition2 = ', '.join(condition2)
                            condition2 = f"({condition2})"
                            break
                        if i == 1:
                            self._validate_table_column(value, no_raise=True)
                            """still raises if dot_table used & not in table """
                            pass

                    if 'like' in operator:
                        condition2 = f"{condition2}"
                        if not '*' in condition2:
                            condition2 = f"'%{condition2}%'"
                        else:
                            condition2 = '%'.join(condition2.split('*'))
                            condition2 = f"'{condition2}'"

                    
                    where_sel = f"{where_sel}{and_value}{condition1} {operator} {condition2}"
                if isinstance(condition, dict):
                    for col_name, v in condition.items():
                        table, column = self._validate_table_column(col_name)
                        table = self.database.tables[table]
                        eq = '=' if not v == 'NULL' else ' IS '
                        #json check
                        if v == 'NULL' or table.columns[column].type == str and '{"' and '}' in v:
                            where_sel = f"{where_sel}{and_value}{col_name}{eq}{v}"
                        else:
                            val = v if table.columns[column].type is not str else f"'{v}'"
                            where_sel = f"{where_sel}{and_value}{col_name}{eq}{val}"

                and_value = ' AND '
                    
        if isinstance(kw['where'], dict):
            for col_name, v in kw['where'].items():
                table, column = self._validate_table_column(col_name)
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
                raise InvalidInputError(error, f"valid tables are {list(t for t in self.database.tables)}")
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

    async def select(self, selection, *args,  **kw):
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
        col_select = [selection] + list(args) if not isinstance(selection, list) else selection
        col_select = [i for i in col_select]

        if 'join' in kw and isinstance(kw['join'], str):
            if kw['join'] in [self.foreign_keys[k]['table'] for k in self.foreign_keys]:
                for local_key, foreign_key in self.foreign_keys.items():
                    if foreign_key['table'] == kw['join']:
                        kw['join'] = {
                            foreign_key['table']: {
                                f"{self.name}.{local_key}": f"{foreign_key['table']}.{foreign_key['ref']}"
                            }
                        }
            else:
                error = f"join table {kw['join']} specified without specifying matching columns or tables do not share keys"
                raise InvalidInputError(error, f"valid foreign_keys {self.foreign_keys}")
        cache_new_rows = True
        if '*' in selection:
            selection = '*'
            if 'join' in kw:
                if isinstance(kw['join'], dict):
                    col_refs = {}
                    links = {}
                    keys = []
                    for table in [self.name] + list(kw['join'].keys()):
                        if not table in self.database.tables:
                            raise InvalidInputError(table, f"{table} is not a valid table in {self.database}")
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
            # only cache complete rows using '*'  
            cache_new_rows = False

            col_refs = {}
            keys = []
            for col in col_select: # selection:
                if not col in self.columns:
                    if not '.' in col:
                        raise InvalidColumnType(f"column {col} is not a valid column", f"valid column types {self.columns}")
                    table, column = col.split('.')
                    if table in self.database.tables and column in self.database.tables[table].columns:
                        col_refs[col] = self.database.tables[table].columns[column]
                        keys.append(col)
                        continue
                    
                col_refs[col] = self.columns[col]
                keys.append(col)
            selection = ','.join(col_select)

        # validates where conditions provided and where query
        where_sel = self.__where(kw)

        join = ''
        if 'join' in kw:
            # validate join usage
            join = self._join(kw)

            cache_new_rows = False
        else:
            # join statements cannot return cached rows with 
            # cache check
            if 'where' in kw and isinstance(kw['where'], dict) and self.cache_enabled:
                cached_row = None
                for column, value in kw['where'].items():
                    # primary key used in where statement
                    if column == self.prim_key:
                        # check if value exists in cache
                        if value in self.cache:
                            cached_row = self.cache[value]
                # check cached_row against other where conditions
                # As primary key was used, we know only 1 row should ever 
                # exist so remaining conditions can be safely validated
                if not cached_row == None:
                    for column, value in kw['where'].items():
                        if column == self.prim_key:
                            continue
                        # check cached value against 'where' value
                        if not cached_row[column] == value:
                            # no rows match condition
                            return []
                    # return cache row
                    if '*' in selection:
                        self.log.debug(f"## cache - SELECT * - {cached_row} ##")
                        return [cached_row]
                    else:
                        cached_row = {sel: cached_row[sel] for sel in col_select}
                        self.log.debug(f"## cache - SELECT {col_select} - {cached_row} ##")
                        return [cached_row]

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
        try:
            rows = await self.database.get(query)
        except Exception as e:
            self.log.exception(f"Exception while selecting data in {self.name} ")
            cache_new_rows = False
            rows = []

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
                        self.log.exception(f"error processing results on row {row} index {i} value {v} with {keys}")
                        assert False
                to_return.append(r_dict)
        if cache_new_rows and self.cache_enabled:
            for row in to_return:
                value_to_cache = row[self.prim_key]
                self.cache[value_to_cache] = row
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
        add_to_cache = False
        
        # copy insertion before modification / validation
        insert_values = {}
        insert_values.update(kw)

        kw = self._process_input(kw)
        
        if len(kw) == len(self.columns):
            add_to_cache = True
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
        #self.log.debug(query)
        try:
            result = await self.database.run(query)
            if add_to_cache and self.cache_enabled:
                self.log.debug("## cache add - from insertion ##")
                self.cache[kw[self.prim_key]] = insert_values
                
        except Exception as e:
            self.log.exception(f"exception inserting into {self.name}")
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

    async def modify_cache(self, action, where_kw, updated_data=None):
        """ 
        called for updates  or deletions
            action: 'update'|'delete'
            where_kw: {'where': {'column1': 'value'}}
        """
        if 'where' in where_kw and isinstance(where_kw['where'], dict):
            self.log.debug(f"modify_cache {action} called with {where_kw} and {updated_data}")
            cache_to_modify = {}
            rows_to_check = []
            if self.prim_key in where_kw['where']:
                prim_key = where_kw['where'][self.prim_key]
                if prim_key in self.cache:
                    row = self.cache[prim_key]
                    cache_to_modify[prim_key] = row
                    rows_to_check.append(row)
                    where_kw['where'].pop(self.prim_key)
                else:
                    return
                for column, value in where_kw['where'].items():
                    if not cache_to_modify[prim_key][column] == value:
                        return # No cache to modify matching value
            else: # No Table Primary key used in where_kw['where']
                for column, value in where_kw['where'].items():
                    for cache, row in self.cache:
                        if row[column] == value and not cache in cache_to_modify:
                            rows_to_check.append(row)
                            cache_to_modify[cache] = row
                for column, value in where_kw['where'].items():
                    for row in rows_to_check:
                        if not row[column] == value:
                            cache_to_modify.pop(row[self.prim_key])
            # All cache rows to modify now ready 
            for cache in cache_to_modify:
                if action == 'update':
                    for c, v in updated_data.items():
                        self.cache[cache][c] = v
                        self.log.debug(f"## {self.name} cache updated ##")
                if action == 'delete':
                    del self.cache[cache]
                    self.log.debug(f"## {self.name} cache deleted ##")
    async def update(self, **kw):
        """
        Usage:
            db.tables['stocks'].update(
                symbol='NTAP',
                trans='SELL', 
                where={
                        'order_num': 1
                    }
            )
        """
        where_kw = {'where': {}}
        where_kw['where'].update(kw['where'])

        # creates copy of input set vars for cache
        set_kw = {}
        set_kw.update(kw)
        set_kw.pop('where')

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

        # process where selection for db query
        where_sel = self.__where(kw)

        query = 'UPDATE {name} SET {cols_vals} {where}'.format(
            name=self.name,
            cols_vals=cols_to_set,
            where=where_sel
        )

        try:
            # run db query 
            result = await self.database.run(query)

            # update cache values if enabled
            if self.cache_enabled:
                await self.modify_cache('update', where_kw, set_kw)
            return result
        except Exception as e:
            return self.log.exception(f"Exception updating row for {self.name}")

    async def delete(self, all_rows=False, **kw):
        """
        Usage:
            db.tables['stocks'].delete(where={'order_num': 1})
            db.tables['stocks'].delete(all_rows=True)
        """

        # create a copy of where selection for cache usage
        del_where_sel = {}
        del_where_sel.update(kw)

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
        try:
            result = await self.database.run(query)
            if self.cache_enabled:
                await self.modify_cache('delete', del_where_sel)
            return result
        except Exception as e:
            return self.log.exception(f"Exception deleting row from {self.name}")

    def __get_val_column(self):
        if len(self.columns.keys()) == 2:
            for key in list(self.columns.keys()):
                if not key == self.prim_key:
                    return key

    def __getitem__(self, key_val):
        """
        returns get_key_in_table() coro if event loop is running 
        otherwise executes in new event loop and returns
        """
        async def get_key_in_table():
            val = await self.select('*', where={self.prim_key: key_val})
            if not val == None and len(val) > 0:
                if len(self.columns.keys()) == 2:
                    return val[0][self.__get_val_column()] # returns 
                return val[0]
            return None
        if 'closed=False' in str(self.database.loop):
            self.log.debug(f"__getitem__ called with event loop {self.database.loop}")
            return get_key_in_table()
        else:
            self.log.debug(f"__getitem__ called without event loop - {self.database.loop}")
            val = self.database._run_async_tasks(   
                self.select('*', where={self.prim_key: key_val})
            )
            self.log.debug(f"__getitem__  {val}")
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
                """ UPDATE """
                if not isinstance(values, dict) and len(self.columns.keys()) == 2:
                    return await self.update(**{self.__get_val_column(): values}, where={self.prim_key: key})
                return await self.update(**values, where={self.prim_key: key})
            """ INSERT - value Dictionary"""
            if not isinstance(values, dict) and len(self.columns.keys()) == 2:
                return await self.insert(**{self.prim_key: key, self.__get_val_column(): values})
            #TODO - Not sure if this one is used
            if len(self.columns.keys()) == 2 and isinstance(values, dict) and not self.prim_key in values:
                return await self.insert(**{self.prim_key: key, self.__get_val_column(): values})
            if len(values) == len(self.columns):
                return await self.insert(**values)
        if 'running=True' in str(self.database.loop):
            self.log.debug(f"__getitem__ called with running event loop {self.database.loop}")
            error = "unable to use [] bracket syntax inside a running event loop as __setitem__ is not awaitable,  use tb.insert( tb.update("
            raise NotImplementedError(error)
        return self.database._run_async_tasks(set_item_coro())

    def __contains__(self, key):
        if self[key] == None:
            return False
        return True
    def __iter__(self):
        def gen():
            for row in self.database._run_async_tasks(self.select('*')):
                yield row
        if 'running=True' in str(self.database.loop):
            self.log.debug(f"__iter__ called with running event loop {self.database.loop}")
            error = "unable to use __iter__ in a running event loop,  use async for in <coro> instead"
            raise NotImplementedError(error)
        return gen()
    def __aiter__(self):
        async def gen():
            for row in await self.select('*'):
                yield row
        return gen()