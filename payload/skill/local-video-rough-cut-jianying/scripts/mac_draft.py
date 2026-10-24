"""New draft identity and macOS 5.5 profile. No app indexing or encrypted draft edits.

Schema reference: https://github.com/lhwget/auto_edit (jianying-tool 0.5.0).
The profile is a serialization baseline, not proof of compatibility with an installed app.
"""
import json
from pathlib import Path
import time
import uuid
from roughcut_cli import write_json


def finalize_draft(folder, root, profile='mac-5.5'):
    folder, root = Path(folder).resolve(), Path(root).resolve()
    path = folder / 'draft_content.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    identity = str(uuid.uuid4()).upper()
    data['id'] = identity
    if profile == 'mac-5.5':
        data['new_version'] = '103.0.0'
        data['color_space'] = -1
        for key in ('platform', 'last_modified_platform'):
            data.setdefault(key, {}).update({'os': 'mac', 'app_id': 3704,
                                            'app_source': 'lv', 'app_version': '5.5.0'})
    elif profile != 'windows':
        raise ValueError(f'未知草稿格式：{profile}')
    write_json(path, data)
    if profile == 'mac-5.5':
        write_json(folder / 'draft_info.json', data)
    meta_path = folder / 'draft_meta_info.json'
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    meta.update({'draft_id': identity, 'draft_name': folder.name, 'draft_fold_path': str(folder),
                 'draft_root_path': str(root), 'tm_duration': int(data['duration']),
                 'tm_draft_create': int(time.time() * 1e6), 'tm_draft_modified': int(time.time() * 1e6)})
    write_json(meta_path, meta)
    return identity
