import os
import shutil
from pathlib import Path
import re

def sort_deeply(root_dir: Path):
    if not root_dir.exists():
        return
        
    # Iterate through Category -> Hardware -> RunN
    for run_dir in root_dir.glob("*/*"):
        if not run_dir.is_dir() or not run_dir.name.startswith(("Run", "Base")):
            continue
            
        print(f"Deep-sorting Frequency levels: {run_dir}")
        
        # We need to scan recursively to find files that might already be in Sprint/Weekend/Profile
        for file_path in list(run_dir.rglob("*")):
            if file_path.is_dir() or file_path.name.startswith("."):
                continue
                
            # If the file is already inside a Frequency folder, skip it to avoid double-processing
            if "Frequency" in file_path.parts:
                continue
                
            filename = file_path.name.lower()
            
            # 1. Determine Level 4: Weekend vs Sprint (if not already there)
            # 2. Determine Level 5: Realistic, UltraLow, Standard
            # 3. Determine Level 6/7: Frequency/XXXhz
            
            # Extract parts or guess from path
            rel_parts = file_path.relative_to(run_dir).parts
            
            session_folder = "Weekend"
            profile_folder = "Standard"
            
            if len(rel_parts) >= 2:
                session_folder = rel_parts[0]
                profile_folder = rel_parts[1]
            elif "weekend" in filename:
                session_folder = "Weekend"
            elif "sprint" in filename:
                session_folder = "Sprint"
                
            if "realistic" in filename:
                profile_folder = "Realistic"
            elif "ultralow" in filename:
                profile_folder = "UltraLow"

            # Determine Frequency label
            if "1mhz" in filename:
                freq_label = "1mhz"
            elif "1000hz" in filename:
                freq_label = "1000hz"
            else:
                freq_label = "1000hz" # default
                
            dest_dir = run_dir / session_folder / profile_folder / "Frequency" / freq_label
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            # Pre-create the empty twin for symmetry
            (run_dir / session_folder / profile_folder / "Frequency" / "1mhz").mkdir(parents=True, exist_ok=True)
            (run_dir / session_folder / profile_folder / "Frequency" / "1000hz").mkdir(parents=True, exist_ok=True)
            
            shutil.move(str(file_path), str(dest_dir / file_path.name))

def migrate():
    sort_deeply(Path("data/solo"))
    sort_deeply(Path("data/team"))
    print("Deep Frequency migration complete.")

if __name__ == "__main__":
    migrate()
