"""Tests for the bulk import script."""

import os
import tempfile

import pytest

from scripts.bulk_import import (
    ImportReport,
    ImportTracker,
    PatientImporter,
    MedicalRecordImporter,
    _clean_row,
    _collect_files,
    _detect_entity_type_from_filename,
    _load_csv,
    _load_json,
    _normalize_date,
    _validate_row,
)
from app.schemas.patient import PatientCreate
from app.services.patient_service import create_patient


class TestHelpers:
    def test_detect_entity_type(self):
        assert _detect_entity_type_from_filename("patients.json") == "patient"
        assert _detect_entity_type_from_filename("records.csv") == "medical_record"
        assert _detect_entity_type_from_filename("medical_records.json") == "medical_record"
        assert _detect_entity_type_from_filename("visits.csv") == "visit_record"
        assert _detect_entity_type_from_filename("unknown.txt") is None

    def test_clean_row(self):
        row = {"full_name": "  张三  ", "phone": "  13800138000  ", "empty_field": ""}
        cleaned = _clean_row(row)
        assert cleaned["full_name"] == "张三"
        assert cleaned["phone"] == "13800138000"
        assert cleaned["empty_field"] is None

    def test_validate_row(self):
        assert _validate_row(
            {"hospital_id": "h1", "patient_code": "P1", "full_name": "测试"},
            "patient",
        ) is None
        error = _validate_row(
            {"hospital_id": "h1"},
            "patient",
        )
        assert error is not None
        assert "patient_code" in error
        assert "full_name" in error

    def test_normalize_date(self):
        from datetime import date
        assert _normalize_date("2024-01-15") == date(2024, 1, 15)
        assert _normalize_date("2024/01/15") == date(2024, 1, 15)
        assert _normalize_date(None) is None
        with pytest.raises(ValueError):
            _normalize_date("not-a-date")


class TestCollectFiles:
    def test_single_file(self):
        path = os.path.join(os.path.dirname(__file__), "..", "data", "examples", "patients.example.json")
        files = _collect_files(path)
        assert len(files) == 1

    def test_directory(self):
        path = os.path.join(os.path.dirname(__file__), "..", "data", "examples")
        files = _collect_files(path)
        assert len(files) >= 2  # at least .json and .csv

    def test_unsupported_extension(self):
        with pytest.raises(ValueError, match="不支持的文件格式"):
            # Use an existing file with unsupported extension
            _collect_files("AGENTS.md")


class TestLoadRows:
    def test_load_json(self):
        path = os.path.join(os.path.dirname(__file__), "..", "data", "examples", "patients.example.json")
        rows = _load_json(path)
        assert len(rows) == 2
        assert rows[0]["patient_code"] == "BULK001"

    def test_load_csv(self):
        path = os.path.join(tempfile.gettempdir(), "test_import_csv.tmp")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("patient_code,record_type,title\nP001,outpatient,测试\n")
            rows = _load_csv(path)
            assert len(rows) == 1
            assert rows[0]["patient_code"] == "P001"
        finally:
            if os.path.exists(path):
                os.unlink(path)


class TestPatientImporter:
    def test_import_patient_success(self, db_session):
        importer = PatientImporter(db_session, update=False, dry_run=False)
        row = {
            "hospital_id": "hosp-import",
            "patient_code": "IMP001",
            "full_name": "导入测试",
            "gender": "male",
            "phone": "13800001111",
        }
        success, message, patient = importer.import_row(row)
        assert success is True
        assert patient is not None
        assert patient.full_name == "导入测试"

    def test_skip_duplicate(self, db_session):
        importer = PatientImporter(db_session, update=False, dry_run=False)
        row = {
            "hospital_id": "hosp-import",
            "patient_code": "IMP002",
            "full_name": "重复测试",
        }
        importer.import_row(row)
        # Second import should skip
        success, message, patient = importer.import_row(row)
        assert success is True
        assert "跳过" in message

    def test_update_existing(self, db_session):
        importer = PatientImporter(db_session, update=True, dry_run=False)
        row = {
            "hospital_id": "hosp-import",
            "patient_code": "IMP003",
            "full_name": "原名",
        }
        _, _, patient = importer.import_row(row)

        # Update
        row["full_name"] = "新名字"
        success, message, patient = importer.import_row(row)
        assert success is True
        assert "更新" in message
        assert patient.full_name == "新名字"

    def test_dry_run(self, db_session):
        importer = PatientImporter(db_session, update=False, dry_run=True)
        row = {
            "hospital_id": "hosp-import",
            "patient_code": "IMP004",
            "full_name": "干跑测试",
        }
        success, message, patient = importer.import_row(row)
        assert success is True
        assert "DRY-RUN" in message
        # Verify not in DB
        from app.models.patient import Patient
        existing = db_session.query(Patient).filter(Patient.patient_code == "IMP004").first()
        assert existing is None

    def test_missing_required_field(self, db_session):
        importer = PatientImporter(db_session, update=False, dry_run=False)
        row = {"hospital_id": "hosp-import"}  # missing patient_code, full_name
        success, message, patient = importer.import_row(row)
        assert success is False
        assert "缺少" in message

    def test_import_with_all_fields(self, db_session):
        importer = PatientImporter(db_session, update=False, dry_run=False)
        row = {
            "hospital_id": "hosp-all",
            "patient_code": "ALL001",
            "full_name": "完整测试",
            "gender": "female",
            "birth_date": "1990-06-15",
            "phone": "13900009999",
            "address": "测试地址",
            "emergency_contact_name": "紧急联系人",
            "emergency_contact_phone": "13900008888",
            "blood_type": "O",
            "allergy_history": "磺胺过敏",
            "family_history": "母亲糖尿病",
            "notes": "备注信息",
        }
        success, _, patient = importer.import_row(row)
        assert success is True
        assert patient.blood_type == "O"
        assert patient.allergy_history == "磺胺过敏"
        assert patient.emergency_contact_name == "紧急联系人"


class TestMedicalRecordImporter:
    def test_create_record(self, db_session):
        # Create patient first
        patient = create_patient(db_session, PatientCreate(
            hospital_id="hosp-mr", patient_code="MR001", full_name="病历测试患者",
        ))
        patient_map = {"MR001": patient}

        importer = MedicalRecordImporter(db_session, patient_map, dry_run=False)
        row = {
            "patient_code": "MR001",
            "record_type": "outpatient",
            "title": "测试病历",
            "department": "心内科",
            "diagnosis": "高血压2级",
        }
        success, message, record = importer.import_row(row)
        assert success is True
        assert record.diagnosis == "高血压2级"

    def test_patient_not_found(self, db_session):
        importer = MedicalRecordImporter(db_session, {}, dry_run=False)
        success, message, _ = importer.import_row({
            "patient_code": "NONEXIST",
            "record_type": "outpatient",
            "title": "测试",
        })
        assert success is False
        assert "不存在" in message


# ── Knowledge Chunk Generation ──

class TestKnowledgeChunkGeneration:
    def test_chunks_from_medical_record(self, db_session):
        """Verify that importing a medical record with --chunk generates chunks."""
        from app.models.memory_knowledge_chunk import MemoryKnowledgeChunk
        from app.schemas.patient import PatientCreate
        from app.services.patient_service import create_patient

        patient = create_patient(db_session, PatientCreate(
            hospital_id="hosp-chunk", patient_code="CHK001", full_name="切片测试",
        ))

        # Create a medical record with full data
        from app.services.patient_service import create_medical_record
        from app.schemas.medical_record import MedicalRecordCreate
        record = create_medical_record(db_session, patient.id, MedicalRecordCreate(
            record_type="outpatient",
            title="切片测试病历",
            department="心内科",
            diagnosis="高血压2级",
            present_illness="头晕两月，血压升高",
            treatment_plan="低盐饮食+药物治疗",
            medications="缬沙坦80mg",
        ))

        # Generate chunks
        from scripts.bulk_import import _build_knowledge_chunks_from_medical_record
        count = _build_knowledge_chunks_from_medical_record(db_session, record)
        assert count >= 1  # at least diagnosis chunk

        # Verify chunks exist in DB
        chunks = db_session.query(MemoryKnowledgeChunk).filter(
            MemoryKnowledgeChunk.source_ref == record.id
        ).all()
        assert len(chunks) > 0
        assert any("诊断" in c.chunk_text for c in chunks)

    def test_chunks_from_visit_record(self, db_session):
        """Verify that importing a visit record with --chunk generates chunks."""
        from app.models.memory_knowledge_chunk import MemoryKnowledgeChunk
        from app.schemas.patient import PatientCreate
        from app.schemas.visit_record import VisitRecordCreate
        from app.services.patient_service import create_patient, create_visit_record

        patient = create_patient(db_session, PatientCreate(
            hospital_id="hosp-chunk", patient_code="CHK002", full_name="就诊切片测试",
        ))

        visit = create_visit_record(db_session, patient.id, VisitRecordCreate(
            visit_type="outpatient",
            department="内分泌科",
            visit_summary="血糖控制良好，继续当前方案",
            follow_up_plan="三个月后复诊",
        ))

        from scripts.bulk_import import _build_knowledge_chunks_from_visit_record
        count = _build_knowledge_chunks_from_visit_record(db_session, visit)
        assert count >= 1

        chunks = db_session.query(MemoryKnowledgeChunk).filter(
            MemoryKnowledgeChunk.source_ref == visit.id
        ).all()
        assert len(chunks) > 0


# ── 增量同步跟踪器 ──

class TestImportTracker:
    def test_tracker_new_file(self, tmp_path):
        """A file not yet tracked should be processed."""
        tracker_path = tmp_path / "tracker.json"
        tracker = ImportTracker(str(tracker_path))

        filepath = tmp_path / "test.json"
        filepath.write_text("[]")
        should, reason = tracker.should_process(str(filepath))
        assert should is True
        assert "新文件" in reason

    def test_tracker_unchanged_file(self, tmp_path):
        """A file with same mtime should be skipped."""
        tracker_path = tmp_path / "tracker.json"
        tracker = ImportTracker(str(tracker_path))

        filepath = tmp_path / "test.json"
        filepath.write_text("[1]")
        mtime = os.path.getmtime(str(filepath))

        # Record import
        tracker.record_import(str(filepath), rows=10, succeeded=10, failed=0)

        should, reason = tracker.should_process(str(filepath))
        assert should is False
        assert "无变更" in reason

    def test_tracker_changed_file(self, tmp_path):
        """A file with changed mtime should be re-processed."""
        tracker_path = tmp_path / "tracker.json"
        tracker = ImportTracker(str(tracker_path))

        filepath = tmp_path / "test.json"
        filepath.write_text("[1]")

        # Record import
        tracker.record_import(str(filepath), rows=10, succeeded=10, failed=0)

        # Modify the file — ensure mtime changes on all platforms
        import time
        time.sleep(0.1)
        filepath.write_text("[1, 2]")
        # Force mtime update
        new_mtime = time.time()
        os.utime(str(filepath), (new_mtime, new_mtime))

        should, reason = tracker.should_process(str(filepath))
        assert should is True, f"Expected file to be re-processed, got reason: {reason}"
        assert "文件已修改" in reason

    def test_tracker_persistence(self, tmp_path):
        """Tracker data should persist to disk."""
        tracker_path = tmp_path / "persist.json"

        # First instance records import
        t1 = ImportTracker(str(tracker_path))
        filepath = tmp_path / "data.json"
        filepath.write_text("[1]")
        t1.record_import(str(filepath), rows=5, succeeded=5, failed=0)

        # Second instance should read the saved data
        t2 = ImportTracker(str(tracker_path))
        should, _ = t2.should_process(str(filepath))
        assert should is False  # unchanged

    def test_tracker_summary_empty(self):
        tracker = ImportTracker("/tmp/nonexistent-tracker.json")
        summary = tracker.get_summary()
        assert "无历史" in summary

    def test_tracker_record_and_summary(self, tmp_path):
        tracker_path = tmp_path / "summary.json"
        tracker = ImportTracker(str(tracker_path))
        filepath = tmp_path / "data.json"
        filepath.write_text("[]")
        tracker.record_import(str(filepath), rows=5, succeeded=3, failed=1)

        summary = tracker.get_summary()
        assert "data.json" in summary
        assert "5 行" in summary



class TestImportReport:
    def test_report_formatting(self):
        report = ImportReport()
        report.total_files = 2
        report.total_rows = 10
        report.succeeded = 8
        report.skipped_duplicates = 1
        report.created_chunks = 12
        report.entity_counts["patient"] = 5
        report.entity_counts["medical_record"] = 3

        output = str(report)
        assert "成功导入:       8" in output
        assert "跳过重复:       1" in output
        assert "知识切片生成:   12" in output
        assert "失败:           0" in output
