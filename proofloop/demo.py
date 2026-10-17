"""Offline demonstration; not an LLM benchmark."""
from pathlib import Path
import json
from .core import HarnessError, git

CHECK = '''import importlib.util
spec = importlib.util.spec_from_file_location("calc", "calculator.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
assert m.mean([2, 4, 9]) == 5
assert m.mean([-2, 2]) == 0
try:
    m.mean([])
except ValueError:
    pass
else:
    raise AssertionError("empty input must raise ValueError")
print("3 behavioral checks passed")
'''
AGENT = '''import json
import sys
from pathlib import Path
context = json.loads(sys.stdin.read().split("\\n", 1)[1])
if not context["recent_attempts"]:
    body = "def mean(values):\\n    return sum(values) / (len(values) + 1)\\n"
else:
    body = "def mean(values):\\n    if not values:\\n        raise ValueError('empty input')\\n    return sum(values) / len(values)\\n"
Path("calculator.py").write_text(body)
print("Demo worker submitted a candidate.")
'''


def create_demo(destination: Path) -> Path:
    if destination.exists():
        raise HarnessError('Demo destination already exists; choose an empty new path.')
    destination.mkdir(parents=True)
    (destination / 'checks').mkdir()
    (destination / 'checks/mean.py').write_text(CHECK, encoding='utf-8')
    (destination / 'demo_agent.py').write_text(AGENT, encoding='utf-8')
    (destination / 'calculator.py').write_text('def mean(values):\n    return sum(values)\n', encoding='utf-8')
    config = {'version': 1, 'id': 'fix-mean', 'goal': 'Implement arithmetic mean; reject empty input with ValueError.',
              'agent': {'command': ['{python}', 'demo_agent.py'], 'timeout_s': 10},
              'writable': ['calculator.py'], 'protected': ['checks/**', 'demo_agent.py', 'task.json'],
              'budget': {'max_attempts': 3, 'max_seconds': 60, 'stall_after': 3},
              'stages': [{'id': 'behavior', 'check': ['{python}', 'checks/mean.py']}]}
    path = destination / 'task.json'
    path.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
    git(destination, 'init', '-b', 'main')
    git(destination, 'add', '.')
    git(destination, '-c', 'user.name=ProofLoop Demo', '-c', 'user.email=demo@localhost',
        'commit', '-m', 'demo: a broken mean and frozen behavioral checks')
    return path
