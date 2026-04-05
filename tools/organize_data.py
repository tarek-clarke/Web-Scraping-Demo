import os
import shutil
import re

def organize_data():
    base_data_dir = "data"
    team_reports_dir = "team reports"
    target_data_dir = "data"
    
    # Ensure targets exist
    os.makedirs(os.path.join(target_data_dir, "solo"), exist_ok=True)
    os.makedirs(os.path.join(target_data_dir, "team"), exist_ok=True)
    
    # 1. Gather all files in data/ root
    ignore_files = {".DS_Store", ".gitkeep", "audit_log.sqlite", "domain_test_result.json", "hitl_feedback.json", "quarantine_log.json", "dlq.sqlite", "edge_buffer.sqlite"}
    solo_files = [f for f in os.listdir(base_data_dir) if os.path.isfile(os.path.join(base_data_dir, f)) and f not in ignore_files]
    
    # 2. Gather all files in team reports/ recursive
    team_files = []
    if os.path.exists(team_reports_dir):
        for root, dirs, files in os.walk(team_reports_dir):
            for f in files:
                if f not in ignore_files:
                    team_files.append(os.path.join(root, f))
            
    def get_dest(src_file, is_team):
        filename = os.path.basename(src_file)
        
        # Categorize by hardware
        hardware = "Misc"
        if "7900XT" in filename:
            hardware = "7900XT"
        elif "M4" in filename:
            hardware = "M4"
        elif "APPLEMETALMPS" in filename or "MPS" in filename:
            hardware = "APPLEMETALMPS"
            
        # Categorize by Run
        run_match = re.search(r"Run_?(\d+)", filename, re.IGNORECASE)
        run_folder = f"Run{run_match.group(1)}" if run_match else "Base"
        
        category = "team" if (is_team or re.search(r"Team", filename, re.IGNORECASE)) else "solo"
        
        target_dir = os.path.join(target_data_dir, category, hardware, run_folder)
        os.makedirs(target_dir, exist_ok=True)
        return os.path.join(target_dir, filename)

    # Move solo files
    for f in solo_files:
        src = os.path.join(base_data_dir, f)
        dest = get_dest(src, False)
        print(f"Moving {src} -> {dest}")
        shutil.move(src, dest)
        
    # Move team files
    for f in team_files:
        src = f
        dest = get_dest(src, True)
        print(f"Moving {src} -> {dest}")
        shutil.move(src, dest)

if __name__ == "__main__":
    organize_data()
