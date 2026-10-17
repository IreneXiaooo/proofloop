"""Run both noncoding fixtures in disposable repositories; requires a source checkout."""
from pathlib import Path
import shutil
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from proofloop.core import Harness, git

for name in ['data-cleaning', 'report']:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / name
        shutil.copytree(Path(__file__).resolve().parent / name, root)
        git(root, 'init', '-b', 'main')
        git(root, 'add', '.')
        git(root, '-c', 'user.name=Example', '-c', 'user.email=example@localhost', 'commit', '-m', 'fixture')
        h = Harness(root, root / 'task.json')
        assert h.run() == 'COMPLETE', name
        assert h.state['accepted'] == 1
        print(name + ': COMPLETE; accepted output is on ' + h.ref)
