import asyncpg
import os
import re
import socket
import subprocess
import ssl
from typing import Optional
from urllib.parse import urlparse


def _resolve_via_google_dns(hostname: str) -> Optional[str]:
    """Resolve hostname using Google's public DNS (8.8.8.8) as fallback."""
    try:
        result = subprocess.run(
            ["nslookup", hostname, "8.8.8.8"],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout + "\n" + result.stderr
        ips = re.findall(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b', output)
        for ip in ips:
            if not ip.startswith("8.8."):
                return ip
    except Exception as e:
        print(f"[Database] Google DNS fallback failed: {e}")
    return None


class _NeonSSLContext:
    """Wrapper that injects server_hostname for Neon SNI-based routing."""

    def __init__(self, hostname: str):
        self._ctx = ssl.create_default_context()
        self._ctx.check_hostname = False
        self._ctx.verify_mode = ssl.CERT_NONE
        self._hostname = hostname

    def __getattr__(self, name):
        return getattr(self._ctx, name)

    def wrap_socket(self, sock, **kwargs):
        kwargs['server_hostname'] = self._hostname
        return self._ctx.wrap_socket(sock, **kwargs)


class Database:
    _pool: Optional[asyncpg.Pool] = None

    @classmethod
    async def get_pool(cls) -> asyncpg.Pool:
        if cls._pool is None:
            dsn = os.environ.get("DATABASE_URL")
            if not dsn:
                raise ValueError("DATABASE_URL is not set")

            parsed = urlparse(dsn)
            hostname = parsed.hostname or "localhost"
            port = parsed.port or 5432
            username = parsed.username
            password = parsed.password
            database = parsed.path.lstrip("/") if parsed.path else None

            # Determine the host to connect to
            connect_host = hostname
            ssl_arg: object = "require"  # default: let asyncpg handle SSL

            try:
                socket.getaddrinfo(hostname, None)
            except socket.gaierror:
                print(f"[Database] System DNS failed for {hostname}, trying Google DNS...")
                ip = _resolve_via_google_dns(hostname)
                if ip:
                    print(f"[Database] Resolved {hostname} -> {ip}")
                    connect_host = ip
                    # Use custom SSL context that passes original hostname for Neon SNI
                    ssl_arg = _NeonSSLContext(hostname)
                else:
                    raise ConnectionError(f"Cannot resolve database host: {hostname}")

            cls._pool = await asyncpg.create_pool(
                host=connect_host,
                port=port,
                user=username,
                password=password,
                database=database,
                ssl=ssl_arg,
            )
            print("[Database] Connection pool created")
        return cls._pool

    @classmethod
    async def close(cls):
        if cls._pool:
            await cls._pool.close()
            cls._pool = None
            print("[Database] Connection pool closed")

    @classmethod
    async def fetch(cls, query: str, *args):
        pool = await cls.get_pool()
        async with pool.acquire() as connection:
            return await connection.fetch(query, *args)

    @classmethod
    async def execute(cls, query: str, *args):
        pool = await cls.get_pool()
        async with pool.acquire() as connection:
            return await connection.execute(query, *args)


