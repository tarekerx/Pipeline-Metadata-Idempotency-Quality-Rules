# Signup Data Ingestion Pipeline

A small learning project that demonstrates how to handle bad data in a real data pipeline: how to **quarantine** it, **why** and **when**, what to expect, and how to stay flexible.

In this project I wanted to learn by doing — I focused on the use cases, refined the code several times, and polished it with the help of AI (do not worry, he will not replace me 😄). It turned out to be a very good practice, even for a small project like this.

## What the pipeline does

1. **Landing** — picks up CSV files dropped in `landing_folder/`
2. **Validation** — classifies each row as `VALID`, `FIXED`, or `QUARANTINE`:
   - Missing `id` → **quarantined** (bad data should not enter the database)
   - Missing `name` → auto-fixed to `"Unknown"`
   - Names are trimmed and title-cased (`alice smith` → `Alice Smith`)
3. **Idempotent writes** — if a user `id` already exists, the row is updated instead of duplicated, so re-running the pipeline is safe
4. **Quarantine** — rejected rows are logged to `quarantine_folder/quarantined_rows.csv` with their source file
5. **Archive** — processed files are moved to `archive_folder/` so they aren't picked up again
6. **Audit logging** — every run records metadata in the `pipeline_runs` table (run id, timings, record counts, status, errors)

## Project structure

```
├── main.py                     # The pipeline
├── gen.py                      # Test-data generator
├── landing_folder/             # Drop CSV files here
├── archive_folder/             # Processed files land here
├── quarantine_folder/          # Rejected rows are logged here
└── signup_pipeline.db          # SQLite database (users + pipeline_runs)
```

## How to run

```bash
python gen.py    # creates a test CSV with valid, fixable, and bad rows
python main.py   # runs the pipeline
```

## Key takeaways

- **Quarantine, don't delete** — bad rows are kept for inspection, not silently dropped
- **Idempotency** — re-running on the same data updates instead of duplicating
- **Audit metadata** — every run is traceable: what was read, inserted, quarantined, and skipped
