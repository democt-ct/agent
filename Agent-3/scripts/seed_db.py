"""种子数据初始化脚本 — 将 mock 数据写入 SQLite 数据库。

用法:
    python scripts/seed_db.py                  # 默认 dev 环境 → data/dev.db
    python scripts/seed_db.py --env production # 生产环境 → data/enterprise.db
    python scripts/seed_db.py --reset          # 删除旧库后重建

环境隔离:
    APP_ENV=dev      → data/dev.db
    APP_ENV=production → data/enterprise.db
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> None:
    parser = argparse.ArgumentParser(description="种子数据初始化")
    parser.add_argument("--env", default="dev", choices=["dev", "production"],
                        help="目标环境 (默认 dev)")
    parser.add_argument("--reset", action="store_true",
                        help="删除已有数据库后重建")
    parser.add_argument("--dry-run", action="store_true",
                        help="仅显示将要执行的操作，不实际写入")
    args = parser.parse_args()

    # 设置环境变量，连接模块据此选择 DB 路径
    os.environ["APP_ENV"] = args.env

    from src.tools.db.connection import get_db_path

    db_path = get_db_path()
    print(f"环境: {args.env}")
    print(f"数据库: {db_path}")

    if args.dry_run:
        print("(dry-run 模式，不执行实际操作)")
        return

    if args.reset and db_path.exists():
        db_path.unlink()
        print(f"已删除旧数据库: {db_path}")

    # 延迟导入，确保环境变量已设置
    from src.tools.db import bootstrap_company_workspace

    print("正在初始化数据库...")
    bootstrap_company_workspace()
    print(f"✅ 种子数据已写入 {db_path}")


if __name__ == "__main__":
    main()
