"""Application defaults with explicit per-project inheritance."""
import json
import os
import tempfile
from pathlib import Path
from laew.project_config import validate_language

DEFAULTS={'documentation_language':'en'}


def settings_path(manifest, manifest_path):
    from laew.console.session_store import conversation_store_from_manifest
    return conversation_store_from_manifest(manifest,manifest_path).directory.parent/'settings.json'


def read_defaults(path):
    try: value=json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError: return dict(DEFAULTS)
    if not isinstance(value,dict) or set(value)-set(DEFAULTS): raise ValueError('Invalid application defaults.')
    validate_language(value.get('documentation_language','en'))
    return DEFAULTS | value


def save_defaults(path, value):
    if not isinstance(value,dict) or set(value)-set(DEFAULTS): raise ValueError('Unknown default setting.')
    value=read_defaults(path) | value
    validate_language(value['documentation_language'])
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,delete=False) as handle:
            temporary=handle.name; json.dump(value,handle); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary,path)
    finally:
        if temporary and os.path.exists(temporary): os.unlink(temporary)
    return value
