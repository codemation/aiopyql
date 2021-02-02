import os, unittest, json, asyncio
from aiopyql import data
from tests.main_test import async_test


class TestData(unittest.TestCase):
    def test_run_sqlite_test(self):
        # test async load inside event loop
        db = data.Database.create(
                database="testdb",
                cache_enabled=True,
                #debug=True
            )
        try:
            asyncio.run(async_test(db))
        except asyncio.CancelledError:
            pass