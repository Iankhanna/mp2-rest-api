# MP2 Part 2 — Data Processing REST API

A FastAPI application for uploading, validating, cleaning, and retrieving CSV datasets. The project integrates the data processing pipeline developed in MP1.

## Features

- Upload CSV datasets using POST /upload
- Retrieve stored datasets using GET /datasets/{dataset_id}
- Validate and clean datasets using POST /datasets/{dataset_id}/process
- Remove duplicate rows, handle missing values, and optionally remove outliers
- Return validation and cleaning reports
- Log requests with request IDs and processing durations

## Installation

Install dependencies:

pip install -r requirements.txt

## Running the API

uvicorn main:app --reload

Open http://127.0.0.1:8000/docs to test the endpoints.

## Running Tests

python -m pytest -v

## Project Structure

- main.py — FastAPI endpoints
- src/models.py — Pydantic models
- src/storage.py — In-memory dataset storage
- src/middleware.py — Request logging middleware
- data_pipeline/ — Reused MP1 data processing code
- tests/ — Automated API tests
- fixtures/ — Sample CSV data
