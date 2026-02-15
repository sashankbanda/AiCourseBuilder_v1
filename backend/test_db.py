"""Test DB connection with DNS fallback"""
import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

async def test():
    try:
        from app.config.db import Database
        pool = await Database.get_pool()
        print("SUCCESS: Connected to database!")
        result = await pool.fetchval("SELECT 1")
        print(f"Query test: SELECT 1 = {result}")
        await Database.close()
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")

asyncio.run(test())
