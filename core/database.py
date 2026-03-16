"""
core/database.py
────────────────
SQLite-backed storage for VeilClip clipboard history.

Thread safety
─────────────
Every public method opens its own connection (WAL mode, check_same_thread=False)
so background threads and the Qt main thread can call them concurrently
without sharing a connection object.  A threading.Lock serialises writes.
"""

import logging
import sqlite3
import sys
import threading
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.config import DB_PATH, MAX_ITEMS, MAX_ITEM_SIZE

logger = logging.getLogger(__name__)

# ── Schema ────────────────────────────────────────────────────────────────────

_DDL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS clipboard_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    content_type TEXT    NOT NULL CHECK(content_type IN ('text','image','link','filepath')),
    content_text TEXT,
    content_blob BLOB,
    source_app   TEXT,
    created_at   TEXT    NOT NULL,
    updated_at   TEXT,
    is_pinned    INTEGER NOT NULL DEFAULT 0,
    size_bytes   INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_created_at ON clipboard_items(created_at);
CREATE INDEX IF NOT EXISTS idx_is_pinned  ON clipboard_items(is_pinned);

CREATE VIRTUAL TABLE IF NOT EXISTS clips_fts
    USING fts5(content_text, content=clipboard_items, content_rowid=id);

CREATE TABLE IF NOT EXISTS favorites (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id      INTEGER,
    category     TEXT    NOT NULL DEFAULT 'General',
    added_at     TEXT    NOT NULL,
    content_type TEXT    NOT NULL CHECK(content_type IN ('text','image','link','filepath')),
    content_text TEXT,
    content_blob BLOB,
    source_app   TEXT,
    created_at   TEXT    NOT NULL,
    size_bytes   INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_fav_category ON favorites(category);
CREATE INDEX IF NOT EXISTS idx_fav_item_id  ON favorites(item_id);

CREATE TABLE IF NOT EXISTS vault_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    label        TEXT    NOT NULL DEFAULT '',
    content_enc  BLOB    NOT NULL,
    created_at   TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_vault_created ON vault_items(created_at);
"""

def _now_utc() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Database:
    """
    Thin wrapper around SQLite.

    Parameters
    ----------
    db_path : Path | str
        Filesystem path to the SQLite file.  Created automatically.
    """

    def __init__(self, db_path: Path | str = DB_PATH) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        """Return the shared connection, creating it lazily on first call."""
        if self._conn is None:
            con = sqlite3.connect(
                str(self._path),
                check_same_thread=False,
                timeout=10,
            )
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA journal_mode = WAL;")
            con.execute("PRAGMA foreign_keys = ON;")
            self._conn = con
        return self._conn

    @contextmanager
    def _cursor(self):
        """Context manager: yields (connection, cursor), commits on exit.
        Uses the shared persistent connection; does NOT close it on exit.
        """
        with self._lock:
            con = self._connect()
            try:
                cur = con.cursor()
                yield con, cur
                con.commit()
            except Exception:
                con.rollback()
                raise

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def init_db(self) -> None:
        with self._cursor() as (con, cur):
            cur.executescript(_DDL)
            self._migrate_favorites_snapshot(cur)
            self._migrate_updated_at(cur)
            self._migrate_fts(cur)
        logger.info("Database initialised: %s", self._path)

    def _migrate_fts(self, cur) -> None:
        """Populate the FTS index from existing rows on first run.

        The virtual table is created by the DDL above (no-op if it already
        exists).  We only need to rebuild its content when the table was
        just created (i.e. it is empty while clipboard_items has rows).
        """
        try:
            cur.execute("SELECT COUNT(*) FROM clips_fts")
            fts_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM clipboard_items")
            items_count = cur.fetchone()[0]
            if fts_count == 0 and items_count > 0:
                cur.execute(
                    "INSERT INTO clips_fts(rowid, content_text) "
                    "SELECT id, content_text FROM clipboard_items WHERE content_text IS NOT NULL"
                )
                logger.info("FTS index built from %d existing row(s).", items_count)
        except Exception as exc:
            logger.warning("FTS migration failed (non-fatal): %s", exc)

    def _migrate_updated_at(self, cur) -> None:
        """Add updated_at column to clipboard_items if it doesn't exist yet."""
        try:
            cur.execute("PRAGMA table_info(clipboard_items)")
            cols = {row[1] for row in cur.fetchall()}
            if "updated_at" not in cols:
                cur.execute("ALTER TABLE clipboard_items ADD COLUMN updated_at TEXT")
                logger.info("Migrated clipboard_items: added updated_at column.")
        except Exception as exc:
            logger.warning("updated_at migration failed (non-fatal): %s", exc)

    def _migrate_favorites(self, cur) -> None:
        """Migrate old fat favorites table to the normalized slim schema.

        If the favorites table still has content_type/content_text columns
        (old schema), we rebuild it keeping only item_id/category/added_at.
        This is a one-time migration — subsequent calls are no-ops.
        """
        try:
            cur.execute("PRAGMA table_info(favorites)")
            cols = {row[1] for row in cur.fetchall()}
            if "content_type" not in cols:
                return   # already on new schema
            logger.info("Migrating favorites table to normalized schema…")
            # Save existing rows we can map to clipboard_items
            cur.execute(
                """
                SELECT f.id, f.item_id, f.category, f.added_at
                FROM favorites f
                INNER JOIN clipboard_items c ON c.id = f.item_id
                """
            )
            rows = cur.fetchall()
            cur.execute("DROP TABLE favorites")
            cur.executescript("""
                CREATE TABLE IF NOT EXISTS favorites (
                    id       INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id  INTEGER NOT NULL,
                    category TEXT    NOT NULL DEFAULT 'General',
                    added_at TEXT    NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_fav_category ON favorites(category);
                CREATE INDEX IF NOT EXISTS idx_fav_item_id  ON favorites(item_id);
            """)
            cur.executemany(
                "INSERT INTO favorites (item_id, category, added_at) VALUES (?,?,?)",
                [(r[1], r[2], r[3]) for r in rows],
            )
            logger.info("Favorites migration complete — %d row(s) preserved.", len(rows))
        except Exception as exc:
            logger.warning("Favorites migration failed (non-fatal): %s", exc)

    def _migrate_favorites_snapshot(self, cur) -> None:
        """Ensure favorites persist independently from clipboard_items."""
        try:
            cur.execute("PRAGMA table_info(favorites)")
            cols = {row[1] for row in cur.fetchall()}
            required_cols = {
                "content_type",
                "content_text",
                "content_blob",
                "source_app",
                "created_at",
                "size_bytes",
            }
            if required_cols.issubset(cols):
                return

            logger.info("Migrating favorites table to persistent snapshot schema...")
            if "content_type" in cols:
                cur.execute(
                    """
                    SELECT
                        f.item_id,
                        f.category,
                        f.added_at,
                        COALESCE(f.content_type, c.content_type) AS content_type,
                        COALESCE(f.content_text, c.content_text) AS content_text,
                        COALESCE(f.content_blob, c.content_blob) AS content_blob,
                        COALESCE(f.source_app, c.source_app) AS source_app,
                        COALESCE(f.created_at, c.created_at, f.added_at) AS created_at,
                        COALESCE(f.size_bytes, c.size_bytes, 0) AS size_bytes
                    FROM favorites f
                    LEFT JOIN clipboard_items c ON c.id = f.item_id
                    """
                )
            else:
                cur.execute(
                    """
                    SELECT
                        f.item_id,
                        f.category,
                        f.added_at,
                        c.content_type,
                        c.content_text,
                        c.content_blob,
                        c.source_app,
                        COALESCE(c.created_at, f.added_at) AS created_at,
                        COALESCE(c.size_bytes, 0) AS size_bytes
                    FROM favorites f
                    LEFT JOIN clipboard_items c ON c.id = f.item_id
                    """
                )

            rows = [tuple(row) for row in cur.fetchall() if row[3] is not None]

            cur.execute("ALTER TABLE favorites RENAME TO favorites_legacy")
            cur.executescript(
                """
                CREATE TABLE favorites (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id      INTEGER,
                    category     TEXT    NOT NULL DEFAULT 'General',
                    added_at     TEXT    NOT NULL,
                    content_type TEXT    NOT NULL CHECK(content_type IN ('text','image','link','filepath')),
                    content_text TEXT,
                    content_blob BLOB,
                    source_app   TEXT,
                    created_at   TEXT    NOT NULL,
                    size_bytes   INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_fav_category ON favorites(category);
                CREATE INDEX IF NOT EXISTS idx_fav_item_id  ON favorites(item_id);
                """
            )
            cur.executemany(
                """
                INSERT INTO favorites (
                    item_id, category, added_at, content_type, content_text,
                    content_blob, source_app, created_at, size_bytes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            cur.execute("DROP TABLE favorites_legacy")
            logger.info("Favorites snapshot migration complete: %d row(s) preserved.", len(rows))
        except Exception as exc:
            logger.warning("Favorites snapshot migration failed (non-fatal): %s", exc)

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
        logger.debug("Database connection closed: %s", self._path)

    # ── Write ─────────────────────────────────────────────────────────────────

    def add_item(
        self,
        content_type: str,
        size_bytes: int,
        *,
        content_text: str | None = None,
        content_blob: bytes | None = None,
        source_app: str | None = None,
    ) -> int | None:
        """
        Insert a new clipboard item.

        Returns the new row id, or None if the item was skipped
        (duplicate, too large, or invalid type).
        """
        # Size guard
        if size_bytes > MAX_ITEM_SIZE:
            logger.warning(
                "Item skipped — too large: %s bytes (limit %s).",
                size_bytes, MAX_ITEM_SIZE,
            )
            return None

        with self._cursor() as (con, cur):
            # Duplicate check — same type + same text content
            if content_text:
                cur.execute(
                    """
                    SELECT id FROM clipboard_items
                    WHERE content_type = ? AND content_text = ?
                    LIMIT 1
                    """,
                    (content_type, content_text),
                )
                if cur.fetchone():
                    # Expected path — only log at DEBUG, no WARNING/ERROR
                    logger.debug("Item skipped — duplicate.")
                    return None

            # Always supply created_at explicitly to avoid NOT NULL errors
            created_at = _now_utc()

            cur.execute(
                """
                INSERT INTO clipboard_items
                    (content_type, content_text, content_blob,
                     source_app, created_at, size_bytes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (content_type, content_text, content_blob,
                 source_app, created_at, size_bytes),
            )
            new_id = cur.lastrowid
            logger.debug("Item added — id=%s type=%s", new_id, content_type)

            # Keep FTS index in sync
            if content_text and new_id:
                try:
                    cur.execute(
                        "INSERT INTO clips_fts(rowid, content_text) VALUES (?, ?)",
                        (new_id, content_text),
                    )
                except Exception as exc:
                    logger.debug("FTS insert skipped: %s", exc)

            # Enforce MAX_ITEMS: delete oldest unpinned rows beyond the limit
            cur.execute(
                """
                DELETE FROM clipboard_items
                WHERE id IN (
                    SELECT id FROM clipboard_items
                    WHERE is_pinned = 0
                    ORDER BY created_at DESC
                    LIMIT -1 OFFSET ?
                )
                """,
                (MAX_ITEMS,),
            )
            if cur.rowcount:
                logger.info(
                    "MAX_ITEMS enforced — removed %s old item(s).", cur.rowcount
                )

        return new_id

    def delete_item(self, item_id: int) -> bool:
        with self._cursor() as (con, cur):
            cur.execute("DELETE FROM clipboard_items WHERE id=?", (item_id,))
            deleted = cur.rowcount > 0
            if deleted:
                try:
                    cur.execute("DELETE FROM clips_fts WHERE rowid=?", (item_id,))
                except Exception as exc:
                    logger.debug("FTS delete skipped: %s", exc)
            return deleted

    def delete_items(self, item_ids: list[int]) -> int:
        """Delete multiple items by id. Returns count deleted."""
        if not item_ids:
            return 0
        with self._cursor() as (con, cur):
            placeholders = ",".join("?" * len(item_ids))
            cur.execute(f"DELETE FROM clipboard_items WHERE id IN ({placeholders})", item_ids)
            count = cur.rowcount
            if count:
                try:
                    cur.execute(
                        f"DELETE FROM clips_fts WHERE rowid IN ({placeholders})",
                        item_ids,
                    )
                except Exception as exc:
                    logger.debug("FTS bulk delete skipped: %s", exc)
            return count

    def restore_item(self, item: dict) -> None:
        """Re-insert a previously deleted item back into the database.

        Uses the original id so that undo restores the exact same record.
        Falls back gracefully if the id already exists (no-op duplicate).
        """
        with self._cursor() as (con, cur):
            cur.execute(
                """
                INSERT OR IGNORE INTO clipboard_items
                    (id, content_type, content_text, content_blob, source_app,
                     created_at, updated_at, is_pinned, size_bytes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.get("id"),
                    item.get("content_type", "text"),
                    item.get("content_text"),
                    item.get("content_blob"),
                    item.get("source_app"),
                    item.get("created_at", _now_utc()),
                    item.get("updated_at"),
                    int(item.get("is_pinned", 0)),
                    item.get("size_bytes", 0),
                ),
            )
            # Rebuild FTS entry
            if cur.rowcount:
                try:
                    cur.execute(
                        "INSERT INTO clips_fts(rowid, content_text) VALUES (?, ?)",
                        (item.get("id"), item.get("content_text")),
                    )
                except Exception as exc:
                    logger.debug("FTS restore skipped: %s", exc)

    def update_text(self, item_id: int, new_text: str) -> bool:
        """Update the text content of a clipboard item."""
        with self._cursor() as (con, cur):
            cur.execute(
                "UPDATE clipboard_items SET content_text=?, updated_at=? WHERE id=?",
                (new_text, _now_utc(), item_id),
            )
            return cur.rowcount > 0

    def toggle_pin(self, item_id: int) -> bool:
        with self._cursor() as (con, cur):
            cur.execute(
                "UPDATE clipboard_items SET is_pinned = 1 - is_pinned, updated_at=? WHERE id=?",
                (_now_utc(), item_id),
            )
            return cur.rowcount > 0

    def clear_unpinned(self) -> int:
        """Delete all unpinned items. Returns number of rows deleted."""
        with self._cursor() as (con, cur):
            cur.execute("DELETE FROM clipboard_items WHERE is_pinned = 0")
            count = cur.rowcount
        logger.info("clear_unpinned: removed %s item(s).", count)
        return count

    def clear_pinned(self) -> int:
        """Delete all pinned items. Returns number of rows deleted."""
        with self._cursor() as (con, cur):
            cur.execute("DELETE FROM clipboard_items WHERE is_pinned = 1")
            count = cur.rowcount
        logger.info("clear_pinned: removed %s item(s).", count)
        return count

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_all_items(self) -> list[dict]:
        """Return all items: pinned first, then newest first."""
        with self._cursor() as (con, cur):
            cur.execute(
                """
                SELECT id, content_type, content_text, content_blob,
                       source_app, created_at, is_pinned, size_bytes
                FROM clipboard_items
                ORDER BY is_pinned DESC, created_at DESC
                """
            )
            return [dict(row) for row in cur.fetchall()]

    def search_items(self, query: str) -> list[dict]:
        """Search clipboard history using FTS5 for content_text, LIKE for source_app.

        FTS provides fast, tokenised full-text matching.  Results from both
        paths are merged, de-duplicated, and sorted (pinned first, newest first).
        Falls back gracefully to LIKE-only if the FTS table is unavailable.
        """
        pattern = f"%{query}%"
        with self._cursor() as (con, cur):
            # FTS match on content_text
            fts_ids: set[int] = set()
            try:
                cur.execute(
                    "SELECT rowid FROM clips_fts WHERE clips_fts MATCH ?",
                    (query,),
                )
                fts_ids = {row[0] for row in cur.fetchall()}
            except Exception as exc:
                logger.debug("FTS search unavailable, using LIKE fallback: %s", exc)

            if fts_ids:
                # Combine FTS hits with source_app LIKE hits
                placeholders = ",".join("?" * len(fts_ids))
                cur.execute(
                    f"""
                    SELECT id, content_type, content_text, content_blob,
                           source_app, created_at, is_pinned, size_bytes
                    FROM clipboard_items
                    WHERE id IN ({placeholders}) OR source_app LIKE ?
                    ORDER BY is_pinned DESC, created_at DESC
                    """,
                    (*fts_ids, pattern),
                )
            else:
                # No FTS hits — fall back to full LIKE search
                cur.execute(
                    """
                    SELECT id, content_type, content_text, content_blob,
                           source_app, created_at, is_pinned, size_bytes
                    FROM clipboard_items
                    WHERE content_text LIKE ? OR source_app LIKE ?
                    ORDER BY is_pinned DESC, created_at DESC
                    """,
                    (pattern, pattern),
                )
            return [dict(row) for row in cur.fetchall()]

    def get_by_source(self, source_app: str) -> list[dict]:
        with self._cursor() as (con, cur):
            cur.execute(
                """
                SELECT * FROM clipboard_items
                WHERE source_app = ?
                ORDER BY is_pinned DESC, created_at DESC
                """,
                (source_app,),
            )
            return [dict(row) for row in cur.fetchall()]

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def cleanup_old_items(self, max_age_hours: int = 24) -> int:
        """
        Delete unpinned items older than *max_age_hours*.
        Returns number of rows deleted.
        """
        cutoff = (
            datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        with self._cursor() as (con, cur):
            cur.execute(
                """
                DELETE FROM clipboard_items
                WHERE is_pinned = 0
                  AND created_at < ?
                """,
                (cutoff,),
            )
            count = cur.rowcount

        if count:
            logger.info(
                "cleanup_old_items: removed %s item(s) older than %sh.",
                count, max_age_hours,
            )
        else:
            logger.debug(
                "cleanup_old_items: nothing to remove (max_age=%sh).", max_age_hours
            )

        return count

    # ── Favorites ─────────────────────────────────────────────────────────────

    def add_favorite(self, item: dict, category: str = "General") -> int | None:
        """Add a clipboard item to favorites under the given category.
        Returns new favorite id, or None if already exists in that category."""
        with self._cursor() as (con, cur):
            item_id = item.get("id")
            if item_id is not None:
                cur.execute(
                    "SELECT id FROM favorites WHERE item_id=? AND category=? LIMIT 1",
                    (item_id, category),
                )
            else:
                cur.execute(
                    """
                    SELECT id FROM favorites
                    WHERE item_id IS NULL
                      AND category=?
                      AND content_type=?
                      AND COALESCE(content_text, '') = COALESCE(?, '')
                      AND COALESCE(source_app, '') = COALESCE(?, '')
                    LIMIT 1
                    """,
                    (
                        category,
                        item.get("content_type", "text"),
                        item.get("content_text"),
                        item.get("source_app"),
                    ),
                )
            if cur.fetchone():
                return None
            added_at = _now_utc()
            cur.execute(
                """
                INSERT INTO favorites (
                    item_id, category, added_at, content_type, content_text,
                    content_blob, source_app, created_at, size_bytes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item_id,
                    category,
                    added_at,
                    item.get("content_type", "text"),
                    item.get("content_text"),
                    item.get("content_blob"),
                    item.get("source_app"),
                    item.get("created_at", added_at),
                    item.get("size_bytes", 0),
                ),
            )
            return cur.lastrowid

    def remove_favorite(self, fav_id: int) -> bool:
        with self._cursor() as (con, cur):
            cur.execute("DELETE FROM favorites WHERE id=?", (fav_id,))
            return cur.rowcount > 0

    def update_favorite_text(self, fav_id: int, new_text: str) -> bool:
        """Update a favorite snapshot and its linked clipboard item if present."""
        with self._cursor() as (con, cur):
            cur.execute("SELECT item_id FROM favorites WHERE id=?", (fav_id,))
            row = cur.fetchone()
            if row is None:
                return False

            linked_item_id = row["item_id"]
            cur.execute("UPDATE favorites SET content_text=? WHERE id=?", (new_text, fav_id))
            updated = cur.rowcount > 0

            if linked_item_id is not None:
                cur.execute(
                    "UPDATE clipboard_items SET content_text=?, updated_at=? WHERE id=?",
                    (new_text, _now_utc(), linked_item_id),
                )
                if cur.rowcount:
                    try:
                        cur.execute("DELETE FROM clips_fts WHERE rowid=?", (linked_item_id,))
                        cur.execute(
                            "INSERT INTO clips_fts(rowid, content_text) VALUES (?, ?)",
                            (linked_item_id, new_text),
                        )
                    except Exception as exc:
                        logger.debug("FTS favorite text update skipped: %s", exc)

            return updated

    def get_favorites(self, category: str | None = None) -> list[dict]:
        """Return persistent favorites. Newest first within category."""
        with self._cursor() as (con, cur):
            if category:
                cur.execute(
                    """
                    SELECT id, item_id, category, added_at, content_type,
                           content_text, content_blob, source_app,
                           created_at, size_bytes
                    FROM favorites
                    WHERE category = ?
                    ORDER BY added_at DESC
                    """,
                    (category,),
                )
            else:
                cur.execute(
                    """
                    SELECT id, item_id, category, added_at, content_type,
                           content_text, content_blob, source_app,
                           created_at, size_bytes
                    FROM favorites
                    ORDER BY category, added_at DESC
                    """
                )
            return [dict(row) for row in cur.fetchall()]

    def get_favorite_categories(self) -> list[str]:
        """Return sorted list of distinct category names that still have items."""
        with self._cursor() as (con, cur):
            cur.execute(
                """
                SELECT DISTINCT category
                FROM favorites
                ORDER BY category
                """
            )
            return [row[0] for row in cur.fetchall()]

    def rename_favorite_category(self, old_name: str, new_name: str) -> int:
        with self._cursor() as (con, cur):
            cur.execute(
                "UPDATE favorites SET category=? WHERE category=?",
                (new_name, old_name),
            )
            return cur.rowcount

    def delete_favorite_category(self, category: str) -> int:
        with self._cursor() as (con, cur):
            cur.execute("DELETE FROM favorites WHERE category=?", (category,))
            return cur.rowcount

    # ── Vault ─────────────────────────────────────────────────────────────────

    def add_vault_item(self, content_enc: bytes, label: str = "") -> int | None:
        from datetime import datetime, timezone
        created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._cursor() as (con, cur):
            cur.execute(
                "INSERT INTO vault_items (label, content_enc, created_at) VALUES (?,?,?)",
                (label, content_enc, created_at),
            )
            return cur.lastrowid

    def get_vault_items_raw(self) -> list[dict]:
        with self._cursor() as (con, cur):
            cur.execute(
                "SELECT id, label, content_enc, created_at FROM vault_items ORDER BY created_at DESC"
            )
            return [dict(row) for row in cur.fetchall()]

    def delete_vault_item(self, vault_id: int) -> bool:
        with self._cursor() as (con, cur):
            cur.execute("DELETE FROM vault_items WHERE id=?", (vault_id,))
            return cur.rowcount > 0

    def update_vault_item_enc(self, vault_id: int, content_enc: bytes) -> bool:
        with self._cursor() as (con, cur):
            cur.execute(
                "UPDATE vault_items SET content_enc=? WHERE id=?",
                (content_enc, vault_id),
            )
            return cur.rowcount > 0

    def update_vault_item_label(self, vault_id: int, label: str) -> bool:
        with self._cursor() as (con, cur):
            cur.execute(
                "UPDATE vault_items SET label=? WHERE id=?",
                (label, vault_id),
            )
            return cur.rowcount > 0

    def get_change_hash(self) -> tuple[int, int, int, str]:
        """Return (max_id, count, pinned_sum, max_updated_at) — a cheap proxy
        for detecting any change including pin toggles and text edits.

        The live-refresh timer calls this every 500 ms instead of fetching
        all rows.  A full reload only happens when this tuple changes.
        """
        with self._cursor() as (con, cur):
            cur.execute(
                """
                SELECT
                    COALESCE(MAX(id), 0),
                    COUNT(*),
                    COALESCE(SUM(is_pinned), 0),
                    COALESCE(MAX(updated_at), MAX(created_at), '')
                FROM clipboard_items
                """
            )
            row = cur.fetchone()
            return (row[0], row[1], row[2], row[3])

    def item_count(self) -> int:
        with self._cursor() as (con, cur):
            cur.execute("SELECT COUNT(*) FROM clipboard_items")
            return cur.fetchone()[0]


# ── Self-test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    )

    db = Database()
    db.init_db()

    db.add_item("text", 5, content_text="Hello World", source_app="Test")
    db.add_item("link", 30, content_text="https://example.com", source_app="Chrome")
    db.add_item("text", 5, content_text="Hello World", source_app="Test")  # duplicate

    items = db.get_all_items()
    print(f"\nTotal items: {len(items)}")
    for it in items:
        print(f"  [{it['id']}] {it['content_type']:8s} | {(it['content_text'] or '')[:40]!r}")

    removed = db.cleanup_old_items(max_age_hours=0)
    print(f"\nCleanup (age=0) removed: {removed}")
    print(f"Remaining: {db.item_count()}")
