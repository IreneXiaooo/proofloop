"""Command interface. No implicit uploads, pushes or API calls."""
import argparse
import json
from pathlib import Path
import sys
from . import __version__
from .core import Harness, HarnessError
from .demo import create_demo


def main(argv=None):
    p = argparse.ArgumentParser(description='ProofLoop — keep only verified progress.')
    p.add_argument('--version', action='version', version=__version__)
    sub = p.add_subparsers(dest='cmd', required=True)
    demo = sub.add_parser('demo', help='run an offline reject-then-accept demonstration')
    demo.add_argument('--dir', type=Path, default=Path('.proofloop-demo'))
    for name in ['run', 'verify', 'status', 'report']:
        s = sub.add_parser(name)
        s.add_argument('config', type=Path)
        s.add_argument('--repo', type=Path, default=Path('.'))
    args = p.parse_args(argv)
    try:
        if args.cmd == 'demo':
            root = args.dir.resolve()
            harness = Harness(root, create_demo(root))
            status = harness.run()
            print(f'\n{status} · {harness.state["accepted"]} accepted / {harness.state["attempts"]} attempts')
            print(f'Original checkout preserved: {root}')
            print('Inspect: git -C ' + str(root) + ' diff main..proofloop/fix-mean')
            return 0 if status == 'COMPLETE' else 1
        harness = Harness(args.repo, args.config)
        if args.cmd in ['status', 'report']:
            if not harness.state_path.exists():
                raise HarnessError('No run yet. Start with proofloop run or verify.')
            if args.cmd == 'report':
                print((harness.home / 'REPORT.md').read_text(encoding='utf-8'))
            else:
                state = json.loads(harness.state_path.read_text())
                print(json.dumps({k: state[k] for k in ['status', 'attempts', 'accepted', 'calls', 'seconds', 'head']}, indent=2))
            return 0
        status = harness.run(verify_only=args.cmd == 'verify')
        print(status)
        print(f'Report: {harness.home / "REPORT.md"}')
        return 0 if status in ['COMPLETE', 'VERIFIED'] else 1
    except (HarnessError, OSError, ValueError) as exc:
        print(f'ProofLoop: {exc}', file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print('Interrupted. State saved; rerun the same command to resume.', file=sys.stderr)
        return 130
