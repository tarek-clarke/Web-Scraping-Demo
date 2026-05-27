from pathlib import Path
import json

root = Path('/Users/tarekclarke/resilient-rap-framework-semantic_only')
changed = []


def write_text_replace(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    if old in text:
        path.write_text(text.replace(old, new))
        changed.append(str(path))


def transform_gh200(obj, path_stack=None):
    if path_stack is None:
        path_stack = []
    if isinstance(obj, dict):
        new_obj = {}
        for key, value in obj.items():
            new_value = value
            if key == 'actual_device' and value == 'aarch64':
                new_value = 'GH200'
            elif key == 'hardware' and value == 'aarch64':
                new_value = 'GH200'
            elif key == 'model' and value == 'aarch64' and path_stack and path_stack[-1] == 'device' and 'policy' in path_stack:
                new_value = 'GH200'
            new_obj[key] = transform_gh200(new_value, path_stack + [key])
        return new_obj
    if isinstance(obj, list):
        return [transform_gh200(item, path_stack) for item in obj]
    return obj

for path in root.rglob('*'):
    if not path.is_file():
        continue
    rel = path.relative_to(root).as_posix()
    if rel.startswith('.git/') or rel.startswith('.venv/'):
        continue

    if path.suffix == '.json':
        if rel.startswith('results/raw/Apple_M4_16GB/'):
            write_text_replace(path, 'Apple_Silicon_arm', 'Apple M4 16GB')
        elif rel.startswith('results/raw/GH200/'):
            data = json.loads(path.read_text())
            updated = transform_gh200(data)
            if updated != data:
                path.write_text(json.dumps(updated, separators=(', ', ': ')))
                changed.append(str(path))
        elif rel.startswith('results/'):
            write_text_replace(path, 'Apple_Silicon_arm', 'Apple M4 16GB')
    elif path.suffix == '.csv' and rel.startswith('results/'):
        write_text_replace(path, 'Apple_Silicon_arm', 'Apple M4 16GB')

unique_changed = sorted(set(changed))
print(f'updated {len(unique_changed)} files')
for item in unique_changed[:25]:
    print(item)
if len(unique_changed) > 25:
    print('...')
