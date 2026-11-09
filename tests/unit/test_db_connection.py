"""get_db() must open exactly one connection however many callers race it.

Two racing first callers used to each open a connection, leak one, and run
PRAGMAs on the other mid-statement ("database table is locked" in
test_assistant_provider on CI).
"""
import asyncio

from agent.db import schema


async def test_concurrent_first_calls_open_one_connection(test_db, monkeypatch):
    await schema.close_db()
    assert schema._db_connection is None

    real_connect = schema.aiosqlite.connect
    opened = []

    def counting_connect(*args, **kwargs):
        conn = real_connect(*args, **kwargs)
        opened.append(conn)
        return conn

    monkeypatch.setattr(schema.aiosqlite, "connect", counting_connect)

    conns = await asyncio.gather(*(schema.get_db() for _ in range(8)))

    try:
        assert len(opened) == 1
        assert all(c is conns[0] for c in conns)
    finally:
        # Close any extras so a failure here doesn't leak worker threads.
        for conn in opened:
            if conn is not schema._db_connection:
                await conn.close()
