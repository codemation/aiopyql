from aiopyql import data
from fastapi import FastAPI

app = FastAPI()

@app.on_event('startup')
async def db_setup():
    app.data = {}
    app.data['database'] = await data.Database.create(
        database='fastapi_db',
        cache_enabled=True
    )
    if not 'keystore' in app.data['database'].tables:
        await app.data['database'].create_table(
            'keystore',
            [
                ('key', str, 'UNIQUE NOT NULL'),
                ('value', str)
            ],
            'key',
            cache_enabled=True
        )
@app.post("/{table}")
async def insert_or_update_table(table, data: dict):
    tb = app.data['database'].tables[table]
    for key, value in data.items():
        if await tb[key] == None:
            await tb.insert(
                key=key,
                value=value
            )
        else:
            await tb.update(
                value=value,
                where={'key': key}
            )

@app.get("/{table}")
async def get_table_items(table: str):
    tb = app.data['database'].tables[table]
    return await tb.select('*')