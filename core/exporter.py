"""
core/exporter.py
────────────────
Export and import clipboard history as JSON or CSV.

Export includes: id, content_type, content_text, source_app,
                 created_at, is_pinned.
Image blobs are omitted from text-based exports (noted as [image]).

Import merges items into the current DB — duplicates (same content_type
+ content_text) are silently skipped via the existing add_item() guard.
"""

import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import utils.i18n as i18n

if TYPE_CHECKING:
    from core.database import Database

logger = logging.getLogger(__name__)

_EXPORT_FIELDS = [
    "id", "content_type", "content_text",
    "source_app", "created_at", "is_pinned",
]


# ── Export ────────────────────────────────────────────────────────────────────

def export_json(db: "Database", dest_path: Path) -> tuple[int, str]:
    """
    Write clipboard history to a JSON file.
    Returns (count, message).
    """
    try:
        items = db.get_all_items()
        records = []
        for it in items:
            rec = {k: it.get(k) for k in _EXPORT_FIELDS}
            if it.get("content_blob") and not rec.get("content_text"):
                rec["content_text"] = "[image]"
            records.append(rec)

        dest_path = Path(dest_path)
        dest_path.write_text(
            json.dumps(
                {"veilclip_export": True, "items": records},
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        logger.info("Exported %d items → %s", len(records), dest_path)
        return len(records), i18n.get("export.messages.exported", count=len(records))
    except Exception as exc:
        logger.error("JSON export failed: %s", exc)
        return 0, i18n.get("export.messages.export_failed", detail=str(exc))


def export_csv(db: "Database", dest_path: Path) -> tuple[int, str]:
    """
    Write clipboard history to a CSV file.
    Returns (count, message).
    """
    try:
        items = db.get_all_items()
        dest_path = Path(dest_path)
        with dest_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=_EXPORT_FIELDS)
            writer.writeheader()
            count = 0
            for it in items:
                rec = {k: it.get(k, "") for k in _EXPORT_FIELDS}
                if it.get("content_blob") and not rec.get("content_text"):
                    rec["content_text"] = "[image]"
                writer.writerow(rec)
                count += 1
        logger.info("Exported %d items → %s", count, dest_path)
        return count, i18n.get("export.messages.exported", count=count)
    except Exception as exc:
        logger.error("CSV export failed: %s", exc)
        return 0, i18n.get("export.messages.export_failed", detail=str(exc))


# ── Import ────────────────────────────────────────────────────────────────────

def import_json(db: "Database", src_path: Path) -> tuple[int, str]:
    """
    Import items from an VeilClip JSON export.
    Returns (imported_count, message).
    """
    try:
        data = json.loads(Path(src_path).read_text(encoding="utf-8"))
        items = data.get("items", data) if isinstance(data, dict) else data
        if not isinstance(items, list):
            return 0, i18n.get("export.messages.invalid_json")
        return _import_records(db, items)
    except Exception as exc:
        logger.error("JSON import failed: %s", exc)
        return 0, i18n.get("export.messages.import_failed", detail=str(exc))


def import_csv(db: "Database", src_path: Path) -> tuple[int, str]:
    """
    Import items from an VeilClip CSV export.
    Returns (imported_count, message).
    """
    try:
        records = []
        with Path(src_path).open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append(dict(row))
        return _import_records(db, records)
    except Exception as exc:
        logger.error("CSV import failed: %s", exc)
        return 0, i18n.get("export.messages.import_failed", detail=str(exc))


def _import_records(db: "Database", records: list[dict]) -> tuple[int, str]:
    imported = 0
    skipped  = 0
    valid_types = {"text", "link", "image", "filepath"}

    for rec in records:
        ct   = str(rec.get("content_type", "text")).strip()
        text = rec.get("content_text") or None
        src  = rec.get("source_app")   or None

        if ct not in valid_types:
            skipped += 1
            continue
        if ct == "image" or not text or text == "[image]":
            skipped += 1
            continue

        size = len(text.encode("utf-8"))
        result = db.add_item(
            ct,
            size,
            content_text=text,
            source_app=src,
        )
        if result is not None:
            imported += 1
        else:
            skipped += 1

    msg = i18n.get("export.messages.imported", imported=imported, skipped=skipped)
    logger.info(msg)
    return imported, msg
