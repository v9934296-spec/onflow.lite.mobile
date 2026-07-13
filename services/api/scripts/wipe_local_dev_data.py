"""Wipe all local dev user data for a clean smoke-test run."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text

from app.core.config import _API_DIR, get_settings


def main() -> None:
    settings = get_settings()
    engine = create_engine(settings.get_database_url())

    with engine.connect() as conn:
        tables = conn.execute(
            text(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT IN ('sqlite_sequence', 'alembic_version') "
                "ORDER BY name"
            )
        ).fetchall()
        print("Before wipe:")
        for (name,) in tables:
            count = conn.execute(text(f'SELECT COUNT(*) FROM "{name}"')).scalar_one()
            if count:
                print(f"  {name}: {count}")

    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        for (name,) in tables:
            conn.execute(text(f'DELETE FROM "{name}"'))
        conn.execute(text("PRAGMA foreign_keys=ON"))

    upload_dir = (_API_DIR / settings.upload_dir).resolve()
    retention_dir = settings.retention_dir_resolved
    removed_uploads = 0
    removed_retained = 0

    if upload_dir.exists():
        for path in upload_dir.iterdir():
            if path.is_file():
                path.unlink()
                removed_uploads += 1

    if retention_dir.exists():
        for path in retention_dir.rglob("*"):
            if path.is_file():
                path.unlink()
                removed_retained += 1

    with engine.connect() as conn:
        users = conn.execute(text("SELECT COUNT(*) FROM users")).scalar_one()
        clip_jobs = conn.execute(text("SELECT COUNT(*) FROM clip_jobs")).scalar_one()

    print(f"Removed {removed_uploads} upload file(s) and {removed_retained} retained file(s).")
    print(f"After wipe: users={users}, clip_jobs={clip_jobs}")


if __name__ == "__main__":
    main()
