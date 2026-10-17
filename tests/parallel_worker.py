"""Process fixture for concurrency and merge tests. No model calls or OS sandbox."""
from pathlib import Path
import json
import os
import sys
import time

role, mode, label, sync = sys.argv[1:]
sync = Path(sync)
sync.mkdir(parents=True, exist_ok=True)
prompt = sys.stdin.read()
shared = Path('output/shared.txt')
if role == 'resolver':
    context = json.loads(prompt)
    assert context['conflicted_paths']
    if mode == 'untouched':
        print('No change')
        raise SystemExit(0)
    if mode == 'fail':
        raise SystemExit(1)
    if mode == 'scope':
        Path('output/alpha.txt').write_text('unrelated')
    if mode == 'protected':
        Path('checks/parallel.py').write_text('pass')
    for path in context['conflicted_paths']:
        p = Path(path)
        if mode == 'retry' and not (sync/'resolver-once').exists():
            (sync/'resolver-once').write_text('yes')
            print('Leave markers for another pass')
            raise SystemExit(0)
        if mode == 'markers':
            p.write_text('<<<<<<< left\na\n=======\nb\n>>>>>>> right\n')
        elif mode == 'bad':
            p.write_text('wrong\n')
        else:
            p.write_text('a+b\n')
    print('Resolved fixture text conflict')
    raise SystemExit(0)

(sync / f'{label}-start.json').write_text(json.dumps({'cwd':str(Path.cwd()), 'pid':os.getpid(), 'start':time.monotonic()}))
# Rendezvous proves overlapping execution. A sequential runner cannot pass this.
if mode in {'barrier', 'cancel', 'slow', 'bounded'}:
    deadline = time.monotonic() + 5
    while len(list(sync.glob('*-start.json'))) < 2:
        if time.monotonic() > deadline:
            raise SystemExit('Workers did not overlap')
        time.sleep(.01)
if mode == 'bounded':
    time.sleep(.3 if label == 'a' else .1)
    Path('output/new-' + label + '.txt').write_text(label)
    (sync / f'{label}-finish').write_text(str(time.monotonic()))
    raise SystemExit(0)
if mode == 'cancel':
    if label == 'b':
        raise SystemExit(3)
    time.sleep(30)
if mode == 'slow':
    time.sleep(30)
if mode in {'barrier', 'disjoint'}:
    assert Path('output/alpha.txt').read_text() == '0'
    assert Path('output/beta.txt').read_text() == '0'
    Path('output/' + ('alpha.txt' if label == 'a' else 'beta.txt')).write_text(label)
elif mode == 'nonoverlap':
    lines = shared.read_text().splitlines()
    lines[0 if label == 'a' else -1] = label
    shared.write_text('\n'.join(lines) + '\n')
elif mode == 'conflict':
    shared.write_text(label + '\n')
elif mode == 'add-conflict':
    Path('output/new.txt').write_text(label + '\n')
elif mode == 'delete-conflict':
    if label == 'a':
        shared.unlink()
    else:
        shared.write_text(label + '\n')
elif mode == 'binary':
    shared.write_bytes(label.encode() + b'\0binary')
elif mode == 'rename-conflict':
    shared.rename('output/renamed-' + label + '.txt')
elif mode == 'protected':
    if label == 'a':
        Path('checks/parallel.py').write_text('pass')
    else:
        shared.write_text(label + '\n')
elif mode == 'new-file':
    Path('output/new-' + label + '.txt').write_text(label)
elif mode == 'regression':
    shared.write_text(label + '\n')
    if label == 'b':
        Path('output/keep.txt').write_text('broken')
else:
    raise SystemExit('Unknown worker scenario')
(sync / f'{label}-finish').write_text(str(time.monotonic()))
print('Completed fixture worker ' + label)
