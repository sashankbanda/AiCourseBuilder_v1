"""Run schema.sql against the database configured in .env"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

async def run():
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        print("ERROR: DATABASE_URL not set in .env")
        return
    # asyncpg doesn't support channel_binding as a DSN parameter
    dsn = dsn.split('&channel_binding')[0]
    print(f"Connecting to database...")
    conn = await asyncpg.connect(dsn, ssl='require')
    
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    sql = open(schema_path, 'r').read()
    await conn.execute(sql)
    print("Schema applied successfully!")
    await conn.close()

if __name__ == '__main__':
    asyncio.run(run())
