"""Quick verification that the test infrastructure works."""

from app.models.patient import Patient


def test_database_connection(db_session):
    """Verify we can connect to the test database and perform a query."""
    # Verify the patients table exists and is queryable
    result = db_session.execute(
        Patient.__table__.select().limit(1)
    )
    rows = result.fetchall()
    # Table should exist — may or may not have data from other tests
    assert isinstance(rows, list)


def test_app_health(client):
    """Verify the FastAPI app can start and serve health check."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
