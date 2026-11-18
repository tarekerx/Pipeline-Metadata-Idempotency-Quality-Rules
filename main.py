import sqlite3
import datetime
import uuid
import csv
from pathlib import Path

# Define paths and configuration names
LANDING_FOLDER = Path("./landing_folder")
ARCHIVE_FOLDER = Path("./archive_folder")
QUARANTINE_FOLDER = Path("./quarantine_folder")
DB_NAME = "signup_pipeline.db"
METADATA_TABLE = "pipeline_runs"


def initialize_database():
    """Initializes the SQLite database and creates tables."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    create_users_table_sql = """
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT,
        signup_date TEXT
    )
    """
    
    create_audit_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {METADATA_TABLE} (
        run_id TEXT PRIMARY KEY,
        job_name TEXT,
        start_time TEXT,
        end_time TEXT,
        duration_seconds REAL,
        records_read INTEGER,
        records_inserted INTEGER,
        records_quarantined INTEGER,
        records_skipped INTEGER,
        status TEXT,
        error_message TEXT,
        source_file_path TEXT,
        target_table_name TEXT
    )
    """

    cursor.execute(create_users_table_sql)
    cursor.execute(create_audit_table_sql)
    conn.commit()
    conn.close()


def check_landing_folder(folder_path: Path):
    """Checks if the landing folder exists and contains any CSV files."""
    folder_path.mkdir(exist_ok=True)
    csv_files = list(folder_path.glob("*.csv"))
    if not csv_files:
        return []
    return csv_files


def validate_and_classify_row(row):
    """Validates a single signup row."""
    user_id = str(row.get("id", "")).strip()
    name = str(row.get("name", "")).strip()
    signup_date = str(row.get("signup_date", "")).strip()

    if not user_id:
        return ("QUARANTINE", "MISSING_ID")

    is_fixed = False
    if not name:
        name = "Unknown"
        is_fixed = True

    cleaned_name = name.title()
    if cleaned_name != name:
        name = cleaned_name
        is_fixed = True

    cleaned_row = {"id": user_id, "name": name, "signup_date": signup_date}
    return ("FIXED" if is_fixed else "VALID", cleaned_row)


def check_for_duplicate(cursor, user_id):
    """Checks if a user ID already exists in the database."""
    cursor.execute("SELECT 1 FROM users WHERE id = ?", (user_id,))
    return cursor.fetchone() is not None


def push_user_to_db(conn, cursor, row, is_dub):
    """Inserts a new user or updates an existing duplicate row."""
    if is_dub:
        sql = "UPDATE users SET name = ?, signup_date = ? WHERE id = ?"
        cursor.execute(sql, (row["name"], row["signup_date"], row["id"]))
    else:
        sql = "INSERT INTO users (id, name, signup_date) VALUES (?, ?, ?)"
        cursor.execute(sql, (row["id"], row["name"], row["signup_date"]))
    conn.commit()


def log_to_quarantine(row, file_name):
    """Routes quarantined data to a local log file."""
    QUARANTINE_FOLDER.mkdir(exist_ok=True)
    log_file = QUARANTINE_FOLDER / "quarantined_rows.csv"
    file_exists = log_file.exists()
    
    with open(log_file, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["source_file", "id", "name", "signup_date"])
        writer.writerow([file_name, row.get("id", ""), row.get("name", ""), row.get("signup_date", "")])


def log_pipeline_run(conn, cursor, run_metadata):
    """Inserts a comprehensive audit log record into the metadata table."""
    sql = f"""
        INSERT INTO {METADATA_TABLE} (
            run_id, job_name, start_time, end_time, duration_seconds,
            records_read, records_inserted, records_quarantined, records_skipped,
            status, error_message, source_file_path, target_table_name
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    cursor.execute(sql, (
        run_metadata["run_id"],
        run_metadata["job_name"],
        run_metadata["start_time"],
        run_metadata["end_time"],
        run_metadata["duration_seconds"],
        run_metadata["records_read"],
        run_metadata["records_inserted"],
        run_metadata["records_quarantined"],
        run_metadata["records_skipped"],
        run_metadata["status"],
        run_metadata["error_message"],
        run_metadata["source_file_path"],
        run_metadata["target_table_name"]
    ))
    conn.commit()


if __name__ == "__main__":
    initialize_database()
    csv_files = check_landing_folder(LANDING_FOLDER)
    
    if csv_files:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        ARCHIVE_FOLDER.mkdir(exist_ok=True)

        for file_path in csv_files:
            run_id = str(uuid.uuid4())
            start_time = datetime.datetime.now().isoformat()
            start_tick = datetime.datetime.now()
            
            records_read = 0
            records_inserted = 0
            records_quarantined = 0
            records_skipped = 0
            run_status = "SUCCESS"
            error_message = None

            try:
                print(f"Processing file: {file_path.name}")
                with open(file_path, mode="r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for raw_row in reader:
                        records_read += 1
                        
                        # 1. Validation & Classification
                        row_state, result_payload = validate_and_classify_row(raw_row)
                        
                        if row_state == "QUARANTINE":
                            records_quarantined += 1
                            log_to_quarantine(raw_row, file_path.name)
                            continue
                        
                        # 2. Duplicate Check
                        cleaned_row = result_payload
                        is_dub = check_for_duplicate(cursor, cleaned_row["id"])
                        
                        if is_dub:
                            records_skipped += 1
                        
                        # 3. Ingestion (Idempotent write)
                        push_user_to_db(conn, cursor, cleaned_row, is_dub)
                        records_inserted += 1

                # Move processed file to archive so it isn't re-run next time
                archive_path = ARCHIVE_FOLDER / file_path.name
                file_path.rename(archive_path)

            except Exception as e:
                run_status = "FAILED"
                error_message = str(e)
                print(f"Pipeline error on {file_path.name}: {e}")

            # Compute run duration and record audit log
            end_time = datetime.datetime.now().isoformat()
            duration = (datetime.datetime.now() - start_tick).total_seconds()

            run_metadata = {
                "run_id": run_id,
                "job_name": "CSV_SIGNUP_INGESTION",
                "start_time": start_time,
                "end_time": end_time,
                "duration_seconds": duration,
                "records_read": records_read,
                "records_inserted": records_inserted,
                "records_quarantined": records_quarantined,
                "records_skipped": records_skipped,
                "status": run_status,
                "error_message": error_message,
                "source_file_path": str(file_path),
                "target_table_name": "users"
            }

            log_pipeline_run(conn, cursor, run_metadata)
            print(f"Finished run {run_id[:8]}... Status: {run_status} | Read: {records_read}, Inserted: {records_inserted}, Quarantined: {records_quarantined}")

        conn.close()
    else:
        print("No CSV files found in landing folder.")