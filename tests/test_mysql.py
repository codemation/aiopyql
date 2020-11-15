import os, unittest, json, asyncio
from aiopyql import data
from tests.main_test import async_test


class TestData(unittest.TestCase):
    def test_run_mysql_test(self):
        os.environ['DB_USER'] = 'josh'
        os.environ['DB_PASSWORD'] = 'abcd1234'
        os.environ['DB_HOST'] = 'localhost' if not 'DB_HOST' in os.environ else os.environ['DB_HOST']
        os.environ['DB_PORT'] = '3306'
        os.environ['DB_NAME'] = 'joshdb'
        os.environ['DB_TYPE'] = 'mysql'

        env = ['DB_USER','DB_PASSWORD','DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_TYPE']
        conf = ['user','password', 'host', 'port', 'database', 'db_type']
        config = {cnfVal: os.getenv(dbVal).rstrip() for dbVal,cnfVal in zip(env,conf)}
        #config['debug'] = True
        print(config)
        db = data.Database.create(
            **config,
            cache_enabled=True,
        )
        
        # Start tests
        asyncio.run(async_test(db))