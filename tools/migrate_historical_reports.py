import os
import shutil
from pathlib import Path
import re

def migrate():
    base_reports_dir = Path("data/reports")
    solo_root = Path("data/solo")
    team_root = Path("data/team")
    
    # Ensure roots exist
    solo_root.mkdir(parents=True, exist_ok=True)
    team_root.mkdir(parents=True, exist_ok=True)
    
    # Hardware folders in data/reports
    hw_dirs = [d for d in base_reports_dir.iterdir() if d.is_dir() and d.name != "archive"]
    
    for hw_dir in hw_dirs:
        hw_name = hw_dir.name
        print(f"Migrating hardware: {hw_name}")
        
        for file_path in hw_dir.iterdir():
            if file_path.is_dir() or file_path.name.startswith("."):
                continue
                
            filename = file_path.name
            
            # 1. Determine if Solo or Team
            is_team = "team" in filename.lower()
            target_root = team_root if is_team else solo_root
            
            # 2. Extract Run number if present (Run1, Run2, etc.)
            # Match "Run" followed by digits, or "Base"
            run_match = re.search(r"Run(\d+)", filename, re.IGNORECASE)
            if run_match:
                run_folder = f"Run{run_match.group(1)}"
            else:
                run_folder = "Base"
                
            dest_dir = target_root / hw_name / run_folder
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            dest_path = dest_dir / filename
            
            # Move the file
            # print(f"  {filename} -> {dest_dir.relative_to(Path.cwd())}")
            shutil.move(str(file_path), str(dest_path))
            
    print("Migration complete. Checking for empty hardware folders in data/reports...")
    # Clean up empty hw folders
    for hw_dir in hw_dirs:
        try:
            if not any(hw_dir.iterdir()):
                hw_dir.rmdir()
                print(f"  Removed empty directory: {hw_dir}")
        except Exception:
            pass

if __name__ == "__main__":
    migrate()
