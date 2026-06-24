-- 001_baseline.sql — 初始基线迁移（对应 schema.py 中所有 v2 表）
-- 此文件为参考记录；所有表已通过 schema.py 的 CREATE TABLE IF NOT EXISTS 创建。
-- 后续迁移（002_xxx.sql, 003_xxx.sql）将在此基线之上执行增量变更。

-- 示例增量迁移 SQL：
-- ALTER TABLE expense_reports ADD COLUMN receipt_url TEXT;
-- CREATE INDEX IF NOT EXISTS idx_expense_type ON expense_reports(expense_type);
