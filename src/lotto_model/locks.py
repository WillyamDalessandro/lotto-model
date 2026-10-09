"""Draw-level advisory lock shared by issuance and canonical ingestion."""

import hashlib

from sqlalchemy import text


def draw_lock_key(game: str, target_date) -> int:
    digest = hashlib.sha256(f"draw:{game}:{target_date.isoformat()}".encode()).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


def lock_draw(connection, game: str, target_date) -> None:
    """Transaction-scoped lock; released at commit or rollback."""
    connection.execute(
        text("SELECT pg_advisory_xact_lock(:k)"),
        dict(k=draw_lock_key(game, target_date)),
    )
