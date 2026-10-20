"""Small deterministic development search; no provider calls or performance claims."""
import json
from pathlib import Path
from .core import git, write_json, HarnessError

BASE = '''import json

def parse(text):
    return json.loads(text)
'''
FENCED = '''import json

def strip_fence(text):
    return text.removeprefix('```json\\n').removesuffix('\\n```')

def parse(text):
    return json.loads(strip_fence(text))
'''
EXTRACT = '''import json

def extract_object(text):
    return text[text.index('{'):text.rindex('}') + 1]

def parse(text):
    return json.loads(extract_object(text))
'''
DRIVER = '''import json, sys
from pathlib import Path
request = json.loads(sys.stdin.read())
if request.get('candidate') is not None:
    print(json.dumps({'action':'revise','directive':'The prose task still fails. Extract the JSON object before decoding.','donor':''}))
else:
    directed = request['mode'] == 'directed'
    Path('harness.py').write_text(%r if directed else %r)
    print(json.dumps({'strategy':'Extract the object' if directed else 'Strip code fences',
                      'mechanism':'extract_object' if directed else 'strip_fence'}))
''' % (EXTRACT, FENCED)
EVALUATOR = '''import importlib.util, json, sys
from pathlib import Path
request = json.loads(sys.stdin.read())
spec = importlib.util.spec_from_file_location('candidate', 'harness.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
cases = {'plain':'{"value":3}', 'fenced':'```json\\n{"value":3}\\n```',
         'prose':'Result: {"value":3}. Done.'}
rows = []
for task in request['tasks']:
    active = set()
    def trace(frame, event, arg):
        if event == 'call' and Path(frame.f_code.co_filename).resolve() == Path('harness.py').resolve():
            active.add(frame.f_code.co_name)
        return trace
    sys.settrace(trace)
    try:
        score = float(module.parse(cases[task]) == {'value':3})
    except Exception:
        score = 0.0
    finally:
        sys.settrace(None)
    rows.append({'id':task,'score':score,'active_mechanisms':sorted(active)})
Path(request['output']).write_text(json.dumps({'executor':request['executor'],'tasks':rows}))
'''


def create_evolution_demo(destination: Path):
    destination = Path(destination)
    if destination.exists() and any(destination.iterdir()):
        raise HarnessError('Evolution demo destination must be empty')
    destination.mkdir(parents=True, exist_ok=True)
    git(destination, 'init', '-b', 'main')
    (destination / 'harness.py').write_text(BASE, encoding='utf-8')
    (destination / 'evolve_driver.py').write_text(DRIVER, encoding='utf-8')
    (destination / 'evaluate.py').write_text(EVALUATOR, encoding='utf-8')
    config = {'version':1, 'id':'json-harness', 'goal':'Improve JSON parsing under fixed executor outputs.',
              'evolver':{'command':['{python}','evolve_driver.py'],'timeout_s':10},
              'writable':['harness.py'], 'protected':['evaluate.py','evolve_driver.py','evolution.json'],
              'evaluation':{'command':['{python}','evaluate.py'],'timeout_s':10,
                            'tasks':['plain','fenced','prose'],
                            'executor':{'name':'frozen-response-fixture','revision':'1'},'repeats':1},
              'budget':{'max_rounds':1,'max_calls':3,'max_evaluations':5,'max_seconds':60}}
    path = destination / 'evolution.json'
    write_json(path, config)
    git(destination, 'add', '.')
    git(destination, '-c', 'user.name=ProofLoop Demo', '-c', 'user.email=demo@localhost',
        'commit', '-m', 'fixed executor development fixture')
    return path
