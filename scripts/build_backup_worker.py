"""Build the allowlisted backup worker with a pinned offline build toolchain."""

import argparse
from importlib.metadata import version
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
FILES = (
    'laew/__init__.py', 'laew/backup_worker.py', 'laew/operator_cli.py',
    'laew/manifest.py', 'laew/project_config.py', 'laew/storage_paths.py',
    'laew/backup/__init__.py', 'laew/backup/archive.py', 'laew/backup/capture.py',
    'laew/backup/fence.py', 'laew/backup/health.py', 'laew/backup/inventory.py',
    'laew/backup/provenance.py', 'laew/backup/recovery_checks.py', 'laew/backup/restore.py',
    'laew/backup/controller.py', 'laew/backup/controls.py', 'laew/backup/managed.py',
    'laew/backup/policy.py', 'laew/backup/replication.py', 'laew/backup/transport.py',
    'laew/console/__init__.py', 'laew/console/session_store.py', 'laew/console/state.py',
    'laew/knowledge/__init__.py', 'laew/knowledge/store.py',
    'laew/memory/__init__.py', 'laew/memory/categories.py', 'laew/memory/store.py',
    'laew/rag/__init__.py', 'laew/rag/config.py', 'laew/rag/identity.py',
    'laew/security/__init__.py', 'laew/security/path_resolver.py',
    'laew/security/windows_security.py',
)
FILENAME = 'laew_backup_worker-0.2.0-py3-none-any.whl'
PYPROJECT = '''[build-system]
requires = ["setuptools==84.2.1", "wheel==0.48.0", "packaging==26.4"]
build-backend = "setuptools.build_meta"

[project]
name = "laew-backup-worker"
version = "0.2.0"
requires-python = ">=3.10"
dependencies = ["PyYAML==6.0.3"]

[project.scripts]
laew-backup-worker = "laew.backup_worker:main"

[tool.setuptools.packages.find]
where = ["src"]
include = ["laew*"]
'''


def build(output):
    if any(version(name) != pinned for name, pinned in (
            ('setuptools', '84.2.1'), ('wheel', '0.48.0'), ('packaging', '26.4'))):
        raise RuntimeError('Build requires pinned setuptools, wheel and packaging')
    if output.name != FILENAME:
        raise ValueError('Output must use the canonical worker wheel filename')
    if output.exists():
        raise FileExistsError(output)
    with tempfile.TemporaryDirectory(prefix='laew-worker-build-') as temporary:
        stage = Path(temporary)
        for name in FILES:
            source, target = ROOT / name, stage / 'src' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        (stage / 'pyproject.toml').write_text(PYPROJECT, encoding='utf-8')
        # No dependency resolution or isolated network-enabled environment.
        env = os.environ.copy()
        env.update(SOURCE_DATE_EPOCH='315532800', PYTHONHASHSEED='0', PIP_NO_INDEX='1')
        subprocess.run([sys.executable, '-m', 'pip', 'wheel', '--no-index', '--no-deps',
                        '--no-build-isolation', '--wheel-dir', str(stage / 'dist'), str(stage)],
                       check=True, env=env)
        with (stage / 'dist' / FILENAME).open('rb') as source, output.open('xb') as destination:
            shutil.copyfileobj(source, destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    build(parser.parse_args().output)


if __name__ == '__main__':
    main()
