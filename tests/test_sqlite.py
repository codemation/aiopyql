import os, unittest, json, asyncio
from aiopyql import data
from tests.main_test import async_test

def get_database():
    return data.Database.create(
        database="testdb",
        cache_enabled=True,
    )



class TestData(unittest.TestCase):
    def test_run_sqlite_test(self):
        # test async load inside event loop
        db = get_database()
        try:
            asyncio.run(async_test(db))
        except asyncio.CancelledError:
            pass
        
        del db

        async def load_and_check_database():
            db = await get_database()
            for table in ['employees', 'positions', 'departments', 'stocks']:
                assert table in db.tables, f"expected {table} already in database - tables {db.tables}"
        try:
            asyncio.run(load_and_check_database())
        except asyncio.CancelledError:
            pass