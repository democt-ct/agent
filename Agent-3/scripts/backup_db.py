#!/usr/bin/env python3
"""数据库备份脚本 — 复制 SQLite DB + Chroma 向量库。

用法:
    python scripts/backup_db.py                     # 备份到 data/backups/
    python scripts/backup_db.py --output /path/     # 指定输出目录
    python scripts/backup_db.py --keep 10           # 保留最近 10 个备份

可配合 cron / Task Scheduler 定时执行:
    # Linux cron (每天 2:00 AM):
    0 2 * * * cd /app && python scripts/backup_db.py --keep 7

    # Windows 计划任务:
    schtasks /create /tn "EnterpriseDB Backup" /tr "python scripts\backup_db.py" /sc daily /st 02:00
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tools.db.connection import get_db_path, get_db_size_mb


def backup_db(output_dir: str, keep: int = 30) -> None:
    """备份 SQLite 数据库 + Chroma 向量库。

    Args:
        output_dir: 输出目录
        keep: 保留最近 N 个备份
    """
    backup_root = Path(output_dir)
    backup_root.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_name = f"backup_{timestamp}"
    backup_path = backup_root / backup_name
    backup_path.mkdir(parents=True, exist_ok=True)

    # 1. SQLite 备份（使用 SQLite 内置 backup API 确保一致性）
    db_path = get_db_path()
    if db_path.exists():
        import sqlite3
        dest = backup_path / db_path.name
        src_conn = sqlite3.connect(str(db_path))
        dst_conn = sqlite3.connect(str(dest))
        src_conn.backup(dst_conn)
        src_conn.close()
        dst_conn.close()
        size_mb = dest.stat().st_size / (1024 * 1024)
        print(f"✅ SQLite 备份: {dest} ({size_mb:.1f} MB)")
    else:
        print(f"⚠️  数据库文件不存在: {db_path}")

    # 2. Chroma 向量库备份
    project_root = Path(__file__).resolve().parent.parent
    chroma_src = project_root / "chroma_db"
    if chroma_src.exists():
        chroma_dest = backup_path / "chroma_db"
        shutil.copytree(chroma_src, chroma_dest, dirs_exist_ok=True)
        # 计算大小
        total = sum(f.stat().st_size for f in chroma_dest.rglob("*") if f.is_file())
        print(f"✅ Chroma 备份: {chroma_dest} ({total / (1024*1024):.1f} MB)")
    else:
        print(f"⚠️  Chroma 目录不存在: {chroma_src}")

    # 3. 压缩
    archive_path = str(backup_path) + ".zip"
    shutil.make_archive(str(backup_path), "zip", backup_root, backup_name)
    shutil.rmtree(backup_path)
    archive_size = Path(archive_path).stat().st_size / (1024 * 1024)
    print(f"📦 打包: {archive_path} ({archive_size:.1f} MB)")

    # 4. 清理旧备份（保留最近 N 个）
    _cleanup_old_backups(backup_root, keep)


def _cleanup_old_backups(backup_root: Path, keep: int) -> None:
    """清理旧备份，保留最近 N 个 zip 文件。"""
    archives = sorted(
        backup_root.glob("backup_*.zip"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in archives[keep:]:
        old.unlink()
        print(f"🗑  清理旧备份: {old.name}")


def list_backups(output_dir: str) -> None:
    """列出已有备份。"""
    backup_root = Path(output_dir)
    archives = sorted(
        backup_root.glob("backup_*.zip"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not archives:
        print("暂无备份")
        return

    print(f"\n备份列表 ({len(archives)} 个):\n")
    for a in archives:
        mtime = datetime.fromtimestamp(a.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        size_mb = a.stat().st_size / (1024 * 1024)
        print(f"  {a.name}  |  {mtime}  |  {size_mb:.1f} MB")


def main() -> None:
    parser = argparse.ArgumentParser(description="数据库备份工具")
    parser.add_argument("--output", default="data/backups", help="备份输出目录")
    parser.add_argument("--keep", type=int, default=30, help="保留最近 N 个备份")
    parser.add_argument("--list", action="store_true", help="列出已有备份")
    args = parser.parse_args()

    if args.list:
        list_backups(args.output)
    else:
        print(f"开始备份到 {args.output}/ ...")
        backup_db(args.output, args.keep)
        print("完成")


if __name__ == "__main__":
    main()
