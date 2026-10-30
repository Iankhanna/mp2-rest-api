from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health():
    """Check that the health endpoint works."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": "1.0.0"
    }
    assert "x-request-id" in response.headers


def test_upload():
    """Check that a CSV file can be uploaded."""
    csv_content = b"student_id,score\n1,80\n2,90\n"

    response = client.post(
        "/upload",
        files={"file": ("test.csv", csv_content, "text/csv")}
    )

    assert response.status_code == 200
    data = response.json()

    assert data["filename"] == "test.csv"
    assert data["rows"] == 2
    assert data["columns"] == 2
    assert data["column_names"] == ["student_id", "score"]
    assert isinstance(data["id"], int)


def test_get_dataset():
    """Check that an uploaded dataset can be retrieved."""
    csv_content = b"student_id,score\n1,80\n2,90\n"

    upload_response = client.post(
        "/upload",
        files={"file": ("test.csv", csv_content, "text/csv")}
    )

    assert upload_response.status_code == 200
    dataset_id = upload_response.json()["id"]

    response = client.get(f"/datasets/{dataset_id}")

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == dataset_id
    assert data["total_rows"] == 2
    assert data["data"] == [
        {"student_id": 1, "score": 80},
        {"student_id": 2, "score": 90}
    ]


def test_process_dataset():
    """Check that processing removes duplicates and missing values."""
    csv_content = (
        b"student_id,score\n"
        b"1,80\n"
        b"2,90\n"
        b"2,90\n"
        b"3,\n"
        b"4,85\n"
    )

    upload_response = client.post(
        "/upload",
        files={"file": ("test.csv", csv_content, "text/csv")}
    )

    assert upload_response.status_code == 200
    dataset_id = upload_response.json()["id"]

    config = {
        "validation": {
            "required_columns": ["student_id", "score"],
            "numeric_columns": ["score"]
        },
        "processing": {
            "remove_duplicates": True,
            "missing": {"enabled": True, "axis": "rows"},
            "outliers": {"enabled": False}
        }
    }

    response = client.post(
        f"/datasets/{dataset_id}/process",
        json=config
    )

    assert response.status_code == 200
    report = response.json()

    assert report["id"] == dataset_id
    assert report["validation_rows_removed"] == 0
    assert report["cleaning_report"]["rows_before"] == 5
    assert report["cleaning_report"]["rows_after"] == 3
    assert report["cleaning_report"]["rows_removed"] == 2

    retrieved = client.get(f"/datasets/{dataset_id}")

    assert retrieved.status_code == 200
    assert retrieved.json()["total_rows"] == 3


def test_dataset_not_found():
    """Check that requesting a missing dataset returns 404."""
    response = client.get("/datasets/99999")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Dataset not found"
    }
    assert "x-request-id" in response.headers


def test_invalid_file_upload():
    """Check that uploading a non-CSV file returns 400."""
    response = client.post(
        "/upload",
        files={"file": ("notes.txt", b"hello world", "text/plain")}
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Only CSV files are supported"
    }
    assert "x-request-id" in response.headers


def test_missing_required_column():
    """Check that processing rejects missing required columns."""
    csv_content = b"student_id,score\n1,80\n2,90\n"

    upload_response = client.post(
        "/upload",
        files={"file": ("test.csv", csv_content, "text/csv")}
    )

    dataset_id = upload_response.json()["id"]

    config = {
        "validation": {
            "required_columns": ["student_id", "score", "age"],
            "numeric_columns": ["score"]
        }
    }

    response = client.post(
        f"/datasets/{dataset_id}/process",
        json=config
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Required column missing: age"
    }


def test_invalid_numeric_values():
    """Check that invalid numeric values are removed."""
    csv_content = (
        b"student_id,score\n"
        b"1,80\n"
        b"2,unknown\n"
        b"3,90\n"
    )

    upload_response = client.post(
        "/upload",
        files={"file": ("test.csv", csv_content, "text/csv")}
    )

    assert upload_response.status_code == 200
    dataset_id = upload_response.json()["id"]

    config = {
        "validation": {
            "required_columns": ["student_id", "score"],
            "numeric_columns": ["score"]
        }
    }

    response = client.post(
        f"/datasets/{dataset_id}/process",
        json=config
    )

    assert response.status_code == 200
    assert response.json()["validation_rows_removed"] == 1

    retrieved = client.get(f"/datasets/{dataset_id}")

    assert retrieved.status_code == 200
    assert retrieved.json()["total_rows"] == 2


def test_dataset_limit():
    """Check that the limit parameter restricts returned rows."""
    csv_content = (
        b"student_id,score\n"
        b"1,80\n"
        b"2,90\n"
        b"3,85\n"
    )

    upload_response = client.post(
        "/upload",
        files={"file": ("test.csv", csv_content, "text/csv")}
    )

    assert upload_response.status_code == 200
    dataset_id = upload_response.json()["id"]

    response = client.get(f"/datasets/{dataset_id}?limit=2")

    assert response.status_code == 200
    data = response.json()

    assert data["total_rows"] == 3
    assert len(data["data"]) == 2
    assert data["data"] == [
        {"student_id": 1, "score": 80},
        {"student_id": 2, "score": 90}
    ]


def test_invalid_dataset_limit():
    """Check that a negative limit is rejected."""
    response = client.get("/datasets/1?limit=-1")
    assert response.status_code == 422


# REQUIRED ASSIGNMENT TESTS

def test_upload_csv(client, sample_csv_bytes):
    """Check that the provided sample CSV uploads correctly."""
    response = client.post(
        "/upload",
        files={"file": ("sample_data.csv", sample_csv_bytes, "text/csv")}
    )

    assert response.status_code == 200
    data = response.json()

    assert data["rows"] == 6
    assert data["columns"] == 2
    assert isinstance(data["id"], int)
    assert data["id"] > 0


def test_process_and_retrieve(client, uploaded_dataset_id, processing_body):
    """Check that processing cleans the sample dataset correctly."""
    response = client.post(
        f"/datasets/{uploaded_dataset_id}/process",
        json=processing_body
    )

    assert response.status_code == 200
    report = response.json()

    assert report["validation_rows_removed"] == 1
    assert report["cleaning_report"]["rows_before"] == 5
    assert report["cleaning_report"]["rows_after"] == 3
    assert report["cleaning_report"]["rows_removed"] == 2

    retrieved = client.get(f"/datasets/{uploaded_dataset_id}")

    assert retrieved.status_code == 200
    data = retrieved.json()

    assert data["total_rows"] == 3
    assert data["data"] == [
        {"student_id": 1, "score": 80},
        {"student_id": 2, "score": 90},
        {"student_id": 5, "score": 85}
    ]


def test_retrieve_missing_dataset(client):
    """Check that retrieving a nonexistent dataset returns 404."""
    response = client.get("/datasets/999999")
    assert response.status_code == 404
