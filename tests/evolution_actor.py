"""Process fixture for evolution control-flow and rejection tests."""
import json
from pathlib import Path
import sys
import time

from proofloop.evolution_demo import FENCED, EXTRACT

mode = sys.argv[1]
request = json.loads(sys.stdin.read())
reflect = 'candidate' in request
if reflect:
    if mode == 'reflect-write':
        Path('harness.py').write_text('changed')
    if mode == 'invalid-reflection':
        response = {'action': 'unknown', 'directive': '', 'donor': ''}
    elif mode == 'unknown-donor':
        response = {'action': 'crossover', 'directive': 'Copy it', 'donor': 'missing'}
    elif mode == 'crossover' and request['strategies']:
        response = {'action': 'crossover', 'directive': 'Adapt the donor and extract JSON',
                    'donor': next(iter(request['strategies']))}
    else:
        response = {'action': 'keep', 'directive': '', 'donor': ''}
    print(json.dumps(response))
else:
    if mode == 'slow':
        time.sleep(5)
    if mode == 'exit':
        sys.exit(1)
    if mode == 'scope':
        Path('evaluate.py').write_text('raise SystemExit(0)')
    elif mode == 'head':
        import subprocess
        subprocess.run(['git', 'checkout', '-b', 'bad-branch'], check=True, capture_output=True)
    elif mode == 'startup':
        Path('harness.py').write_text('invalid python !')
    elif mode == 'regression':
        Path('harness.py').write_text("import json\ndef strip_fence(text):\n    assert text.startswith('```')\n    return text[8:-4]\ndef parse(text):\n    return json.loads(strip_fence(text))\n")
    elif mode != 'nochange':
        source = EXTRACT if request['mode'] == 'directed' else FENCED
        if mode == 'crossover':
            source += '\n# parent ' + request['parent']['id'] + '\n'
        Path('harness.py').write_text(source)
    mechanism = 'missing' if mode == 'no-activation' else 'extract_object' if request['mode'] == 'directed' else 'strip_fence'
    print(json.dumps({'strategy': 'Fixture change', 'mechanism': mechanism}))
