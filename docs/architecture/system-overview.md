# System Overview

## Purpose

TPM Cockpit is a local web application for managing TPM-specific operational work.

The application should help a TPM maintain visibility across programs, work items, risks, dependencies, decisions, stakeholders, and notes.

## Initial Architecture

The initial system uses:

- Python backend
- FastAPI API
- SQLite local database
- SQLAlchemy data models
- Alembic migrations
- Browser-based user interface

## High-Level Flow

```text
Browser UI
  → FastAPI backend
  → SQLite database
  → local data folder