import logging 
import uuid, time
import asyncio
from typing import (
    Optional
)
from concurrent.futures._base import CancelledError
from asyncio.base_futures import InvalidStateError

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
        **kw):
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
        self.queue_process_task = None
        self.queue_results = {"pending": {}, "finished": {}}
        self.MAX_QUEUE_PROCESS = 100

        self.queue_processing = False
    def setup_parameter_check(self, params):
        self.connect_params =  {'user', 'password', 'host', 'port'}

        db_key = 'db' if not self.type == 'sqlite' else 'database'
        self.connect_config = {db_key: self.db_name}
        for k,v in params.items():
            if k in self.connect_params:
                self.connect_config[k] = v if not k == 'port' else int(v)
    def setup_connection_and_cursor(self):
        """
        based on database type, setup connection / cursor for database
        """
        if self.type == 'mysql':
            import aiopyql.mysql_connector as connector 
        if self.type == 'sqlite':
            import aiopyql.sqlite_connector as connector

        self.connect = connector.get_db_manager()
        self.cursor = connector.get_cursor_manager(self)
        self.load_tables = connector.load_tables
        def db_validate_where_input(tables, where):
            return connector.validate_where_input(self, tables, where)
        self._validate_where_input = db_validate_where_input
    def __del__(self):
        self.queue_process_task.cancel()
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

    async def __commit_querries(self, connection, querries):
        self.log.debug(f"__commit_querries started for {querries}")
        start = time.time()
        run_querries = []
        for query in querries:
            run_querries.append(
                self.__commit_querries_run_query(query)
            )
        if self.type == 'mysql':
            for run_q in run_querries:
                await run_q
        else:
            await asyncio.gather(*run_querries, return_exceptions=True)
        await connection.commit()
        self.log.debug(f"__commit_querries of {len(querries)} completed in {time.time() - start} seconds")

    async def __process_queue(self, commit=True):
        self.queue_processing = True
        try:
            last_exception = None
            async for conn in self.cursor(commit=commit):
                querries_to_commit = []
                last_commit = time.time()
                queue_empty = True
                try:
                    while True:
                        try:
                            if queue_empty:
                                query_id, query = await self._query_queue.get()
                                queue_empty = False
                            else:
                                query_id, query = self._query_queue.get_nowait()
                            query_commit = not (
                                'SELECT' in query
                                or 'select' in query
                                or 'show ' in query
                                )

                            query_start = time.time()
                            query = f"{';'.join(self.pre_query + [query])}"
                            query = query.split(';') if ';' in query else [query]
                        except Exception as e:
                            if not isinstance(e, asyncio.queues.QueueEmpty):
                                last_exception = e
                                break
                            if len(querries_to_commit) > 0:
                                self.log.debug(f"queue empty, commiting: {querries_to_commit}")
                                await self.__commit_querries(
                                    conn[1] if self.type == 'mysql' else conn,
                                    querries_to_commit
                                )
                                querries_to_commit = []
                            last_commit = time.time()
                            queue_empty = True
                            continue

                        if not query_commit or time.time() - last_commit > 0.05:
                            if len(querries_to_commit) > 0:
                                await self.__commit_querries(
                                    conn[1] if self.type == 'mysql' else conn,
                                    querries_to_commit
                                )
                                querries_to_commit = []
                            last_commit = time.time()
                        results = []
                        try:
                            for q in query:
                                if self.type == 'mysql':
                                    if not query_commit:
                                        self.log.debug(f"{self.db_name} - execute: {q}")
                                        await conn[0].execute(q)
                                        result = await conn[0].fetchall()          
                                        for row in result:
                                            results.append(row)
                                    else:
                                        querries_to_commit.append(
                                            (query_id, q, conn[0].execute(q))
                                        )
                                    
                                if self.type == 'sqlite':
                                    if not query_commit:
                                        async with conn.execute(q) as cursor:
                                            async for row in cursor:
                                                results.append(row)
                                    else:
                                        querries_to_commit.append(
                                            (query_id, q, conn.execute(q))
                                        )
                        except Exception as e:
                            self.log.exception(f"error running query: {query}")
                            results = e
                        if not query_commit:
                            #self.queue_results[query_id] = results
                            await self.queue_results[query_id].put(results)
                except Exception as e:
                    if not isinstance(e, CancelledError):
                        self.log.exception(f"error in __process_queue, closing db connection")
                    continue
                                                      
        except Exception as e:
            if not e in {InvalidStateError, CancelledError}:
                self.log.exception(f"error during __process_queue")

        # un-locks processing so new processing tasks can start
        self.queue_processing = False

        return "completed processing items in queue"

    async def execute(self, query, commit=False):
        query_id = str(uuid.uuid1())
        self.queue_results[query_id] = asyncio.Queue(1)
        await self._query_queue.put((query_id, query))
        # start queue procesing task
        if not self.queue_processing:
            self.queue_process_task = self.loop.create_task(self.__process_queue())
            await asyncio.sleep(0.005)
        try:
            result = await self.queue_results[query_id].get()
        except Exception as e:
            self.log.exception(f"error while executing query {query}")
            result = e
        #result = self.queue_results.pop(query_id)
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
        #Convert tuple columns -> named_tuples
        cols = []
        for c in columns:
            # Allows for len(2) tuple input ('name', int) --> converts to TableColumn('name', int, None)
            if not isinstance(c, TableColumn):
                cols.append(TableColumn(*c) if len(c) > 2 else TableColumn(*c, ''))
            else:
                cols.append(c)
        self.tables[name] = Table(
            name, 
            self, 
            cols, 
            prim_key,
            foreign_keys=foreign_keys,
            cache_enabled=cache_enabled,
            max_cache_len=max_cache_len
        )
        if not 'existing' in kw:
            await self.tables[name].create_schema()
        self.log.debug(f"table {name} created")
        return f"table {name} created"

#   TOODOO:
# - Add support for creating column indexes per tables
# - Determine if views are needed and add support
# - Support for transactions?