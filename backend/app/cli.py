from __future__ import annotations

import argparse
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from .core.security import hash_password
from .db import SessionLocal, init_development_database
from .models import ConversationSession, Marker, Practice, PracticeAttempt, User, UserPreference
from .services.storage import get_storage


def parse_legacy_datetime(value: object) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    raw = str(value).strip()
    if not raw:
        return None
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def create_admin(email: str, password: str, display_name: str) -> None:
    init_development_database()
    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == email.casefold()))
        if existing:
            existing.role = "admin"
            existing.status = "active"
            existing.password_hash = hash_password(password)
        else:
            existing = User(email=email.casefold(), display_name=display_name, role="admin", password_hash=hash_password(password))
            existing.preference = UserPreference()
            db.add(existing)
        db.commit()
        print(f"管理员账号已准备：{existing.email}")


def migrate_legacy(path: Path, owner_email: str, owner_password: str) -> None:
    if not path.is_file():
        raise SystemExit(f"找不到旧数据库：{path}")
    init_development_database()
    source = sqlite3.connect(path)
    source.row_factory = sqlite3.Row
    storage = get_storage()
    with SessionLocal() as db:
        owner = db.scalar(select(User).where(User.email == owner_email.casefold()))
        if not owner:
            owner = User(email=owner_email.casefold(), display_name="旧数据所有者", password_hash=hash_password(owner_password), role="admin")
            owner.preference = UserPreference()
            db.add(owner)
            db.flush()
        for row in source.execute("SELECT * FROM sessions"):
            if db.get(ConversationSession, row["id"]):
                continue
            object_key = None
            audio_path = row["audio_path"] if "audio_path" in row.keys() else None
            if audio_path and Path(audio_path).is_file():
                suffix = Path(audio_path).suffix
                object_key = f"users/{owner.id}/sessions/{row['id']}/original{suffix}"
                storage.put(object_key, Path(audio_path).read_bytes(), "application/octet-stream")
            import json
            item = ConversationSession(
                id=row["id"], owner_id=owner.id, title=row["title"], scenario=row["scenario"],
                created_at=parse_legacy_datetime(row["created_at"]), duration_ms=row["duration_ms"], processing_status=row["processing_status"],
                audio_object_key=object_key, analysis_json=json.loads(row["analysis_json"]) if row["analysis_json"] else None,
                failure_reason=row["failure_reason"], user_speaker_id=row["user_speaker_id"],
            )
            db.add(item)
        db.flush()
        for row in source.execute("SELECT * FROM markers"):
            if not db.get(Marker, row["id"]):
                db.add(Marker(id=row["id"], session_id=row["session_id"], timestamp_ms=row["timestamp_ms"]))
        db.commit()
        print(f"旧数据已导入账号：{owner.email}；原数据库未删除。")
    source.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Beyond Words 运维工具")
    sub = parser.add_subparsers(dest="command", required=True)
    admin = sub.add_parser("create-admin")
    admin.add_argument("--email", required=True)
    admin.add_argument("--password", required=True)
    admin.add_argument("--name", default="系统管理员")
    legacy = sub.add_parser("migrate-legacy")
    legacy.add_argument("--source", default="backend/data/beyond_words.db")
    legacy.add_argument("--owner-email", default=os.getenv("LEGACY_OWNER_EMAIL"))
    legacy.add_argument("--owner-password", default=os.getenv("LEGACY_OWNER_PASSWORD"))
    args = parser.parse_args()
    if args.command == "create-admin":
        create_admin(args.email, args.password, args.name)
    elif args.command == "migrate-legacy":
        if not args.owner_email or not args.owner_password:
            raise SystemExit("必须提供旧数据所有者邮箱和至少 12 位密码")
        migrate_legacy(Path(args.source).resolve(), args.owner_email, args.owner_password)


if __name__ == "__main__":
    main()
