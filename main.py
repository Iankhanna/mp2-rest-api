import io
import json
import logging
import pandas as pd

from src.middleware import RequestLoggingMiddleware
from pathlib import Path
from fastapi import FastAPI, File, HTTPException, Query, UploadFile

from src import DatasetInfo, DatasetStorage, HealthResponse, setup_logging
from src.models import ProcessConfig, ProcessingReport
from data_pipeline import (
    process_data,
    validate_dataframe,
    create_cleaning_report,
)

setup_logging(verbose=True)
logger = logging.getLogger(__name__)


app = FastAPI(title="Data Processing API", version="1.0.0")

app.add_middleware(RequestLoggingMiddleware)

storage = DatasetStorage()


@app.get("/health", response_model=HealthResponse)
def health_check():
    """Return the application status and version."""
    return {
        "status": "ok",
        "version": "1.0.0"
    }


@app.post("/upload", response_model=DatasetInfo)
async def upload_dataset(file: UploadFile = File(...)):
    """Read and store a CSV upload."""

    extension = Path(file.filename or "").suffix.lower()

    if extension != ".csv":
        logger.warning(f"Unsupported file format: {extension}")
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are supported"
        )

    try:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))

    except (
        pd.errors.EmptyDataError,
        pd.errors.ParserError,
        UnicodeDecodeError
    ):
        logger.warning("Could not read uploaded CSV file")
        raise HTTPException(
            status_code=400,
            detail="Could not read CSV file"
        )

    dataset_id = storage.save(df, file.filename)

    logger.info(
        f"Uploaded dataset: id={dataset_id}, "
        f"filename={file.filename}, rows={len(df)}"
    )

    return storage.get_metadata(dataset_id)


@app.get("/datasets/{dataset_id}")
def get_dataset(
    dataset_id: int,
    limit: int = Query(default=100, ge=1)
):
    """Return up to limit rows from a stored dataset."""

    df = storage.get(dataset_id)

    if df is None:
        logger.warning(f"Dataset not found: id={dataset_id}")
        raise HTTPException(
            status_code=404,
            detail="Dataset not found"
        )

    records = json.loads(
        df.head(limit).to_json(orient="records")
    )

    logger.info(
        f"Retrieved dataset: id={dataset_id}, rows={len(records)}"
    )

    return {
        "id": dataset_id,
        "data": records,
        "total_rows": len(df)
    }


@app.post(
    "/datasets/{dataset_id}/process",
    response_model=ProcessingReport
)
def process_dataset(dataset_id: int, config: ProcessConfig):
    """Validate and clean a stored dataset."""

    df = storage.get(dataset_id)

    if df is None:
        logger.warning(f"Dataset not found: id={dataset_id}")
        raise HTTPException(
            status_code=404,
            detail="Dataset not found"
        )

    validation = config.validation

    missing_numeric = [
        col for col in validation.numeric_columns
        if col not in df.columns
    ]

    if missing_numeric:
        raise HTTPException(
            status_code=400,
            detail=f"Numeric columns not found: {missing_numeric}"
        )

    original_rows = len(df)

    try:
        validated_df = validate_dataframe(
            df.copy(),
            validation.required_columns,
            validation.numeric_columns
        )

    except ValueError as e:
        logger.warning(f"Dataset validation failed: {e}")
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    validation_rows_removed = original_rows - len(validated_df)

    try:
        cleaned_df = process_data(
            validated_df.copy(),
            config.model_dump()
        )

    except ValueError as e:
        logger.warning(f"Dataset processing failed: {e}")
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    cleaning_report = create_cleaning_report(
        validated_df,
        cleaned_df
    )

    storage.update(dataset_id, cleaned_df)

    logger.info(
        f"Processed dataset: id={dataset_id}, "
        f"rows_before={original_rows}, "
        f"rows_after={len(cleaned_df)}"
    )

    return {
        "id": dataset_id,
        "validation_rows_removed": validation_rows_removed,
        "cleaning_report": cleaning_report
    }