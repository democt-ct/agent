"""Integration tests for the FastAPI endpoints via TestClient."""


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_detailed_health_check(client):
    response = client.get("/health/detailed")
    assert response.status_code == 200


class TestPatientAPI:
    def test_create_patient(self, client):
        payload = {
            "hospital_id": "hosp-api",
            "patient_code": "API001",
            "full_name": "API测试患者",
            "phone": "13800138001",
            "gender": "female",
        }
        response = client.post("/api/v1/patients", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["full_name"] == "API测试患者"
        assert data["patient_code"] == "API001"
        assert "id" in data

    def test_create_duplicate_patient(self, client):
        payload = {
            "hospital_id": "hosp-api",
            "patient_code": "DUP001",
            "full_name": "重复患者",
        }
        client.post("/api/v1/patients", json=payload)
        response = client.post("/api/v1/patients", json=payload)
        assert response.status_code == 409

    def test_list_patients(self, client):
        response = client.get("/api/v1/patients")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_patient_by_id(self, client):
        # Create
        create_resp = client.post("/api/v1/patients", json={
            "hospital_id": "hosp-api",
            "patient_code": "GET001",
            "full_name": "查询测试",
        })
        patient_id = create_resp.json()["id"]

        # Get
        response = client.get(f"/api/v1/patients/{patient_id}")
        assert response.status_code == 200
        assert response.json()["full_name"] == "查询测试"

    def test_get_patient_not_found(self, client):
        response = client.get("/api/v1/patients/nonexistent-id")
        assert response.status_code == 404

    def test_update_patient(self, client):
        create_resp = client.post("/api/v1/patients", json={
            "hospital_id": "hosp-api",
            "patient_code": "UPD001",
            "full_name": "原名",
        })
        patient_id = create_resp.json()["id"]

        response = client.put(f"/api/v1/patients/{patient_id}", json={
            "full_name": "新名字",
        })
        assert response.status_code == 200
        assert response.json()["full_name"] == "新名字"

    def test_delete_patient(self, client):
        create_resp = client.post("/api/v1/patients", json={
            "hospital_id": "hosp-api",
            "patient_code": "DEL001",
            "full_name": "待删除",
        })
        patient_id = create_resp.json()["id"]

        response = client.delete(f"/api/v1/patients/{patient_id}")
        assert response.status_code == 200

        # Verify deletion
        get_resp = client.get(f"/api/v1/patients/{patient_id}")
        assert get_resp.status_code == 404


class TestMedicalRecordAPI:
    def test_crud_flow(self, client):
        # Create patient
        patient_resp = client.post("/api/v1/patients", json={
            "hospital_id": "hosp-api",
            "patient_code": "MR001",
            "full_name": "病历测试",
        })
        pid = patient_resp.json()["id"]

        # Create medical record
        mr_payload = {
            "record_type": "outpatient",
            "title": "高血压复诊",
            "department": "心内科",
            "diagnosis": "高血压2级",
        }
        mr_resp = client.post(f"/api/v1/patients/{pid}/medical-records", json=mr_payload)
        assert mr_resp.status_code == 201
        mr_id = mr_resp.json()["id"]

        # List medical records
        list_resp = client.get(f"/api/v1/patients/{pid}/medical-records")
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1

        # Get single record
        get_resp = client.get(f"/api/v1/patients/{pid}/medical-records/{mr_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["diagnosis"] == "高血压2级"

        # Update record
        upd_resp = client.put(
            f"/api/v1/patients/{pid}/medical-records/{mr_id}",
            json={"diagnosis": "高血压1级"},
        )
        assert upd_resp.status_code == 200
        assert upd_resp.json()["diagnosis"] == "高血压1级"

        # Delete record
        del_resp = client.delete(f"/api/v1/patients/{pid}/medical-records/{mr_id}")
        assert del_resp.status_code == 200

        # Verify deleted
        get_resp = client.get(f"/api/v1/patients/{pid}/medical-records/{mr_id}")
        assert get_resp.status_code == 404


class TestVisitRecordAPI:
    def test_crud_flow(self, client):
        patient_resp = client.post("/api/v1/patients", json={
            "hospital_id": "hosp-api",
            "patient_code": "VR001",
            "full_name": "就诊测试",
        })
        pid = patient_resp.json()["id"]

        # Create
        vr_payload = {
            "visit_type": "outpatient",
            "department": "心内科",
            "doctor_name": "王医生",
        }
        vr_resp = client.post(f"/api/v1/patients/{pid}/visits", json=vr_payload)
        assert vr_resp.status_code == 201
        vr_id = vr_resp.json()["id"]

        # List
        list_resp = client.get(f"/api/v1/patients/{pid}/visits")
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1

        # Get
        get_resp = client.get(f"/api/v1/patients/{pid}/visits/{vr_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["doctor_name"] == "王医生"

        # Update
        upd_resp = client.put(
            f"/api/v1/patients/{pid}/visits/{vr_id}",
            json={"visit_summary": "就诊摘要已更新"},
        )
        assert upd_resp.status_code == 200
        assert upd_resp.json()["visit_summary"] == "就诊摘要已更新"

        # Delete
        del_resp = client.delete(f"/api/v1/patients/{pid}/visits/{vr_id}")
        assert del_resp.status_code == 200
        get_resp = client.get(f"/api/v1/patients/{pid}/visits/{vr_id}")
        assert get_resp.status_code == 404


class TestProfileAPI:
    def test_get_memory_profile(self, client):
        patient_resp = client.post("/api/v1/patients", json={
            "hospital_id": "hosp-api",
            "patient_code": "PROF001",
            "full_name": "画像测试",
        })
        pid = patient_resp.json()["id"]

        # Add some records
        client.post(f"/api/v1/patients/{pid}/medical-records", json={
            "record_type": "outpatient",
            "title": "测试病历",
            "department": "心内科",
            "diagnosis": "测试诊断",
        })
        client.post(f"/api/v1/patients/{pid}/visits", json={
            "visit_type": "outpatient",
            "department": "心内科",
        })

        # Get profile
        response = client.get(f"/api/v1/memory/profile?patient_id={pid}")
        assert response.status_code == 200
        data = response.json()
        assert data["patient"]["full_name"] == "画像测试"
        assert len(data["medical_records"]) == 1
        assert len(data["visit_records"]) == 1
