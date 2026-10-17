"""Exercise the real controller in real throwaway Git repositories."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from proofloop.core import Harness, HarnessError, git, invoke, load_config, write_json
from proofloop.demo import create_demo


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'repo'
        self.config = create_demo(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def configure(self, **updates):
        c = json.loads(self.config.read_text())
        c.update(updates)
        write_json(self.config, c)
        self.commit()
        return c

    def commit(self):
        git(self.root, 'add', '.')
        git(self.root, '-c', 'user.name=Test', '-c', 'user.email=test@localhost',
            'commit', '--allow-empty', '-m', 'test fixture')

    def agent(self, body):
        (self.root / 'demo_agent.py').write_text(body)
        self.commit()

    def run_harness(self, verify=False):
        h = Harness(self.root, self.config)
        with contextlib.redirect_stdout(io.StringIO()):
            status = h.run(verify_only=verify)
        return h, status

    def one_attempt(self):
        self.configure(budget={'max_attempts': 1, 'max_seconds': 20, 'stall_after': 3})

    def fixed_agent(self):
        self.agent("from pathlib import Path\nPath('calculator.py').write_text(\"def mean(v):\\n    if not v: raise ValueError('empty')\\n    return sum(v)/len(v)\\n\")\n")

    def test_reject_then_accept_and_preserve_checkout(self):
        original = (self.root / 'calculator.py').read_bytes()
        main = git(self.root, 'rev-parse', 'HEAD')
        h, status = self.run_harness()
        self.assertEqual(status, 'COMPLETE')
        self.assertEqual([x['decision'] for x in h.state['history']], ['REJECTED', 'ACCEPTED'])
        self.assertEqual(h.state['attempts'], 2)
        self.assertEqual(git(self.root, 'rev-parse', 'HEAD'), main)
        self.assertEqual((self.root / 'calculator.py').read_bytes(), original)
        self.assertIn('len(values)', git(self.root, 'show', h.ref + ':calculator.py'))
        self.assertTrue((h.home / 'runs/0002/diff.patch').exists())

    def test_resume_completed_reverifies_without_new_agent(self):
        h, _ = self.run_harness()
        again, status = self.run_harness()
        self.assertEqual(status, 'COMPLETE')
        self.assertEqual(again.state['calls'], h.state['calls'])
        self.assertEqual(len(again.state['history']), 2)

    def test_verify_does_not_call_agent(self):
        h, status = self.run_harness(True)
        self.assertEqual(status, 'CHECKS_FAILED')
        self.assertEqual(h.state['calls'], 0)
        self.assertFalse((h.home / 'runs').exists())

    def test_baseline_already_complete(self):
        (self.root / 'calculator.py').write_text('def mean(v):\n    if not v: raise ValueError()\n    return sum(v)/len(v)\n')
        self.commit()
        h, status = self.run_harness()
        self.assertEqual((status, h.state['calls']), ('COMPLETE', 0))

    def test_frozen_check_tampering_rejected(self):
        self.one_attempt()
        self.configure(writable=['**'])
        self.agent("from pathlib import Path\nPath('checks/mean.py').write_text('pass')\n")
        h, _ = self.run_harness()
        self.assertIn('PATH_POLICY:checks/mean.py', h.state['history'][0]['reasons'])
        self.assertEqual(h.state['accepted'], 0)

    def test_deleting_protected_file_rejected(self):
        self.one_attempt()
        self.agent("from pathlib import Path\nPath('checks/mean.py').unlink()\n")
        h, _ = self.run_harness()
        self.assertIn('PATH_POLICY:checks/mean.py', h.state['history'][0]['reasons'])

    def test_new_disallowed_file_rejected(self):
        self.one_attempt()
        self.agent("from pathlib import Path\nPath('surprise.txt').write_text('new')\n")
        h, _ = self.run_harness()
        self.assertIn('PATH_POLICY:surprise.txt', h.state['history'][0]['reasons'])

    def test_stall_on_no_change(self):
        self.configure(budget={'max_attempts': 5, 'max_seconds': 20, 'stall_after': 2})
        self.agent("print('done')\n")
        h, status = self.run_harness()
        self.assertEqual(status, 'STALLED')
        self.assertEqual(h.state['attempts'], 2)
        self.assertIn('NO_CHANGE', h.state['history'][0]['reasons'])

    def test_nonzero_agent_never_publishes(self):
        self.one_attempt()
        self.fixed_agent()
        with (self.root / 'demo_agent.py').open('a') as f:
            f.write('raise SystemExit(1)\n')
        self.commit()
        h, _ = self.run_harness()
        self.assertEqual(h.state['accepted'], 0)
        self.assertIn('AGENT_EXIT', h.state['history'][0]['reasons'])

    def test_regression_is_rejected(self):
        self.one_attempt()
        c = json.loads(self.config.read_text())
        (self.root / 'marker.txt').write_text('keep')
        (self.root / 'checks/marker.py').write_text("from pathlib import Path\nassert Path('marker.txt').read_text() == 'keep'\n")
        c['stages'].insert(0, {'id': 'marker', 'check': ['{python}', 'checks/marker.py']})
        c['writable'].append('marker.txt')
        self.configure(**c)
        self.fixed_agent()
        with (self.root / 'demo_agent.py').open('a') as f:
            f.write("Path('marker.txt').write_text('broken')\n")
        self.commit()
        h, _ = self.run_harness()
        self.assertIn('REGRESSION', h.state['history'][0]['reasons'])
        self.assertEqual(h.state['accepted'], 0)

    def reviewer(self, body):
        (self.root / 'review.py').write_text(body)
        self.configure(reviewer={'command': ['{python}', 'review.py'], 'timeout_s': 5})
        self.one_attempt()
        self.fixed_agent()

    def test_reviewer_approval(self):
        self.reviewer('print(\'{"verdict":"APPROVE","reason":"covered"}\')\n')
        h, status = self.run_harness()
        self.assertEqual(status, 'COMPLETE')
        self.assertEqual(h.state['calls'], 2)

    def test_reviewer_rejection(self):
        self.reviewer('print(\'{"verdict":"REJECT","reason":"missing edge case"}\')\n')
        h, _ = self.run_harness()
        self.assertIn('REVIEW_REJECTED', h.state['history'][0]['reasons'])

    def test_malformed_reviewer_fails_closed(self):
        self.reviewer("print('looks great!')\n")
        h, _ = self.run_harness()
        self.assertIn('REVIEW_INVALID', h.state['history'][0]['reasons'])

    def test_reviewer_changes_rejected(self):
        self.reviewer("from pathlib import Path\nPath('calculator.py').write_text('bad')\nprint('{\"verdict\":\"APPROVE\",\"reason\":\"ok\"}')\n")
        h, _ = self.run_harness()
        self.assertIn('REVIEWER_MODIFIED_FILES', h.state['history'][0]['reasons'])

    def test_config_drift_refused(self):
        self.run_harness(True)
        self.configure(goal='different task')
        with self.assertRaisesRegex(HarnessError, 'configuration changed'):
            self.run_harness()

    def test_dirty_checkout_refused(self):
        (self.root / 'calculator.py').write_text('dirty')
        with self.assertRaisesRegex(HarnessError, 'Commit or stash'):
            self.run_harness()

    def test_checked_out_result_branch_refused(self):
        h, _ = self.run_harness(True)
        git(self.root, 'switch', 'proofloop/fix-mean')
        with self.assertRaisesRegex(HarnessError, 'checked out'):
            self.run_harness()

    def test_branch_drift_on_resume_refused(self):
        h, _ = self.run_harness(True)
        (self.root / 'other').write_text('human work')
        self.commit()
        git(self.root, 'update-ref', h.ref, git(self.root, 'rev-parse', 'HEAD'))
        with self.assertRaisesRegex(HarnessError, 'moved outside'):
            self.run_harness()

    def test_compare_and_swap_failure_does_not_accept(self):
        self.one_attempt()
        self.fixed_agent()
        original_git = git
        def racing_git(repo, *args):
            if len(args) == 4 and args[:1] == ('update-ref',) and args[-1] != '0' * 40:
                raise HarnessError('simulated competing writer')
            return original_git(repo, *args)
        with patch('proofloop.core.git', side_effect=racing_git):
            h, _ = self.run_harness()
        self.assertIn('BRANCH_MOVED', h.state['history'][0]['reasons'])
        self.assertEqual(h.state['accepted'], 0)

    def test_write_ahead_reconciles_publication(self):
        h, _ = self.run_harness(True)
        old = dict(h.state)
        (self.root / 'new.txt').write_text('committed elsewhere')
        self.commit()
        new = git(self.root, 'rev-parse', 'HEAD')
        old['pending'] = {'new': new, 'state': {'accepted': 1, 'stalled': 0}}
        write_json(h.state_path, old)
        git(self.root, 'update-ref', h.ref, new)
        h.initialize()
        self.assertEqual(h.state['head'], new)
        self.assertEqual(h.state['accepted'], 1)
        self.assertNotIn('pending', h.state)

    def test_concurrent_run_lock(self):
        h = Harness(self.root, self.config)
        with h.lock():
            with self.assertRaisesRegex(HarnessError, 'stale lock'):
                with h.lock():
                    self.fail('second lock acquired')

    def test_verifier_cannot_rewrite_product(self):
        (self.root / 'checks/mean.py').write_text("from pathlib import Path\nPath('calculator.py').write_text('changed')\n")
        self.commit()
        with self.assertRaisesRegex(HarnessError, 'modified repository files'):
            self.run_harness()

    def test_timeout_is_explicit(self):
        row = invoke([sys.executable, '-c', 'import time; time.sleep(20)'], self.root, .05,
                     log=Path(self.tmp.name) / 'timeout.log')
        self.assertEqual(row['status'], 'TIMEOUT')
        self.assertLess(row['seconds'], 3)

    def test_unicode_log_tail(self):
        row = invoke([sys.executable, '-c', "print('斑马鱼' * 6000)"], self.root, 5,
                     log=Path(self.tmp.name) / 'unicode.log')
        self.assertEqual(row['returncode'], 0)
        self.assertLessEqual(len(row['tail']), 6000)

    def test_missing_executable(self):
        row = invoke(['/not/a/command'], self.root, 1, log=Path(self.tmp.name) / 'missing.log')
        self.assertEqual(row['status'], 'LAUNCH_ERROR')

    def test_interrupt_after_publication_recovers_decision(self):
        self.fixed_agent()
        original_git = git
        def interrupt_git(repo, *args):
            value = original_git(repo, *args)
            if len(args) == 4 and args[:1] == ('update-ref',) and args[-1] != '0' * 40:
                raise KeyboardInterrupt()
            return value
        with patch('proofloop.core.git', side_effect=interrupt_git):
            with self.assertRaises(KeyboardInterrupt):
                self.run_harness()
        h, status = self.run_harness()
        self.assertEqual(status, 'COMPLETE')
        self.assertEqual(h.state['accepted'], 1)
        self.assertEqual(h.state['calls'], 1)
        record = json.loads((h.home / 'runs/0001/decision.json').read_text())
        self.assertEqual(record['decision'], 'ACCEPTED')

    def test_interrupt_before_publication_rejects_prepared_record(self):
        self.fixed_agent()
        original_git = git
        def interrupt_git(repo, *args):
            if len(args) == 4 and args[:1] == ('update-ref',) and args[-1] != '0' * 40:
                raise KeyboardInterrupt()
            return original_git(repo, *args)
        with patch('proofloop.core.git', side_effect=interrupt_git):
            with self.assertRaises(KeyboardInterrupt):
                self.run_harness()
        h = Harness(self.root, self.config)
        h.initialize()
        self.assertEqual(h.state['accepted'], 0)
        record = json.loads((h.home / 'runs/0001/decision.json').read_text())
        self.assertEqual(record['reasons'], ['INTERRUPTED_BEFORE_PUBLICATION'])

    def test_cumulative_attempt_budget(self):
        self.one_attempt()
        h, status = self.run_harness()
        self.assertEqual(status, 'ATTEMPT_BUDGET')
        again, status = self.run_harness()
        self.assertEqual(status, 'ATTEMPT_BUDGET')
        self.assertEqual(again.state['calls'], 1)

    def test_expired_time_budget_launches_no_agent(self):
        h, _ = self.run_harness(True)
        h.state['seconds'] = h.config['budget']['max_seconds'] + 1
        write_json(h.state_path, h.state)
        again, status = self.run_harness()
        self.assertEqual(status, 'TIME_BUDGET')
        self.assertEqual(again.state['calls'], 0)

    def test_configuration_validation(self):
        base = json.loads(self.config.read_text())
        for update in [{'unknown': True}, {'version': 2}, {'writable': ['../escape']},
                       {'budget': {'max_attempts': -1}}, {'agent': {'command': 'shell string'}},
                       {'stages': [{'id': 'a', 'check': ['true'], 'depends_on': ['b']}]},
                       {'id': '../../bad'}]:
            with self.subTest(update=update):
                write_json(self.config, {**base, **update})
                with self.assertRaises(HarnessError):
                    load_config(self.config)


if __name__ == '__main__':
    unittest.main()
