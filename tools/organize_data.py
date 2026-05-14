import os
import re
import shutil
from pathlib import Path


IGNORE_FILES = {
    ".DS_Store",
    ".gitkeep",
    "audit_log.sqlite",
    "domain_test_result.json",
    "hitl_feedback.json",
    "quarantine_log.json",
    "dlq.sqlite",
    "edge_buffer.sqlite",
}


def _clean_filename(filename: str) -> str:
    cleaned = re.sub(r"_Run\d+_?", "_", filename)
    cleaned = re.sub(r"__+", "_", cleaned)
    return cleaned.replace("_.", ".")


def _find_folder_name(parts: tuple[str, ...], choices: set[str], default: str) -> str:
    for part in parts:
        if part in choices:
            return part
    return default


def _canonical_destination(source_path: Path) -> Path | None:
    if not source_path.is_file() or source_path.name in IGNORE_FILES:
        return None

    parts = source_path.parts
    if "data" not in parts:
        return None

    data_index = parts.index("data")
    if len(parts) <= data_index + 2:
        return None

    category = parts[data_index + 1]
    hardware = parts[data_index + 2]

    session_folder = _find_folder_name(parts, {"Sprint", "Weekend"}, "Weekend").lower()
    profile_folder = _find_folder_name(parts, {"Standard", "Realistic", "UltraLow"}, "Standard")

    frequency_folder = "100hz"
    for part in parts:
        lowered = part.lower()
        if lowered in {"100hz", "1000hz", "1mhz"}:
            frequency_folder = lowered
            break

    canonical_name = _clean_filename(source_path.name)
    destination_dir = Path("data") / "reports" / hardware / category / session_folder / frequency_folder / profile_folder
    return destination_dir / canonical_name


def organize_data() -> None:
    source_roots = [Path("data/solo"), Path("data/team")]
    moved = 0

    for source_root in source_roots:
        if not source_root.exists():
            continue

        for source_path in source_root.rglob("*"):
            destination_path = _canonical_destination(source_path)
            if destination_path is None:
                continue

            destination_path.parent.mkdir(parents=True, exist_ok=True)
            if destination_path.exists():
                print(f"Skipping existing file: {destination_path}")
                continue

            print(f"Moving {source_path} -> {destination_path}")
            shutil.move(str(source_path), str(destination_path))
            moved += 1

    for source_root in source_roots:
        if not source_root.exists():
            continue
        for root, dirs, files in os.walk(source_root, topdown=False):
            if not dirs and not files:
                try:
                    os.rmdir(root)
                except OSError:
                    pass

    print(f"Organized {moved} benchmark file(s) into data/reports/.")


if __name__ == "__main__":
    organize_data()
