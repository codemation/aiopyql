import logging 
import uuid, time
import asyncio
from typing import (
    Optional
)
from collections import deque
from concurrent.futures._base import CancelledError
from asyncio import InvalidStateError

from aiopyql.utilities import TableColumn
from aiopyql.cache import Cache
from aiopyql.table import Table

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
    async def create(cls, 
        database: str,
        db_type: str = 'sqlite',
        cache_enabled: Optional[bool] = False,
        max_cache_len: Optional[int] = 125,
        debug: Optional[bool] = False,
        log: Optional[logging.Logger] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
        **kw
    ):

        db = Database(
            database=database,
            db_type=db_type,
            cache_enabled=cache_enabled,
            max_cache_len=max_cache_len,
            debug=debug,
            log=log,
            loop=loop,
            **kw
        )
        await db.load_tables(db)
        return db
    def __init__(
        self, 
        database: str,
        db_type: str = 'sqlite',
        cache_enabled: Optional[bool] = False,
        max_cache_len: Optional[int] = 125,
        debug: Optional[bool] = False,
        log: Optional[logging.Logger] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
        **kw
    ):
        self.db_name = database
        self.loop = asyncio.get_running_loop() if not loop else loop
        # 
        self.type = db_type
        self.log = log
        self.debug = debug

        # param check
        self.setup_parameter_check(kw)

        # logger 
        self.setup_logger(logger=self.log, level='DEBUG' if self.debug else 'ERROR')

        # connection & cursor setup
        self.setup_connection_and_cursor()

        #if self.type == 'sqlite':
        #    self.foreign_keys = False
        self.pre_query = [] # SQL commands Ran before each for self.get self.run query 
        self.tables = {}

        # cache
        self.cache_enabled = cache_enabled
        self.max_cache_len = max_cache_len
        self.cache = None
        if self.cache_enabled:
            self.enable_cache()

        # query queue
        self._query_queue = asyncio.Queue()
        self.querries_to_commit = {}

        self.queue_process_tasks = []
        self.queue_results = {"pending": {}, "finished": {}}
        self.MAX_QUEUE_PROCESS = 100

        self.queue_processing = set()
        self.MAX_QUEUE_PROCESSORS = 1
        for _ in range(self.MAX_QUEUE_PROCESSORS):
            self.queue_process_tasks.append(self.loop.create_task(self.__process_queue()))

        self.liveness = self.loop.create_task(self.keep_alive())
    async def keep_alive(self):
        """
        periodic check for db connection live-ness 
        """
        try:
            if 'liveness' in self.tables:
                await self.run('drop table liveness')
        except Exception as e:
            pass

        await self.create_table(
            'liveness',
            columns=[
                ('timestamp_utc', str),
                ('status', str)
            ],
            prim_key='timestamp_utc',
            cache_enabled=True
        )
        last_timestamp = str(time.time())

        while True:
            try:
                timestamp = await self.tables['liveness'].select(
                    '*', where={'timestamp_utc': last_timestamp})

                if not timestamp:
                    await self.tables['liveness'].insert(
                        timestamp_utc=last_timestamp
                    )
                await asyncio.sleep(30)
                new_timestamp = str(time.time())
                await self.tables['liveness'].update(
                    timestamp_utc=new_timestamp,
                    where={'timestamp_utc': last_timestamp}
                )
                last_timestamp = new_timestamp
                timestamp = await self.tables['liveness'].select(
                    '*', where={'timestamp_utc': last_timestamp})
                self.log.warning(f"liveness timestamp: {timestamp}")
                
                timestamp = timestamp[0]['timestamp_utc']
                self.log.warning(f'liveness check completed - {timestamp} - last_timestamp: {last_timestamp}')
                if timestamp == last_timestamp:
                    continue
            except Exception as e:
                if not type(e) in {InvalidStateError, CancelledError}:
                    self.log.exception(f"error in liveness check - closing & restarting")
                    await self.close(liveness=False)
                    self.queue_process_tasks = []
                    await self.restart_queue_processor()
                    continue
                # exiting
                break

    async def restart_queue_processor(self):
        await asyncio.sleep(1)
        self.queue_processing = set()
        self.log.warning(f"restart_queue_processor called: current {self.queue_processing}")
        self.setup_connection_and_cursor()

        if len(self.queue_processing) < self.MAX_QUEUE_PROCESSORS:
            for _ in range(self.MAX_QUEUE_PROCESSORS):
                self.queue_process_tasks.append(self.loop.create_task(self.__process_queue()))

            

    def setup_parameter_check(self, params):
        self.connect_params =  {'user', 'password', 'host', 'port'}

        db_key = 'db' if self.type == 'mysql' else 'database'
        self.connect_config = {db_key: self.db_name}
        for k,v in params.items():
            if k in self.connect_params:
                if k == 'db':
                    continue
                self.connect_config[k] = v if not k == 'port' else int(v)
    def setup_connection_and_cursor(self):
        """
        based on database type, setup connection / cursor for database
        """
        if self.type == 'mysql':
            import aiopyql.mysql_connector as connector 
        if self.type == 'sqlite':
            import aiopyql.sqlite_connector as connector
        if self.type == 'postgres':
            import aiopyql.postgres_connector as connector

        self.connect = connector.get_db_manager()
        self.cursor = connector.get_cursor_manager(self)
        self.load_tables = connector.load_tables
        self.row_return_type = connector.row_return_type
        self.get_table_schema = connector.get_table_schema
        self.migrate_table = connector.migrate_table

        self.process_query_commit = connector.process_query_commit
        self.process_query_no_commit = connector.process_query_no_commit
        self.submit_commit_pool = connector.submit_commit_pool

        def db_validate_where_input(tables, where):
            return connector.validate_where_input(self, tables, where)
        self._validate_where_input = db_validate_where_input

    async def close(self, liveness=True):
        """
        stops running running process task
        """
        for task in self.queue_process_tasks:
            task.cancel()
        await self._query_queue.put(('EXITING', None))
        await asyncio.sleep(0.1)
        self.log.debug(f"{self.db_name} closed successfully")
        if liveness:
            self.liveness.cancel()
            await asyncio.sleep(0.1)
    def __str__(self):
        return self.db_name
    def enable_cache(self):
        """
        enables cache if cache is None
        does not run if cache exists, should be disabled first via .disable_cache
        """
        if self.cache == None:
            self.cache_enabled = True
            self.cache = Cache(self)
        else:
            self.log.warning("enable_cache called while cache exists, first disable & then enable")
    def disable_cache(self):
        if not self.cache == None:
            self.cache = None
            self.cache_enabled = False
    def _run_async_tasks(self, *args):
        if not self.loop == None:
            raise NotImplementedError(f"_run_async_tasks method not allowed with an existing event loop {self.loop}")
        self.loop = asyncio.get_event_loop()
        if len(args) > 1:
            result = self.loop.run_until_complete(asyncio.gather(*args))
        else:
            result = asyncio.get_event_loop().run_until_complete(*args)
        self.loop = None
        return result

    def setup_logger(self, logger=None, level=None):
        if logger is None:
            level = logging.DEBUG if level == 'DEBUG' else logging.ERROR
            logging.basicConfig(
                level=level,
                format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                datefmt='%m-%d %H:%M'
            )
            self.log = logging.getLogger(f'aiopyql-db-{self.db_name}')
            self.log.propogate = False
            self.log.setLevel(level)
        else:
            self.log = logger
    def cache_check(self, query):
        """
        checks 
        """
        if 'SELECT' in query:
            return
        # non - select

        cache_to_clear = set()
        table_in_query = None
        for table in self.tables:
            if (f"UPDATE {table}" in query or 
                f"INTO {table}" in query or
                f"FROM {table}" in query
                ):
                table_in_query = table
        for cache, _ in self.cache:
            if f"JOIN {table_in_query}" in cache or f'FROM {table_in_query}' in cache:
                cache_to_clear.add(cache)
        for cache in cache_to_clear:
            self.log.debug(f"## db cache deleted - query {cache}")
            del self.cache[cache]
    async def __commit_querries_run_query(self, query):
        """
        a coro which unpacks query id, query, and pending coroutine, 
        executes and marks query complete by updating 
        self.queue_results[query_id]
        """
        try:
            query_id, q, q_coro = query 
            self.log.debug(f"{self.db_name} - execute: {q}")
            await q_coro
            await self.queue_results[query_id].put([])
        except Exception as e:
            self.log.exception(f"error running query: {query}")
            results = e
            await self.queue_results[query_id].put(results)

    async def commit_querries(self, connection, querries):
        self.log.debug(f"commit_querries started for {querries}")
        start = time.time()
        run_querries = []

        try:
            #while len(querries) > 0:
            while True:
                run_querries.append(
                    self.__commit_querries_run_query(querries.popleft())
            )
        except IndexError:
            pass
        except Exception as e:
            self.log.exception(f"exception while building commit query pool")

        if not self.type == 'sqlite':
            for run_q in run_querries:
                await run_q
        else:
            await asyncio.gather(*run_querries, return_exceptions=True)
        if not self.type == 'postgres':
            await connection.commit()
        self.log.debug(f"commit_querries of {len(querries)} completed in {time.time() - start} seconds")

    async def __process_queue(self, commit=True):
        try:
            last_exception = None
            async for conn in self.cursor(commit=commit):
                self.log.debug(f"__process_queue conn: {conn}")
                if self.pre_query:
                    await conn.execute(self.pre_query)
                conn_id = str(uuid.uuid1())
                self.queue_processing.add(conn_id)
                self.querries_to_commit[conn_id] = deque()
                last_commit = time.time()
                queue_empty = True
                try:
                    while True:
                        try:
                            if queue_empty:
                                self.log.debug("queue_empty waiting for new query")
                                query_id, query = await self._query_queue.get()
                                self.log.debug(f"received new query: {query}")
                                queue_empty = False
                            else:
                                query_id, query = self._query_queue.get_nowait()
                            if query_id == 'EXITING':
                                self.log.debug(f"__process_queue received exiting signal")
                                break

                            query_commit = not (
                                'SELECT' in query
                                or 'select' in query
                                or 'show ' in query
                                )

                            query_start = time.time()
                        except asyncio.queues.QueueEmpty:
                            await self.submit_commit_pool(self, conn, conn_id)
                            last_commit = time.time()
                            queue_empty = True
                            continue       
                        except Exception as e:
                            if not isinstance(e, CancelledError):
                                self.log.exception(f"error waiting / preparing query")
                            last_exception = e
                            break

                        if not query_commit or time.time() - last_commit > 0.02:
                            await self.submit_commit_pool(self, conn, conn_id)
                            last_commit = time.time()
                        results = []
                        try:
                            #for q in query:
                            if not query_commit:
                                results = await self.process_query_no_commit(self, conn, query_id, query)
                            else:
                                self.process_query_commit(self, conn, conn_id, query_id, query)
                        except Exception as e:
                            self.log.exception(f"error running query: {query}")
                            results = e
                        if not query_commit:
                            await self.queue_results[query_id].put(results)
                        if 'Broken pipe' in f"{results}":
                            last_exception = results
                            raise last_exception
                except Exception as e:
                    if not isinstance(e, CancelledError):
                        self.log.exception(f"error in __process_queue, closing db connection")
                # process last queued
                await self.submit_commit_pool(self, conn, conn_id)
                self.log.debug(f"closing cursor connecting")
            self.log.debug(f"closed cursor connection")                             
        except Exception as e:
            if not e in {InvalidStateError, CancelledError}:
                self.log.exception(f"error during __process_queue")
                if 'Broken pipe' in repr(e):
                    last_exception = e

        # un-locks processing so new processing tasks can start
        self.queue_processing  = set()
        self.log.debug(f"completed processing items in queue - {last_exception}")
        if not last_exception in {InvalidStateError, CancelledError}:
            self.log.debug(f"completed processing items in queue - restarting")
            await self.restart_queue_processor()
        return "completed processing items in queue"

    async def execute(self, query, commit=False):
        self.log.debug(f"execute - {query}")
        query_id = str(uuid.uuid1())
        self.queue_results[query_id] = asyncio.Queue(1)

        await self._query_queue.put((query_id, query))
        try:
            result = await self.queue_results[query_id].get()
        except Exception as e:
            self.log.exception(f"error while executing query {query}")
            result = e
        self.log.debug(f"completed query: {query_id}")
        del self.queue_results[query_id]
        if isinstance(result, Exception):
            raise result
        return result
            
    async def run(self, query):
        """
        Run query with commit
        """
        if self.cache_enabled:
            self.cache_check(query)
        result = await self.execute(query, commit=True)
        if self.cache_enabled:
            self.cache_check(query)
        return result

    async def get(self, query, commit=False):
        """
        Run query with optional commit. Typically used for select query. 
        Default:
            commit=False
        """
        if self.cache_enabled:
            self.cache_check(query)
            if query in self.cache:
                self.log.debug(f"## db cache used - query {query}")
                result = self.cache[query]
                if not result == None and len(result) > 0:
                    return result
        result = await self.execute(query, commit=False)
        if self.cache_enabled:
            self.log.debug(f"## db cache added - query {query}")
            self.cache[query] = result
        return result
    async def remove_table(
        self,
        name: str,
        drop_table: bool = True
    ):
        if drop_table:
            try:
                await self.run(f'drop table {name}')
            except Exception as e:
                self.log.exception(f"error removing table {name} from database")
        if name in self.tables:
            del self.tables[name]
            self.log.warning(f"table {name} removed")

    async def create_table(
        self, 
        name: str, 
        columns: list, 
        prim_key: str,
        foreign_keys: dict = None,
        cache_enabled: Optional[bool] = False,
        max_cache_len: Optional[int] = 125,
        **kw
    ):
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

        str_to_type = {'str': str, 'int': int, 'bytes': bytes, 'float': float, 'bool': bool}
        #Convert tuple columns -> named_tuples
        cols = []
        for c in columns:
            if not isinstance(c[1], type):
                if not c[1] in str_to_type:
                    raise Exception(f"{c[1]} is not a valid type() or key in {str_to_type}")
                if len(c) > 2:
                    cols.append(
                        TableColumn(c[0], str_to_type[c[1]], c[2])
                    )
                else:
                    cols.append(
                        TableColumn(c[0], str_to_type[c[1]], '')
                    )
                continue
            # Allows for len(2) tuple input ('name', int) --> converts to TableColumn('name', int, None)
            if not isinstance(c, TableColumn):
                cols.append(TableColumn(*c) if len(c) > 2 else TableColumn(*c, ''))
            else:
                cols.append(c)
        
        try:
            new_table = Table(
                name, 
                self, 
                cols, 
                prim_key,
                foreign_keys=foreign_keys,
                cache_enabled=cache_enabled,
                max_cache_len=max_cache_len
            )
            
            # check for existing table & detect schema changes
            if name in self.tables:
                existing_cols = [col for col in self.tables[name].columns]
                new_cols = [col.name for col in cols]
                migrated = False

                # check for new columnstype=<class
                for col in cols:
                    if not col.name in existing_cols:
                        # migration needed
                        await self.migrate_table(self, new_table)
                        migrated = True
                        break
                # check for removed columns
                if not migrated:
                    for col in existing_cols:
                        if not col in new_cols:
                            # col removed from original table - need to migrate
                            await self.migrate_table(self, new_table)
    
            result = await new_table.create_schema()
            self.log.warning(f"create_table result: {result}")

        except Exception as e:
            if 'exists' in f"{repr(e)}":
                self.log.warning(f"detected already existing table {name}")
            else:
                self.log.exception(f"error during create_table - {repr(e)}")
        
        self.tables[name] = new_table
        return f"table {name} created"

#   TOODOO:
# - Add support for creating column indexes per tables
# - Determine if views are needed and add support
# - Support for transactions?