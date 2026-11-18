import csv
from pathlib import Path

def generate_test_csv():
    landing_folder = Path("./landing_folder")
    landing_folder.mkdir(exist_ok=True)
    
    file_path = landing_folder / "test_signups.csv"
    
    # Mix of valid, flawed (auto-fixable), fatal (quarantine), and duplicate rows
    test_data = [
        {"id": "U001", "name": "alice smith", "signup_date": "2026-03-01"},       # Will trigger name title-casing (FIXED)
        {"id": "U002", "name": "BOB JONES", "signup_date": "2026-03-02"},         # Will trigger name casing fix (FIXED)
        {"id": "", "name": "Charlie Brown", "signup_date": "2026-03-03"},         # Missing ID -> QUARANTINE
        {"id": "U001", "name": "alice smith", "signup_date": "2026-03-01"},       # Duplicate of U001 (updates existing row)
        {"id": "U003", "name": "", "signup_date": "2026-03-04"},                # Missing name -> Auto-fixed to "Unknown" (FIXED)
        {"id": "U004", "name": "  diana prince  ", "signup_date": "2026-03-05"},  # Extra spaces & lowercase -> trimmed & cased (FIXED)
        {"id": "U005", "name": "Evan Wright", "signup_date": "2026-03-06"},       # Perfectly clean (VALID)
    ]
    
    with open(file_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "name", "signup_date"])
        writer.writeheader()
        writer.writerows(test_data)
        
    print(f"Test CSV created successfully at: {file_path}")

if __name__ == "__main__":
    generate_test_csv()