"""
批量数据导入脚本 —— 支持 CSV / JSON 格式批量导入患者、病历、就诊记录。

用法:
  # 导入单个 JSON 文件（格式见 data/examples/）
  python scripts/bulk_import.py data/patients.json

  # 导入单个 CSV 文件
  python scripts/bulk_import.py data/patients.csv

  # 导入目录下所有 .json / .csv 文件
  python scripts/bulk_import.py data/

  # 导入并自动生成知识切片
  python scripts/bulk_import.py data/patients.json --chunk

  # 导入，如果患者已存在则更新
  python scripts/bulk_import.py data/patients.json --update

  # 仅验证不写入数据库
  python scripts/bulk_import.py data/patients.json --dry-run

  # 增量模式 —— 只处理有变更的文件
  python scripts/bulk_import.py data/ --incremental

  # 查看增量跟踪状态
  python scripts/bulk_import.py . --tracker-status

支持的实体类型（通过文件名后缀或文件内 type 字段区分）:
  - patients:  患者主档 (patient)
  - records:   病历 (medical_record)
  - visits:    就诊记录 (visit_record)

文件格式（CSV）:
  # patients.csv — 列名固定
  hospital_id,patient_code,full_name,gender,birth_date,phone,allergy_history
  hospital-a,P001,张三,male,1980-01-01,13800138000,青霉素过敏

  # records.csv
  patient_code,record_type,title,department,diagnosis,treatment_plan
  P001,outpatient,高血压复诊,心内科,高血压2级,低盐饮食

  # visits.csv
  patient_code,visit_type,department,doctor_name,visit_summary
  P001,outpatient,心内科,王医生,血压控制良好
"""

import csv
import json
import os
import sys
import uuid
from collections import defaultdict
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.patient import Patient
from app.models.medical_record import MedicalRecord
from app.models.visit_record import VisitRecord
from app.services.memory_extraction_service import upsert_knowledge_chunk


# ── 导入结果报告 ──

class ImportReport:
    """Tracks import results across all entities."""

    def __init__(self):
        self.total_files = 0
        self.total_rows = 0
        self.succeeded = 0
        self.skipped_duplicates = 0
        self.failures: List[Dict[str, Any]] = []
        self.created_chunks = 0
        self.entity_counts = defaultdict(int)

    def add_success(self, entity_type: str):
        self.succeeded += 1
        self.entity_counts[entity_type] += 1

    def add_skip(self, entity_type: str, reason: str, row: dict):
        self.skipped_duplicates += 1
        self.failures.append({
            "type": entity_type,
            "reason": reason,
            "row": row,
        })

    def add_failure(self, entity_type: str, error: str, row: Optional[dict] = None):
        self.failures.append({
            "type": entity_type,
            "reason": str(error),
            "row": row or {},
        })

    def add_chunks(self, count: int):
        self.created_chunks += count

    def __str__(self) -> str:
        lines = [
            "=" * 50,
            " 批量导入报告",
            "=" * 50,
            f"  文件数:         {self.total_files}",
            f"  总行数:         {self.total_rows}",
            f"  成功导入:       {self.succeeded}",
            f"  跳过重复:       {self.skipped_duplicates}",
            f"  知识切片生成:   {self.created_chunks}",
            f"  失败:           {len(self.failures)}",
        ]
        if self.entity_counts:
            lines.append(f"  明细:           {dict(self.entity_counts)}")
        if self.failures:
            lines.append(f"\n  失败详情:")
            for i, f in enumerate(self.failures[:10], 1):
                lines.append(f"    {i}. [{f['type']}] {f['reason']}")
            if len(self.failures) > 10:
                lines.append(f"    ... 还有 {len(self.failures) - 10} 条失败")
        lines.append("=" * 50)
        return "\n".join(lines)


# ── 增量同步跟踪器 ──

IMPORT_TRACKER_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "import_tracker.json",
)


class ImportTracker:
    """Tracks file import state for incremental sync.

    Records the modification time (mtime) and import timestamp for each file.
    On incremental runs, skips files whose mtime hasn't changed.
    """

    def __init__(self, tracker_path: str = IMPORT_TRACKER_PATH):
        self.tracker_path = tracker_path
        self._data: Dict[str, dict] = self._load()

    def _load(self) -> dict:
        try:
            with open(self.tracker_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save(self):
        os.makedirs(os.path.dirname(self.tracker_path), exist_ok=True)
        with open(self.tracker_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def should_process(self, filepath: str) -> Tuple[bool, str]:
        """Check if a file should be processed.

        Returns (should_process, reason).
        """
        abs_path = os.path.abspath(filepath)
        try:
            current_mtime = os.path.getmtime(abs_path)
        except OSError:
            return True, "无法读取文件状态"

        record = self._data.get(abs_path)
        if record is None:
            return True, "新文件"
        if record.get("mtime") != current_mtime:
            return True, f"文件已修改 (上次导入: {record.get('imported_at', 'unknown')})"

        return False, f"文件无变更 (上次导入: {record.get('imported_at', 'unknown')}, {record.get('rows', 0)} 行)"

    def record_import(self, filepath: str, rows: int, succeeded: int, failed: int):
        """Record a successful import."""
        abs_path = os.path.abspath(filepath)
        try:
            current_mtime = os.path.getmtime(abs_path)
        except OSError:
            current_mtime = 0
        self._data[abs_path] = {
            "mtime": current_mtime,
            "imported_at": datetime.utcnow().isoformat(),
            "rows": rows,
            "succeeded": succeeded,
            "failed": failed,
        }
        self._save()

    def get_summary(self) -> str:
        """Return a summary of tracked imports."""
        if not self._data:
            return "  无历史导入记录"
        lines = [f"  已跟踪 {len(self._data)} 个文件:"]
        for path, record in sorted(self._data.items()):
            fname = os.path.basename(path)
            imported = record.get("imported_at", "?")[:19]
            rows = record.get("rows", 0)
            lines.append(f"    {fname}: {rows} 行, 导入于 {imported}")
        return "\n".join(lines)


# ── 文件探测与分析 ──

SUPPORTED_EXTENSIONS = {".json", ".csv"}

def _detect_entity_type_from_filename(filename: str) -> Optional[str]:
    """Detect entity type from filename prefix."""
    basename = os.path.basename(filename).lower()
    if basename.startswith("patient"):
        return "patient"
    if basename.startswith("record") or basename.startswith("medical"):
        return "medical_record"
    if basename.startswith("visit"):
        return "visit_record"
    return None


def _collect_files(path: str) -> List[str]:
    """Collect supported files from a path (file or directory)."""
    if os.path.isfile(path):
        ext = os.path.splitext(path)[1].lower()
        if ext in SUPPORTED_EXTENSIONS:
            return [path]
        raise ValueError(f"不支持的文件格式: {ext} (支持: {', '.join(SUPPORTED_EXTENSIONS)})")

    if os.path.isdir(path):
        files = []
        for fname in sorted(os.listdir(path)):
            if any(fname.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                files.append(os.path.join(path, fname))
        if not files:
            raise ValueError(f"目录 {path} 中没有找到支持的导入文件")
        return files

    raise FileNotFoundError(f"路径不存在: {path}")


def _load_json(filepath: str) -> List[dict]:
    """Load a JSON file containing an array of objects or a dict with a 'data' key."""
    with open(filepath, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in ("data", "items", "records", "patients"):
            if key in raw and isinstance(raw[key], list):
                return raw[key]
    raise ValueError(f"JSON 格式错误: 需要数组或包含 data/items/records 键的对象")


def _load_csv(filepath: str) -> List[dict]:
    """Load a CSV file as a list of dicts."""
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        raise ValueError(f"CSV 文件为空: {filepath}")
    return rows


def _load_rows(filepath: str) -> List[dict]:
    """Load rows from a JSON or CSV file."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".json":
        return _load_json(filepath)
    elif ext == ".csv":
        return _load_csv(filepath)
    raise ValueError(f"不支持的文件格式: {ext}")


# ── 字段校验与规范化 ──

REQUIRED_FIELDS = {
    "patient": ["hospital_id", "patient_code", "full_name"],
    "medical_record": ["patient_code", "record_type", "title"],
    "visit_record": ["patient_code", "visit_type", "department"],
}

TEXT_ARRAY_FIELDS = ["tags"]
DATE_FIELDS = {"birth_date", "record_date", "visit_date", "effective_from", "expires_at"}


def _validate_row(row: dict, entity_type: str) -> Optional[str]:
    """Validate required fields. Returns None if valid, error message if invalid."""
    required = REQUIRED_FIELDS.get(entity_type, [])
    missing = [f for f in required if not row.get(f, "").strip()]
    if missing:
        return f"缺少必填字段: {', '.join(missing)}"
    return None


def _normalize_date(value: Any) -> Optional[date]:
    """Normalize a date value."""
    if not value:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
        raise ValueError(f"无法解析日期: {value}")
    raise ValueError(f"日期类型不支持: {type(value)}")


def _normalize_datetime(value: Any) -> Optional[datetime]:
    """Normalize a datetime value."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(value.strip(), fmt)
            except ValueError:
                continue
        raise ValueError(f"无法解析日期时间: {value}")
    raise ValueError(f"日期时间类型不支持: {type(value)}")


def _clean_row(row: dict) -> dict:
    """Clean row: strip whitespace, remove empty string values."""
    cleaned = {}
    for k, v in row.items():
        if isinstance(v, str):
            v = v.strip()
            if v == "":
                v = None
        cleaned[k] = v
    return cleaned


# ── 导入器 ──

class PatientImporter:
    """Import patients from rows."""

    def __init__(self, db, update: bool = False, dry_run: bool = False):
        self.db = db
        self.update = update
        self.dry_run = dry_run

    def import_row(self, row: dict) -> Tuple[bool, str, Patient]:
        """Import a single patient row. Returns (success, message, patient_or_None)."""
        row = _clean_row(row)
        error = _validate_row(row, "patient")
        if error:
            return False, error, None

        # Check duplicate
        existing = (
            self.db.query(Patient)
            .filter(
                Patient.hospital_id == row["hospital_id"],
                Patient.patient_code == row["patient_code"],
            )
            .first()
        )
        if existing:
            if self.update:
                # Update fields
                for field in ("full_name", "gender", "phone", "address",
                              "allergy_history", "family_history", "notes"):
                    if row.get(field) is not None:
                        setattr(existing, field, row[field])
                if not self.dry_run:
                    self.db.commit()
                return True, f"已更新患者 {row['patient_code']}", existing
            return True, f"跳过重复患者 {row['patient_code']}", existing

        if self.dry_run:
            return True, f"[DRY-RUN] 将创建患者 {row['patient_code']}", None

        now = datetime.utcnow()
        patient = Patient(
            id=str(uuid.uuid4()),
            hospital_id=row["hospital_id"],
            patient_code=row["patient_code"],
            full_name=row["full_name"],
            gender=row.get("gender"),
            birth_date=_normalize_date(row.get("birth_date")),
            phone=row.get("phone"),
            address=row.get("address"),
            emergency_contact_name=row.get("emergency_contact_name"),
            emergency_contact_phone=row.get("emergency_contact_phone"),
            blood_type=row.get("blood_type"),
            allergy_history=row.get("allergy_history"),
            family_history=row.get("family_history"),
            notes=row.get("notes"),
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self.db.add(patient)
        self.db.commit()
        return True, f"已创建患者 {row['patient_code']}", patient


class MedicalRecordImporter:
    """Import medical records from rows. Patient must already exist."""

    def __init__(self, db, patient_map: Dict[str, Patient],
                 update: bool = False, dry_run: bool = False):
        self.db = db
        self.patient_map = patient_map
        self.update = update
        self.dry_run = dry_run

    def import_row(self, row: dict) -> Tuple[bool, str, Optional[MedicalRecord]]:
        row = _clean_row(row)
        error = _validate_row(row, "medical_record")
        if error:
            return False, error, None

        patient_code = row.pop("patient_code", "")
        patient = self.patient_map.get(patient_code)
        if not patient:
            return False, f"患者 {patient_code} 不存在，请先导入患者", None

        if self.dry_run:
            return True, f"[DRY-RUN] 将为 {patient_code} 创建病历", None

        now = datetime.utcnow()
        record = MedicalRecord(
            id=str(uuid.uuid4()),
            patient_id=patient.id,
            hospital_id=patient.hospital_id,
            record_type=row["record_type"],
            title=row["title"],
            department=row.get("department"),
            doctor_name=row.get("doctor_name"),
            chief_complaint=row.get("chief_complaint"),
            present_illness=row.get("present_illness"),
            diagnosis=row.get("diagnosis"),
            treatment_plan=row.get("treatment_plan"),
            medications=row.get("medications"),
            notes=row.get("notes"),
            record_date=_normalize_datetime(row.get("record_date")) or now,
            created_at=now,
            updated_at=now,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return True, f"已为 {patient_code} 创建病历: {record.title}", record


class VisitRecordImporter:
    """Import visit records from rows. Patient must already exist."""

    def __init__(self, db, patient_map: Dict[str, Patient],
                 update: bool = False, dry_run: bool = False):
        self.db = db
        self.patient_map = patient_map
        self.update = update
        self.dry_run = dry_run

    def import_row(self, row: dict) -> Tuple[bool, str, Optional[VisitRecord]]:
        row = _clean_row(row)
        error = _validate_row(row, "visit_record")
        if error:
            return False, error, None

        patient_code = row.pop("patient_code", "")
        patient = self.patient_map.get(patient_code)
        if not patient:
            return False, f"患者 {patient_code} 不存在，请先导入患者", None

        if self.dry_run:
            return True, f"[DRY-RUN] 将为 {patient_code} 创建就诊记录", None

        now = datetime.utcnow()
        visit = VisitRecord(
            id=str(uuid.uuid4()),
            patient_id=patient.id,
            hospital_id=patient.hospital_id,
            visit_type=row["visit_type"],
            department=row["department"],
            doctor_name=row.get("doctor_name"),
            campus=row.get("campus"),
            chief_complaint=row.get("chief_complaint"),
            visit_status=row.get("visit_status"),
            visit_summary=row.get("visit_summary"),
            follow_up_plan=row.get("follow_up_plan"),
            visit_date=_normalize_datetime(row.get("visit_date")) or now,
            created_at=now,
            updated_at=now,
        )
        self.db.add(visit)
        self.db.commit()
        self.db.refresh(visit)
        return True, f"已为 {patient_code} 创建就诊记录: {visit.department}", visit


# ── 知识切片自动生成 ──

def _build_knowledge_chunks_from_medical_record(db, record: MedicalRecord) -> int:
    """Generate knowledge chunks from a medical record."""
    count = 0
    texts = []

    # Diagnosis chunk
    if record.diagnosis:
        texts.append({
            "domain": "diagnosis",
            "title": f"{record.title} - 诊断",
            "chunk_text": f"患者诊断：{record.diagnosis}。治疗方案：{record.treatment_plan or '未记录'}",
            "source_type": "medical_record",
            "source_ref": record.id,
            "tags": "diagnosis, treatment",
            "confidence": 0.85,
        })

    # Medical history chunk
    if record.present_illness:
        texts.append({
            "domain": "medical_history",
            "title": f"{record.title} - 现病史",
            "chunk_text": record.present_illness,
            "source_type": "medical_record",
            "source_ref": record.id,
            "tags": "present_illness, medical_history",
            "confidence": 0.8,
        })

    # Medications chunk
    if record.medications:
        texts.append({
            "domain": "medication",
            "title": f"{record.title} - 用药",
            "chunk_text": f"用药方案：{record.medications}",
            "source_type": "medical_record",
            "source_ref": record.id,
            "tags": "medication, prescription",
            "confidence": 0.9,
        })

    for payload in texts:
        payload["hospital_id"] = record.hospital_id
        result = upsert_knowledge_chunk(db, payload=payload)
        if result:
            count += 1

    return count


def _build_knowledge_chunks_from_visit_record(db, visit: VisitRecord) -> int:
    """Generate knowledge chunks from a visit record."""
    count = 0

    if visit.visit_summary:
        payload = {
            "hospital_id": visit.hospital_id,
            "domain": "visit_summary",
            "title": f"{visit.visit_date.date() if visit.visit_date else ''} {visit.department}就诊",
            "chunk_text": visit.visit_summary,
            "source_type": "visit_record",
            "source_ref": visit.id,
            "tags": f"visit, {visit.department}, {visit.visit_type}",
            "confidence": 0.85,
        }
        result = upsert_knowledge_chunk(db, payload=payload)
        if result:
            count += 1

    if visit.follow_up_plan:
        payload = {
            "hospital_id": visit.hospital_id,
            "domain": "follow_up",
            "title": f"{visit.visit_date.date() if visit.visit_date else ''} 复诊计划",
            "chunk_text": f"复诊/随访计划：{visit.follow_up_plan}",
            "source_type": "visit_record",
            "source_ref": visit.id,
            "tags": "follow_up, plan",
            "confidence": 0.8,
        }
        result = upsert_knowledge_chunk(db, payload=payload)
        if result:
            count += 1

    return count


# ── 主逻辑 ──

def build_patient_map(db) -> Dict[str, Patient]:
    """Build a patient_code -> Patient map from the database."""
    patients = db.query(Patient).all()
    return {p.patient_code: p for p in patients}


def import_file(filepath: str, db, *,
                entity_type: Optional[str] = None,
                generate_chunks: bool = False,
                update: bool = False,
                dry_run: bool = False) -> ImportReport:
    """Import data from a single file.

    Args:
        filepath: Path to the file
        db: Database session
        entity_type: Override entity type. If None, detected from filename.
        generate_chunks: Generate knowledge chunks from imported records
        update: Update existing records instead of skipping
        dry_run: Validate only, don't write

    Returns:
        ImportReport with results
    """
    report = ImportReport()
    report.total_files = 1

    # Detect entity type
    if not entity_type:
        entity_type = _detect_entity_type_from_filename(filepath)

    # Load rows
    try:
        rows = _load_rows(filepath)
    except (ValueError, json.JSONDecodeError, csv.Error) as e:
        report.add_failure("file", f"文件读取失败: {e}")
        return report

    report.total_rows = len(rows)
    if not rows:
        return report

    # Build patient map for cross-references
    patient_map = build_patient_map(db)

    # Select importer
    if entity_type == "patient":
        importer = PatientImporter(db, update=update, dry_run=dry_run)
    elif entity_type == "medical_record":
        importer = MedicalRecordImporter(db, patient_map, update=update, dry_run=dry_run)
    elif entity_type == "visit_record":
        importer = VisitRecordImporter(db, patient_map, update=update, dry_run=dry_run)
    else:
        # Auto-detect from row content
        keys = set(rows[0].keys()) if rows else set()
        if {"hospital_id", "patient_code", "full_name"}.intersection(keys):
            importer = PatientImporter(db, update=update, dry_run=dry_run)
            entity_type = "patient"
        elif {"patient_code", "record_type", "title"}.intersection(keys):
            importer = MedicalRecordImporter(db, patient_map, update=update, dry_run=dry_run)
            entity_type = "medical_record"
        elif {"patient_code", "visit_type", "department"}.intersection(keys):
            importer = VisitRecordImporter(db, patient_map, update=update, dry_run=dry_run)
            entity_type = "visit_record"
        else:
            report.add_failure("file",
                f"无法自动识别实体类型 (字段: {list(keys)[:5]}...)。"
                f"使用文件名前缀约定或通过 --type 指定。")
            return report

    # Import each row
    for i, row in enumerate(rows):
        success, message, entity = importer.import_row(row)
        if success and entity is None:
            # Dry-run or duplicate skip
            if "跳过" in message or "重复" in message:
                report.add_skip(entity_type, message, row)
            else:
                report.add_success(entity_type)
        elif success and entity is not None:
            report.add_success(entity_type)
            if generate_chunks and not dry_run:
                chunk_count = 0
                if isinstance(entity, MedicalRecord):
                    chunk_count = _build_knowledge_chunks_from_medical_record(db, entity)
                elif isinstance(entity, VisitRecord):
                    chunk_count = _build_knowledge_chunks_from_visit_record(db, entity)
                if chunk_count:
                    report.add_chunks(chunk_count)
        else:
            report.add_failure(entity_type, message, row)

    return report


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="批量导入患者、病历、就诊记录数据",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/bulk_import.py data/patients.json
  python scripts/bulk_import.py data/patients.csv --chunk
  python scripts/bulk_import.py data/ --dry-run
  python scripts/bulk_import.py data/visits.csv --type visit_record
        """,
    )
    parser.add_argument("path", help="数据文件路径或目录路径")
    parser.add_argument("--type", choices=["patient", "medical_record", "visit_record"],
                        help="实体类型（默认由文件名自动识别）")
    parser.add_argument("--chunk", action="store_true",
                        help="导入后自动生成知识切片")
    parser.add_argument("--update", action="store_true",
                        help="如果患者已存在则更新（默认跳过）")
    parser.add_argument("--dry-run", action="store_true",
                        help="仅校验不写入数据库")
    parser.add_argument("--incremental", action="store_true",
                        help="增量模式：只处理有变更的文件（基于文件修改时间）")
    parser.add_argument("--tracker-status", action="store_true",
                        help="显示增量同步跟踪器状态")
    args = parser.parse_args()

    # Show tracker status if requested
    tracker = ImportTracker()
    if args.tracker_status:
        print("增量同步跟踪器状态:")
        print(tracker.get_summary())
        return

    # Collect files
    try:
        files = _collect_files(args.path)
    except (FileNotFoundError, ValueError) as e:
        print(f"错误: {e}")
        sys.exit(1)

    total_report = ImportReport()

    db = SessionLocal()
    try:
        for filepath in files:
            # Incremental check
            if args.incremental:
                should_process, reason = tracker.should_process(filepath)
                if not should_process:
                    print(f"  跳过 {os.path.basename(filepath)}: {reason}")
                    continue
                print(f"\n处理文件: {filepath} ({reason})")
            else:
                print(f"\n处理文件: {filepath}")

            report = import_file(
                filepath, db,
                entity_type=args.type,
                generate_chunks=args.chunk,
                update=args.update,
                dry_run=args.dry_run,
            )
            total_report.total_files += report.total_files
            total_report.total_rows += report.total_rows
            total_report.succeeded += report.succeeded
            total_report.skipped_duplicates += report.skipped_duplicates
            total_report.failures.extend(report.failures)
            total_report.created_chunks += report.created_chunks
            for k, v in report.entity_counts.items():
                total_report.entity_counts[k] += v

            for msg in report.failures[:3]:
                print(f"  ⚠ {msg['reason']}")

            # Record import for incremental tracking
            if not args.dry_run:
                tracker.record_import(
                    filepath,
                    rows=report.total_rows,
                    succeeded=report.succeeded,
                    failed=len(report.failures),
                )

    finally:
        db.close()

    print(f"\n{total_report}")
    if total_report.failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
