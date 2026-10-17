"""Codex CLI contract. No provider SDK, credentials, or implicit sign-in."""
from __future__ import annotations

import json
from pathlib import Path

REVIEW_SCHEMA = {
    'type': 'object', 'properties': {'verdict': {'type': 'string', 'enum': ['APPROVE', 'REJECT']},
                                     'reason': {'type': 'string'}},
    'required': ['verdict', 'reason'], 'additionalProperties': False,
}
PLAN_SCHEMA = {
    'type': 'object', 'properties': {'tasks': {'type': 'array', 'items': {
        'type': 'object', 'properties': {'worker': {'type': 'string'}, 'goal': {'type': 'string'}},
        'required': ['worker', 'goal'], 'additionalProperties': False}}},
    'required': ['tasks'], 'additionalProperties': False,
}


def build_command(spec: dict, role: str, final: Path, schema: Path | None = None) -> list[str]:
    argv = [*spec.get('command', ['codex']), 'exec', '--json', '--model', spec['model'],
            '--sandbox', 'workspace-write' if role == 'worker' else 'read-only',
            '-c', 'agents.enabled=false', '-c', 'features.multi_agent=false',
            '--output-last-message', str(final)]
    if 'reasoning_effort' in spec:
        argv += ['-c', 'model_reasoning_effort=' + json.dumps(spec['reasoning_effort'])]
    if schema:
        argv += ['--output-schema', str(schema)]
    return [*argv, '-']


def parse_events(log: Path) -> dict:
    """Sum completed-turn usage, never infer missing token counts as zero."""
    turns = []
    failed = False
    malformed_lines = 0
    actual_models = set()
    if log.exists():
        with log.open(encoding='utf-8', errors='replace') as stream:
            for line in stream:
                try:
                    event = json.loads(line)
                except ValueError:
                    malformed_lines += bool(line.strip())
                    continue
                if not isinstance(event, dict):
                    continue
                kind = event.get('type')
                if kind in {'turn.failed', 'error'}:
                    failed = True
                if kind == 'turn.completed':
                    turns.append(event.get('usage'))
                # Some versions expose model metadata, others do not.
                if kind in {'thread.started', 'turn.started', 'turn.completed'} and isinstance(event.get('model'), str):
                    actual_models.add(event['model'])
    keys = ['input_tokens', 'cached_input_tokens', 'output_tokens']
    valid = bool(turns)
    for turn in turns:
        if not isinstance(turn, dict) or any(type(turn.get(k)) is not int or turn[k] < 0 for k in keys):
            valid = False
        elif turn['cached_input_tokens'] > turn['input_tokens']:
            valid = False
    usage = {k: sum(t[k] for t in turns) for k in keys} if valid else None
    return {'usage': usage, 'completed_turns': len(turns), 'failed_event': failed,
            'non_json_lines': malformed_lines, 'observed_models': sorted(actual_models)}


def estimate_cost(usage: dict | None, pricing: dict | None) -> float | None:
    if usage is None or pricing is None:
        return None
    uncached = usage['input_tokens'] - usage['cached_input_tokens']
    return (uncached * pricing['input_per_million']
            + usage['cached_input_tokens'] * pricing['cached_input_per_million']
            + usage['output_tokens'] * pricing['output_per_million']) / 1_000_000


def run_codex(spec, role, wt, prompt, log, invoke, timeout):
    """Use a separate final-message file so CLI diagnostics cannot break JSON review."""
    final = log.with_suffix('.final.txt')
    schema_path = None
    log.parent.mkdir(parents=True, exist_ok=True)
    if role in {'planner', 'reviewer'}:
        schema_path = log.with_suffix('.schema.json')
        schema_path.write_text(json.dumps(PLAN_SCHEMA if role == 'planner' else REVIEW_SCHEMA), encoding='utf-8')
    final.unlink(missing_ok=True)
    argv = build_command(spec, role, final, schema_path)
    row = invoke(argv, wt, timeout, prompt, log=log)
    telemetry = parse_events(log)
    row.update(telemetry)
    row['usage_complete'] = bool(row['usage'] is not None and row['status'] == 'OK'
                                 and row['returncode'] == 0 and not row['failed_event'])
    row['requested_model'] = spec['model']
    row['adapter'] = 'codex'
    row['cost_usd_estimate'] = estimate_cost(row['usage'], spec.get('pricing'))
    row['final_message'] = ''
    if final.is_file() and final.stat().st_size <= 65536:
        row['final_message'] = final.read_text(encoding='utf-8')
    if row['status'] == 'OK' and row['returncode'] == 0:
        if telemetry['failed_event'] or not telemetry['completed_turns'] or not row['final_message'].strip():
            row['status'] = 'CODEX_PROTOCOL_ERROR'
            row['returncode'] = 1
    return row


def valid_review(value):
    return (isinstance(value, dict) and set(value) == {'verdict', 'reason'}
            and value['verdict'] in {'APPROVE', 'REJECT'} and isinstance(value['reason'], str)
            and bool(value['reason'].strip()))


def validate_plan(value, delegation):
    if not isinstance(value, dict) or set(value) != {'tasks'} or not isinstance(value['tasks'], list):
        raise ValueError('Planner must return an object containing tasks')
    tasks = value['tasks']
    if not 1 <= len(tasks) <= delegation['max_tasks']:
        raise ValueError('Planner task count exceeds the configured bound or is empty')
    for task in tasks:
        if (not isinstance(task, dict) or set(task) != {'worker', 'goal'}
                or not isinstance(task['worker'], str) or task['worker'] not in delegation['workers']
                or not isinstance(task['goal'], str) or not task['goal'].strip() or len(task['goal']) > 4000):
            raise ValueError('Planner selected an unknown worker or invalid goal')
    return tasks


def usage_summary(home: Path) -> dict:
    summary = {'calls': 0, 'unknown_usage_calls': 0, 'unknown_cost_calls': 0,
               'input_tokens': 0, 'cached_input_tokens': 0, 'output_tokens': 0,
               'known_cost_usd_estimate': 0.0, 'by_role_model': {}}
    for path in sorted((home / 'calls').glob('*.json')):
        row = json.loads(path.read_text(encoding='utf-8'))
        key = row['role'] + '/' + (row.get('requested_model') or row.get('worker_profile') or 'command')
        group = summary['by_role_model'].setdefault(key, {'calls': 0, 'input_tokens': 0,
            'cached_input_tokens': 0, 'output_tokens': 0, 'unknown_usage_calls': 0,
            'known_cost_usd_estimate': 0.0, 'unknown_cost_calls': 0})
        for target in [summary, group]:
            target['calls'] += 1
            if row.get('usage') is None or not row.get('usage_complete', False):
                target['unknown_usage_calls'] += 1
            if row.get('usage') is not None:
                for k in ['input_tokens', 'cached_input_tokens', 'output_tokens']:
                    target[k] += row['usage'][k]
            if row.get('cost_usd_estimate') is None or not row.get('usage_complete', False):
                target['unknown_cost_calls'] += 1
            if row.get('cost_usd_estimate') is not None:
                target['known_cost_usd_estimate'] += row['cost_usd_estimate']
    state_path = home / 'state.json'
    expected_calls = json.loads(state_path.read_text()).get('calls', 0) if state_path.exists() else 0
    missing = max(0, expected_calls - summary['calls'])
    summary['unattributed_calls'] = missing
    summary['calls'] += missing
    summary['unknown_usage_calls'] += missing
    summary['unknown_cost_calls'] += missing
    summary['cost_usd_estimate'] = (summary['known_cost_usd_estimate']
                                    if not summary['unknown_cost_calls'] else None)
    summary['usage_complete'] = not summary['unknown_usage_calls']
    return summary


def create_codex_demo(destination: Path, worker_model: str, reviewer_model: str, planner_model: str | None = None):
    """Prepare a committed task; generation never launches a model."""
    from .core import git, write_json, load_config
    from .demo import create_demo
    path = create_demo(destination)
    config = json.loads(path.read_text())
    def model_spec(model):
        return {'adapter': 'codex', 'model': model, 'reasoning_effort': 'medium', 'timeout_s': 300}
    config['id'] = 'codex-mean'
    config['agent'] = model_spec(worker_model)
    config['reviewer'] = model_spec(reviewer_model)
    config['budget'] = {'max_attempts': 3, 'max_seconds': 1800, 'stall_after': 3, 'max_calls': 12}
    if planner_model:
        config['delegation'] = {'planner': model_spec(planner_model),
                                'workers': {'implementer': model_spec(worker_model)}, 'max_tasks': 2}
    write_json(path, config)
    load_config(path)
    git(destination, 'add', 'task.json')
    git(destination, '-c', 'user.name=ProofLoop Demo', '-c', 'user.email=demo@localhost',
        'commit', '-m', 'Configure explicit Codex models; no model called yet')
    return path


def doctor(config: dict, home: Path, invoke) -> dict:
    """Check executable/version only. Never logs in or makes a model request."""
    specs = [config['agent']]
    if 'reviewer' in config:
        specs.append(config['reviewer'])
    if 'delegation' in config:
        specs += [config['delegation']['planner'], *config['delegation']['workers'].values()]
    specs += [s['agent'] for s in config['stages'] if 'agent' in s]
    results = []
    seen = set()
    for spec in specs:
        if spec.get('adapter') != 'codex':
            continue
        prefix = spec.get('command', ['codex'])
        key = tuple(prefix)
        if key in seen:
            continue
        seen.add(key)
        log = home / 'doctor' / f'{len(results)}.log'
        row = invoke([*prefix, '--version'], home, 10, log=log)
        results.append({'command': prefix, 'available': row['returncode'] == 0 and row['status'] == 'OK',
                        'version_output': row['tail'].strip(), 'status': row['status']})
    return {'checks': results, 'ready': bool(results) and all(r['available'] for r in results),
            'limits': 'Executable/version check only. Authentication, model access, and sandbox behavior are not tested.'}
