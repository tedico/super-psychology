import psycopg


def check_connection(database_url: str) -> str:
    """Connect, run SELECT version(), return the server version string."""
    with psycopg.connect(database_url, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version()")
            row = cur.fetchone()
            if row is None:
                raise RuntimeError("SELECT version() returned no row")
            return row[0]
