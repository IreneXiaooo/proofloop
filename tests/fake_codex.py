"""Deterministic CLI contract fixture. Does not call an LLM or enforce a sandbox."""
import json
from pathlib import Path
import sys

args = sys.argv[1:]
if args == ['--version']:
    print('codex-cli CONTRACT-FIXTURE')
    raise SystemExit(0)
assert args[0] == 'exec'
assert '--json' in args and args[-1] == '-'
def option(key):
    return args[args.index(key) + 1]
model = option('--model')
sandbox = option('--sandbox')
assert 'agents.enabled=false' in args and 'features.multi_agent=false' in args
final = Path(option('--output-last-message'))
prompt = sys.stdin.read()
print('fixture diagnostics on stderr', file=sys.stderr)
print(json.dumps({'type': 'thread.started', 'thread_id': 'fixture', 'model': model}))
if 'timeout' in model:
    import time
    time.sleep(30)
if 'fail' in model:
    print(json.dumps({'type': 'turn.failed', 'error': {'message': 'fixture unavailable model'}}))
    raise SystemExit(1)
if '--output-schema' in args:
    schema = json.loads(Path(option('--output-schema')).read_text())
    if 'tasks' in schema['properties']:
        assert sandbox == 'read-only'
        names = json.loads(prompt)['workers']
        tasks = [{'worker': names[0], 'goal': 'Implement correct mean.'}]
        if 'two' in model:
            tasks.append({'worker': names[-1], 'goal': 'Preserve the correct mean.'})
        if 'three' in model:
            tasks = [{'worker': name, 'goal': 'Independent fixture component.'} for name in names]
        if 'over' in model:
            tasks *= 20
        if 'unknown' in model:
            tasks[0]['worker'] = 'not-allowed'
        if 'tamper' in model:
            Path('calculator.py').write_text('planner edited')
        text = json.dumps({'tasks': tasks})
    else:
        assert sandbox == 'read-only'
        if 'tamper' in model:
            Path('calculator.py').write_text('reviewer edited')
        text = ('not json' if 'malformed' in model else
                json.dumps({'verdict': 'REJECT' if 'reject' in model else 'APPROVE', 'reason': 'fixture review'}))
else:
    assert sandbox == 'workspace-write'
    Path('calculator.py').write_text("def mean(v):\n    if not v: raise ValueError('empty')\n    return sum(v)/len(v)\n")
    text = 'Implemented mean.'
if 'missing-final' not in model:
    final.write_text(text)
if 'no-terminal' not in model:
    event = {'type': 'turn.completed'}
    if 'unknown-usage' not in model:
        event['usage'] = {'input_tokens': 100, 'cached_input_tokens': 40, 'output_tokens': 20}
    print(json.dumps(event))
