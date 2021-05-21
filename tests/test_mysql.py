import os, time, unittest, json, asyncio
from aiopyql import data
from tests.main_test import async_test

os.environ['DB_USER'] = 'josh'
os.environ['DB_PASSWORD'] = 'abcd1234'
os.environ['DB_HOST'] = 'localhost' if not 'DB_HOST' in os.environ else os.environ['DB_HOST']
os.environ['DB_PORT'] = '3306'
os.environ['DB_NAME'] = 'joshdb'
os.environ['DB_TYPE'] = 'mysql'

env = ['DB_USER','DB_PASSWORD','DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_TYPE']
conf = ['user','password', 'host', 'port', 'database', 'db_type']
config = {cnfVal: os.getenv(dbVal).rstrip() for dbVal,cnfVal in zip(env,conf)}

def get_database():
    return data.Database.create(
            **config,
            cache_enabled=True,
            #debug=True
        )

class TestData(unittest.TestCase):
    def test_run_mysql_test(self):
        db = get_database()
        # Start tests
        try:
            asyncio.run(async_test(db))
        except asyncio.CancelledError:
            pass

        del db
        async def load_and_check_database():
            db = await get_database()
            for table in ['employees', 'positions', 'departments', 'stocks']:
                assert table in db.tables, f"expected {table} already in database"
        try:
            asyncio.run(load_and_check_database())
        except asyncio.CancelledError:
            pass