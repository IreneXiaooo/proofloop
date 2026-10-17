import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from proofloop.codex import build_command, estimate_cost, parse_events, usage_summary
from proofloop.core import Harness, HarnessError, git, load_config, write_json
from proofloop.demo import create_demo

FAKE = str(Path(__file__).with_name('fake_codex.py').resolve())
RATES = {'input_per_million': 2, 'cached_input_per_million': 1, 'output_per_million': 5}


def spec(model):
    return {'adapter': 'codex', 'command': ['{python}', FAKE], 'model': model,
            'timeout_s': 10, 'reasoning_effort': 'medium', 'pricing': dict(RATES)}


class CodexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'repo'
        self.config = create_demo(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def configure(self, **values):
        c = json.loads(self.config.read_text())
        c.update(agent=spec('worker-sol'), reviewer=spec('reviewer-astra'),
                 budget={'max_attempts': 1, 'max_seconds': 30, 'stall_after': 3, 'max_calls': 8})
        c.update(values)
        write_json(self.config, c)
        git(self.root, 'add', '.')
        git(self.root, '-c', 'user.name=Test', '-c', 'user.email=test@localhost', 'commit', '-m', 'Codex fixture')
        return c

    def run_task(self):
        h = Harness(self.root, self.config)
        with contextlib.redirect_stdout(io.StringIO()):
            result = h.run()
        return h, result

    def delegate(self, planner='planner-astra', max_tasks=2):
        return {'planner': spec(planner), 'workers': {'sol': spec('worker-sol'), 'luna': spec('worker-luna')},
                'max_tasks': max_tasks}

    def test_codex_worker_and_reviewer_end_to_end(self):
        self.configure()
        h, result = self.run_task()
        self.assertEqual(result, 'COMPLETE')
        self.assertEqual(h.state['calls'], 2)
        usage = usage_summary(h.home)
        self.assertEqual(usage['input_tokens'], 200)
        self.assertEqual(usage['cached_input_tokens'], 80)
        self.assertEqual(usage['output_tokens'], 40)
        self.assertTrue(usage['usage_complete'])
        self.assertAlmostEqual(usage['cost_usd_estimate'], .00052)
        self.assertTrue((h.home / 'runs/0001/review.final.txt').exists())
        self.assertIn('fixture diagnostics', (h.home / 'runs/0001/review.log').read_text())

    def test_sequential_delegation_two_models(self):
        self.configure(delegation=self.delegate('planner-two'))
        h, result = self.run_task()
        self.assertEqual(result, 'COMPLETE')
        self.assertEqual(h.state['calls'], 4)
        groups = usage_summary(h.home)['by_role_model']
        self.assertIn('planner/planner-two', groups)
        self.assertIn('worker/worker-sol', groups)
        self.assertIn('worker/worker-luna', groups)
        self.assertIn('reviewer/reviewer-astra', groups)
        self.assertEqual(json.loads((h.home / 'runs/0001/plan.json').read_text())['tasks'][1]['worker'], 'luna')

    def test_planner_cannot_exceed_task_bound(self):
        self.configure(delegation=self.delegate('planner-over'))
        h, _ = self.run_task()
        self.assertEqual(h.state['calls'], 1)
        self.assertIn('AGENT_PLAN_INVALID', h.state['history'][0]['reasons'])

    def test_planner_cannot_choose_unknown_profile(self):
        self.configure(delegation=self.delegate('planner-unknown'))
        h, _ = self.run_task()
        self.assertEqual(h.state['calls'], 1)
        self.assertEqual(h.state['accepted'], 0)

    def test_planner_modifications_rejected(self):
        self.configure(delegation=self.delegate('planner-tamper'))
        h, _ = self.run_task()
        self.assertIn('AGENT_PLANNER_MODIFIED_FILES', h.state['history'][0]['reasons'])
        self.assertEqual(h.state['calls'], 1)

    def test_call_budget_stops_before_review(self):
        self.configure(budget={'max_attempts': 3, 'max_seconds': 30, 'stall_after': 3, 'max_calls': 1})
        h, result = self.run_task()
        self.assertEqual(result, 'CALL_BUDGET')
        self.assertEqual(h.state['calls'], 1)
        self.assertEqual(h.state['accepted'], 0)
        self.assertEqual(usage_summary(h.home)['calls'], 1)

    def test_call_budget_stops_delegated_worker(self):
        self.configure(delegation=self.delegate('planner-two'),
                    budget={'max_attempts': 3, 'max_seconds': 30, 'stall_after': 3, 'max_calls': 2})
        h, result = self.run_task()
        self.assertEqual(result, 'CALL_BUDGET')
        self.assertEqual(h.state['calls'], 2)
        self.assertEqual(h.state['accepted'], 0)

    def test_model_error_is_not_silently_rerouted(self):
        self.configure(agent=spec('worker-fail'))
        h, _ = self.run_task()
        self.assertEqual(h.state['calls'], 1)
        self.assertEqual(h.state['accepted'], 0)
        self.assertEqual(usage_summary(h.home)['unknown_usage_calls'], 1)

    def test_missing_usage_remains_unknown(self):
        self.configure(agent=spec('worker-unknown-usage'))
        h, result = self.run_task()
        self.assertEqual(result, 'COMPLETE')
        usage = usage_summary(h.home)
        self.assertEqual(usage['unknown_usage_calls'], 1)
        self.assertEqual(usage['input_tokens'], 100)
        self.assertIsNone(usage['cost_usd_estimate'])
        self.assertFalse(usage['usage_complete'])

    def test_missing_terminal_event_rejected(self):
        self.configure(agent=spec('worker-no-terminal'))
        h, _ = self.run_task()
        self.assertIn('AGENT_CODEX_PROTOCOL_ERROR', h.state['history'][0]['reasons'])

    def test_missing_final_rejected(self):
        self.configure(agent=spec('worker-missing-final'))
        h, _ = self.run_task()
        self.assertIn('AGENT_CODEX_PROTOCOL_ERROR', h.state['history'][0]['reasons'])

    def test_malformed_codex_review_rejected(self):
        self.configure(reviewer=spec('reviewer-malformed'))
        h, _ = self.run_task()
        self.assertIn('REVIEW_INVALID', h.state['history'][0]['reasons'])

    def test_codex_reviewer_cannot_edit(self):
        self.configure(reviewer=spec('reviewer-tamper'))
        h, _ = self.run_task()
        self.assertIn('REVIEWER_MODIFIED_FILES', h.state['history'][0]['reasons'])

    def test_timeout_accounts_unknown_call(self):
        worker = spec('worker-timeout')
        worker['timeout_s'] = .05
        self.configure(agent=worker)
        h, _ = self.run_task()
        self.assertEqual(h.state['calls'], 1)
        row = json.loads((h.home / 'calls/000001.json').read_text())
        self.assertEqual(row['status'], 'TIMEOUT')
        self.assertIsNone(row['usage'])

    def test_resume_does_not_double_count_usage(self):
        self.configure()
        first, _ = self.run_task()
        usage = usage_summary(first.home)
        second, result = self.run_task()
        self.assertEqual(result, 'COMPLETE')
        self.assertEqual(usage_summary(second.home), usage)

    def test_stage_override_bypasses_planner(self):
        c = self.configure(delegation=self.delegate())
        c['stages'][0]['agent'] = spec('worker-stage')
        self.configure(**c)
        h, result = self.run_task()
        self.assertEqual(result, 'COMPLETE')
        self.assertEqual(h.state['calls'], 2)
        self.assertIn('worker/worker-stage', usage_summary(h.home)['by_role_model'])

    def test_command_shape_sandboxes_and_schema(self):
        worker = build_command(spec('gpt-6.1-sol'), 'worker', Path('/tmp/final'))
        review = build_command(spec('gpt-6-astra'), 'reviewer', Path('/tmp/final'), Path('/tmp/schema'))
        self.assertIn('workspace-write', worker)
        self.assertIn('read-only', review)
        self.assertIn('--output-schema', review)
        self.assertIn('agents.enabled=false', worker)
        self.assertEqual(worker[-1], '-')
        self.assertNotIn('--yolo', worker)

    def test_invalid_token_usage_is_unknown(self):
        log = Path(self.temp.name) / 'events.log'
        log.write_text(json.dumps({'type': 'turn.completed', 'usage': {
            'input_tokens': 1, 'cached_input_tokens': 2, 'output_tokens': 1}}))
        self.assertIsNone(parse_events(log)['usage'])
        self.assertIsNone(estimate_cost(None, RATES))

    def test_doctor_checks_cli_without_model_call(self):
        from proofloop.codex import doctor
        from proofloop.core import invoke
        self.configure()
        h = Harness(self.root, self.config)
        result = doctor(h.config, h.home, invoke)
        self.assertTrue(result['ready'])
        self.assertEqual(len(result['checks']), 1)
        self.assertIn('CONTRACT-FIXTURE', result['checks'][0]['version_output'])
        self.assertFalse(h.state_path.exists())

    def test_doctor_missing_cli(self):
        from proofloop.codex import doctor
        from proofloop.core import invoke
        self.configure(agent={**spec('worker'), 'command': ['/definitely/missing/codex']}, reviewer=spec('review'))
        h = Harness(self.root, self.config)
        result = doctor(h.config, h.home, invoke)
        self.assertFalse(result['ready'])
        self.assertEqual(result['checks'][0]['status'], 'LAUNCH_ERROR')

    def test_init_codex_makes_no_model_call(self):
        from proofloop.codex import create_codex_demo
        path = create_codex_demo(Path(self.temp.name) / 'new-demo', 'gpt-6.1-sol', 'gpt-6-astra', 'gpt-6-astra')
        c = load_config(path)
        self.assertEqual(c['agent']['model'], 'gpt-6.1-sol')
        self.assertEqual(c['delegation']['max_tasks'], 2)
        self.assertEqual(git(path.parent, 'status', '--porcelain'), '')
        self.assertFalse((path.parent / '.git/proofloop').exists())

    def test_interrupted_call_keeps_unknown_usage(self):
        self.configure()
        def interrupted(*args, **kwargs):
            log = kwargs['log']
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text('{"type":"thread.started"}\n')
            raise KeyboardInterrupt()
        h = Harness(self.root, self.config)
        # Patch only role execution, not baseline check processes.
        from proofloop.codex import run_codex
        def stop(spec, role, wt, prompt, log, invoke, timeout):
            return run_codex(spec, role, wt, prompt, log, interrupted, timeout)
        with patch('proofloop.codex.run_codex', side_effect=stop):
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(KeyboardInterrupt):
                h.run()
        self.assertEqual(h.state['status'], 'INTERRUPTED')
        self.assertEqual(h.state['calls'], 1)
        self.assertEqual(usage_summary(h.home)['unknown_usage_calls'], 1)
        self.assertEqual(json.loads((h.home / 'calls/000001.json').read_text())['status'], 'INTERRUPTED_OR_ERROR')

    def test_legacy_calls_are_unattributed_and_unknown(self):
        home = Path(self.temp.name) / 'legacy'
        write_json(home / 'state.json', {'calls': 4})
        summary = usage_summary(home)
        self.assertEqual(summary['unattributed_calls'], 4)
        self.assertEqual(summary['unknown_usage_calls'], 4)
        self.assertIsNone(summary['cost_usd_estimate'])

    def test_no_prices_gives_unknown_cost(self):
        worker = spec('worker')
        worker.pop('pricing')
        self.configure(agent=worker)
        h, result = self.run_task()
        self.assertEqual(result, 'COMPLETE')
        usage = usage_summary(h.home)
        self.assertTrue(usage['usage_complete'])
        self.assertEqual(usage['unknown_cost_calls'], 1)
        self.assertIsNone(usage['cost_usd_estimate'])

    def test_context_budget_prevents_a_model_call(self):
        self.configure()
        h = Harness(self.root, self.config)
        h.initialize()
        row = h.model_call(h.config['agent'], 'worker', self.root, 'x' * 20000, h.home / 'oversize.log')
        self.assertEqual(row['status'], 'CONTEXT_BUDGET')
        self.assertEqual(h.state['calls'], 0)
        self.assertFalse((h.home / 'calls').exists())

    def test_mixed_codex_and_generic_workers(self):
        delegation = self.delegate('planner-two')
        delegation['workers']['qwen'] = {'command': ['{python}', 'demo_agent.py'], 'timeout_s': 10}
        # A provider-neutral worker follows the same stdin/cwd contract; no Qwen service is called.
        (self.root / 'demo_agent.py').write_text("from pathlib import Path\nimport sys\nsys.stdin.read()\nassert 'return sum(v)/len(v)' in Path('calculator.py').read_text()\nPath('calculator.py').write_text(Path('calculator.py').read_text() + '# reviewed by generic fixture\\n')\n")
        self.configure(delegation=delegation)
        h, result = self.run_task()
        self.assertEqual(result, 'COMPLETE')
        usage = usage_summary(h.home)
        self.assertEqual(usage['calls'], 4)
        self.assertEqual(usage['unknown_usage_calls'], 1)
        self.assertEqual(usage['by_role_model']['worker/qwen']['calls'], 1)
        self.assertIn('reviewed by generic fixture', git(self.root, 'show', h.ref + ':calculator.py'))

    def test_codex_validation(self):
        base = self.configure()
        invalid = [dict(spec('ok'), model=''), dict(spec('ok'), reasoning_effort='ultra'),
                   dict(spec('ok'), pricing={'input_per_million': 2}),
                   dict(spec('ok'), pricing={**RATES, 'output_per_million': -1})]
        for value in invalid:
            with self.subTest(value=value):
                write_json(self.config, {**base, 'agent': value})
                with self.assertRaises(HarnessError):
                    load_config(self.config)
