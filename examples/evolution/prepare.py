"""Prepare a Codex harness-evolution fixture without launching inference."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from proofloop.evolution_demo import create_evolution_demo
from proofloop.core import git, write_json
import json

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--dir', type=Path, required=True)
p.add_argument('--model', required=True, help='a Codex model available to your account')
a = p.parse_args()
root = a.dir.resolve()
path = create_evolution_demo(root)
c = json.loads(path.read_text())
c['id'] = 'codex-json-harness'
c['evolver'] = {'adapter':'codex', 'model':a.model, 'reasoning_effort':'medium', 'timeout_s':300}
c['budget'].update(max_seconds=1800)
write_json(path,c)
git(root,'add','evolution.json')
git(root,'-c','user.name=ProofLoop Demo','-c','user.email=demo@localhost','commit','-m','configure fixed-weight Codex evolver')
print(f'Prepared {path}; no model was called.')
print(f'Next: proofloop evolve {path} --repo {root}')
