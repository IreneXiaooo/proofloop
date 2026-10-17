import contextlib
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from proofloop.core import Harness, HarnessError, git, invoke, load_config, write_json
from proofloop.demo import create_demo
from proofloop.codex import build_command, usage_summary

FAKE = str(Path(__file__).with_name('fake_codex.py').resolve())
WORKER = str(Path(__file__).with_name('parallel_worker.py').resolve())


class ParallelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'repo'
        self.config = create_demo(self.root)
        self.sync = Path(self.tmp.name) / 'sync'
        (self.root / 'output').mkdir()
        (self.root / 'output/shared.txt').write_text('base\n')
        (self.root / 'output/alpha.txt').write_text('0')
        (self.root / 'output/beta.txt').write_text('0')
        (self.root / 'output/keep.txt').write_text('keep')
        self.expected = "assert p('shared.txt') == 'a+b\\n'\n"

    def tearDown(self):
        self.tmp.cleanup()

    def spec(self, mode, label, role='worker'):
        return {'command': ['{python}', WORKER, role, mode, label, str(self.sync)], 'timeout_s': 10}

    def configure(self, mode='conflict', resolver=None, retries=1, max_calls=8, max_parallel=2, planner='planner-two'):
        check = "from pathlib import Path\np = lambda name: Path('output',name).read_text()\n" + self.expected
        (self.root / 'checks/parallel.py').write_text(check)
        (self.root / 'checks/keep.py').write_text("from pathlib import Path\nassert Path('output/keep.txt').read_text() == 'keep'\n")
        c = json.loads(self.config.read_text())
        c['writable'] = ['output/**']
        c['protected'] = ['checks/**', 'task.json', 'demo_agent.py']
        c['stages'] = [{'id':'keep','check':['{python}','checks/keep.py']},
                       {'id':'behavior','check':['{python}','checks/parallel.py'], 'depends_on':['keep']}]
        c['budget'] = {'max_attempts':1,'max_calls':max_calls,'max_seconds':30,'stall_after':3}
        c['delegation'] = {'planner': {'adapter':'codex','command':['{python}',FAKE], 'model':planner,'timeout_s':10},
                           'workers': {'a':self.spec(mode,'a'),'b':self.spec(mode,'b')},
                           'max_tasks':2,'execution':'parallel','max_parallel':max_parallel}
        if resolver:
            c['delegation']['conflict_resolution'] = {'strategy':'resolve','resolver':self.spec(resolver,'r','resolver'),
                                                      'max_attempts':retries}
        write_json(self.config,c)
        self.commit()
        return c

    def commit(self):
        git(self.root,'add','.')
        git(self.root,'-c','user.name=Fixture','-c','user.email=fixture@localhost','commit','--allow-empty','-m','parallel fixture')

    def run_task(self):
        h=Harness(self.root,self.config)
        with contextlib.redirect_stdout(io.StringIO()):
            status=h.run()
        return h,status

    def manifest(self,h):
        return json.loads((h.home/'runs/0001/parallel.json').read_text())

    def test_parallel_barrier_and_isolated_checkouts(self):
        self.expected="assert p('alpha.txt') == 'a'\nassert p('beta.txt') == 'b'\n"
        self.configure('barrier')
        original=git(self.root,'rev-parse','HEAD')
        h,status=self.run_task()
        self.assertEqual(status,'COMPLETE')
        left=json.loads((self.sync/'a-start.json').read_text())
        right=json.loads((self.sync/'b-start.json').read_text())
        self.assertNotEqual(left['cwd'],right['cwd'])
        self.assertNotEqual(Path(left['cwd']),self.root)
        self.assertEqual(git(self.root,'rev-parse','HEAD'),original)
        self.assertEqual((self.root/'output/alpha.txt').read_text(),'0')
        self.assertEqual(len([l for l in git(self.root,'worktree','list','--porcelain').splitlines() if l.startswith('worktree ')]),1)
        self.assertEqual(h.state['calls'],3)
        self.assertEqual(self.manifest(h)['status'],'MERGED_PENDING_VERIFICATION')
        self.assertTrue((h.home/'runs/0001/worker-1.patch').exists())

    def test_conflict_rejected_without_resolver(self):
        self.configure()
        h,_=self.run_task()
        self.assertEqual(h.state['accepted'],0)
        self.assertIn('AGENT_MERGE_CONFLICT',h.state['history'][0]['reasons'])
        self.assertEqual(self.manifest(h)['merges'][1]['merge']['conflicts'],['output/shared.txt'])

    def test_conflict_resolution_runs_then_verifies(self):
        self.configure(resolver='correct')
        h,status=self.run_task()
        self.assertEqual(status,'COMPLETE')
        self.assertEqual(h.state['calls'],4)
        self.assertEqual(git(self.root,'show',h.ref+':output/shared.txt'),'a+b')
        self.assertEqual(usage_summary(h.home)['by_role_model']['resolver/command']['calls'],1)
        self.assertEqual(self.manifest(h)['merges'][1]['resolution']['status'],'OK')

    def test_nonoverlapping_same_file_edits_merge_without_resolver(self):
        lines=['base']+[f'line-{i}' for i in range(12)]+['tail']
        (self.root/'output/shared.txt').write_text('\n'.join(lines)+'\n')
        self.expected="assert p('shared.txt').splitlines()[0] == 'a'\nassert p('shared.txt').splitlines()[-1] == 'b'\n"
        self.configure('nonoverlap')
        h,status=self.run_task()
        self.assertEqual(status,'COMPLETE')
        self.assertEqual(h.state['calls'],3)

    def test_resolver_cannot_change_nonconflict_file(self):
        self.configure(resolver='scope')
        h,_=self.run_task()
        self.assertIn('AGENT_RESOLVER_SCOPE_VIOLATION',h.state['history'][0]['reasons'])
        self.assertEqual(h.state['accepted'],0)

    def test_add_add_text_conflict_resolves(self):
        self.expected="assert p('new.txt') == 'a+b\\n'\n"
        self.configure('add-conflict',resolver='correct')
        h,status=self.run_task()
        self.assertEqual(status,'COMPLETE')
        self.assertEqual(git(self.root,'show',h.ref+':output/new.txt'),'a+b')

    def test_binary_conflicts_stop_without_resolver_call(self):
        self.configure('binary',resolver='correct')
        h,_=self.run_task()
        self.assertIn('AGENT_UNSUPPORTED_CONFLICT',h.state['history'][0]['reasons'])
        self.assertEqual(h.state['calls'],3)

    def test_modify_delete_conflict_stops(self):
        self.configure('delete-conflict',resolver='correct')
        h,_=self.run_task()
        self.assertIn('AGENT_UNSUPPORTED_CONFLICT',h.state['history'][0]['reasons'])
        self.assertEqual(h.state['calls'],3)

    def test_rename_rename_conflict_stops(self):
        self.configure('rename-conflict',resolver='correct')
        h,_=self.run_task()
        self.assertIn('AGENT_UNSUPPORTED_CONFLICT',h.state['history'][0]['reasons'])
        self.assertEqual(h.state['accepted'],0)

    def test_unresolved_markers_are_rejected(self):
        self.configure(resolver='markers')
        h,_=self.run_task()
        self.assertIn('AGENT_CONFLICT_UNRESOLVED',h.state['history'][0]['reasons'])
        self.assertEqual(h.state['calls'],4)

    def test_unchanged_conflict_is_rejected(self):
        self.configure(resolver='untouched')
        h,_=self.run_task()
        self.assertIn('AGENT_CONFLICT_UNRESOLVED',h.state['history'][0]['reasons'])

    def test_resolver_retries_are_bounded_and_can_repair(self):
        self.configure(resolver='retry',retries=2)
        h,status=self.run_task()
        self.assertEqual(status,'COMPLETE')
        self.assertEqual(h.state['calls'],5)
        self.assertEqual(usage_summary(h.home)['by_role_model']['resolver/command']['calls'],2)

    def test_failed_resolver_rejects_candidate(self):
        self.configure(resolver='fail')
        h,_=self.run_task()
        self.assertIn('AGENT_RESOLVER_EXIT',h.state['history'][0]['reasons'])
        self.assertEqual(h.state['accepted'],0)

    def test_resolver_cannot_edit_frozen_checks(self):
        self.configure(resolver='protected')
        h,_=self.run_task()
        self.assertIn('AGENT_RESOLVER_SCOPE_VIOLATION',h.state['history'][0]['reasons'])
        self.assertNotEqual(git(self.root,'show',h.ref+':checks/parallel.py'),'pass')

    def test_resolved_text_must_pass_behavior(self):
        self.configure(resolver='bad')
        h,_=self.run_task()
        self.assertIn('NO_NEW_PASS',h.state['history'][0]['reasons'])
        self.assertEqual(h.state['accepted'],0)
        self.assertEqual((self.root/'output/shared.txt').read_text(),'base\n')

    def test_combined_candidate_cannot_regress(self):
        self.configure('regression',resolver='correct')
        h,_=self.run_task()
        self.assertIn('REGRESSION',h.state['history'][0]['reasons'])
        self.assertEqual(h.state['accepted'],0)
        self.assertEqual(git(self.root,'show',h.ref+':output/keep.txt'),'keep')

    def test_worker_frozen_file_edit_rejects_whole_batch(self):
        self.configure('protected',resolver='correct')
        h,_=self.run_task()
        self.assertIn('AGENT_WORKER_PATH_POLICY',h.state['history'][0]['reasons'])
        self.assertEqual(h.state['accepted'],0)
        self.assertNotEqual(git(self.root,'show',h.ref+':checks/parallel.py'),'pass')

    def test_worker_failure_cancels_running_sibling(self):
        self.configure('cancel')
        h,_=self.run_task()
        records=[json.loads(p.read_text()) for p in (h.home/'calls').glob('*.json')]
        self.assertTrue(any(r['status']=='CANCELLED' for r in records))
        self.assertEqual(h.state['accepted'],0)
        self.assertFalse((self.sync/'a-finish').exists())
        self.assertEqual(len([l for l in git(self.root,'worktree','list','--porcelain').splitlines() if l.startswith('worktree ')]),1)

    def test_workers_do_not_launch_when_batch_exceeds_call_budget(self):
        self.configure(max_calls=2)
        h,_=self.run_task()
        self.assertEqual(h.state['calls'],1)  # planner only
        self.assertFalse(self.sync.exists())
        self.assertIn('AGENT_CALL_BUDGET',h.state['history'][0]['reasons'])

    def test_no_resolver_launch_when_call_budget_exhausted(self):
        self.configure(resolver='correct',max_calls=3)
        h,_=self.run_task()
        self.assertEqual(h.state['calls'],3)
        self.assertIn('AGENT_CALL_BUDGET',h.state['history'][0]['reasons'])

    def test_review_sees_staged_parallel_diff(self):
        self.expected="assert p('alpha.txt') == 'a'\nassert p('beta.txt') == 'b'\n"
        c=self.configure('disjoint')
        c['reviewer']={'command':['{python}','-c',
            "import subprocess,json; diff=subprocess.check_output(['git','diff','HEAD']).decode(); assert 'alpha.txt' in diff and 'beta.txt' in diff; print(json.dumps({'verdict':'APPROVE','reason':'fixture inspected staged diff'}))"], 'timeout_s':10}
        write_json(self.config,c);self.commit()
        h,status=self.run_task()
        self.assertEqual(status,'COMPLETE')
        self.assertEqual(h.state['calls'],4)

    def test_interrupt_cancels_processes_and_cleans_worktrees(self):
        self.configure('slow')
        h=Harness(self.root,self.config)
        def stop_when_started(futures):
            deadline=time.monotonic()+5
            while len(list(self.sync.glob('*-start.json'))) < 2:
                if time.monotonic()>deadline:
                    raise AssertionError('worker processes did not start')
                time.sleep(.01)
            raise KeyboardInterrupt()
        with patch('proofloop.parallel.as_completed',side_effect=stop_when_started):
            with contextlib.redirect_stdout(io.StringIO()),self.assertRaises(KeyboardInterrupt):
                h.run()
        self.assertEqual(h.state['status'],'INTERRUPTED')
        self.assertTrue(all(json.loads(p.read_text())['status'] in {'OK','CANCELLED'} for p in (h.home/'calls').glob('*.json')))
        self.assertFalse((self.sync/'a-finish').exists())
        self.assertEqual(len([l for l in git(self.root,'worktree','list','--porcelain').splitlines() if l.startswith('worktree ')]),1)

    def test_resolver_codex_uses_editing_sandbox(self):
        argv=build_command({'adapter':'codex','model':'gpt-6-astra'},'resolver',Path('/tmp/final'))
        self.assertIn('workspace-write',argv)
        self.assertIn('agents.enabled=false',argv)

    def test_parallel_config_validation(self):
        c=self.configure()
        for update in [{'max_parallel':0},{'max_parallel':9},{'execution':'unknown'},{'execution':[]},
                       {'conflict_resolution':{'strategy':'ours'}},{'conflict_resolution':{'strategy':[]}},
                       {'conflict_resolution':{'strategy':'resolve','resolver':self.spec('correct','r','resolver'),'max_attempts':4}}]:
            with self.subTest(update=update):
                write_json(self.config,{**c,'delegation':{**c['delegation'],**update}})
                with self.assertRaises(HarnessError):load_config(self.config)

    def test_concurrency_cap_atomic_call_ids_and_plan_order(self):
        self.expected="assert all(p('new-'+name+'.txt') == name for name in ['a','b','c'])\n"
        c=self.configure('bounded',planner='planner-three',max_calls=4)
        c['delegation']['max_tasks']=3
        c['delegation']['workers']['c']=self.spec('bounded','c')
        write_json(self.config,c);self.commit()
        h,status=self.run_task()
        self.assertEqual(status,'COMPLETE')
        manifest=self.manifest(h)
        self.assertEqual([m['worker'] for m in manifest['merges']],[1,2,3])
        intervals=[(r['started_seconds'],r['finished_seconds']) for r in manifest['workers']]
        events=sorted([(a,1) for a,b in intervals]+[(b,-1) for a,b in intervals])
        active=peak=0
        for _,delta in events:
            active+=delta;peak=max(peak,active)
        self.assertEqual(peak,2)
        records=[json.loads(p.read_text()) for p in (h.home/'calls').glob('*.json')]
        self.assertEqual(sorted(r['call'] for r in records),[1,2,3,4])
        self.assertEqual(usage_summary(h.home)['calls'],4)
        self.assertEqual(h.state['calls'],4)

    def test_worker_timeout_cancels_and_rejects(self):
        c=self.configure('slow')
        for spec in c['delegation']['workers'].values():spec['timeout_s']=.3
        write_json(self.config,c);self.commit()
        h,_=self.run_task()
        records=[json.loads(p.read_text()) for p in (h.home/'calls').glob('*.json')]
        self.assertTrue(any(r['status']=='TIMEOUT' for r in records))
        self.assertEqual(h.state['accepted'],0)
        self.assertFalse((self.sync/'a-finish').exists())

    def test_merge_error_does_not_publish(self):
        self.expected="assert p('alpha.txt') == 'a'\nassert p('beta.txt') == 'b'\n"
        self.configure('disjoint')
        with patch('proofloop.parallel.merge_tree',return_value={'returncode':1,'status':'MERGE_ERROR','seconds':0,'tail':''}):
            h,_=self.run_task()
        self.assertEqual(h.state['accepted'],0)
        self.assertIn('AGENT_MERGE_ERROR',h.state['history'][0]['reasons'])

    def test_offline_parallel_demo(self):
        from proofloop.demo import create_parallel_demo
        root=Path(self.tmp.name)/'offline-demo'
        path=create_parallel_demo(root)
        h=Harness(root,path)
        with contextlib.redirect_stdout(io.StringIO()):status=h.run()
        self.assertEqual(status,'COMPLETE')
        self.assertEqual(h.state['calls'],4)
        manifest=json.loads((h.home/'runs/0001/parallel.json').read_text())
        self.assertEqual(manifest['merges'][1]['resolution']['status'],'OK')

    def test_parallel_setup_requires_planner_and_configures_resolver(self):
        from proofloop.codex import create_codex_demo
        with self.assertRaises(HarnessError):
            create_codex_demo(Path(self.tmp.name)/'bad-demo','sol','astra',parallel=True)
        self.assertFalse((Path(self.tmp.name)/'bad-demo').exists())
        path=create_codex_demo(Path(self.tmp.name)/'configured-demo','sol','astra','astra',parallel=True,resolver_model='astra')
        c=load_config(path)
        self.assertEqual(c['delegation']['execution'],'parallel')
        self.assertEqual(c['delegation']['conflict_resolution']['max_attempts'],1)
        self.assertEqual(c['delegation']['conflict_resolution']['resolver']['model'],'astra')


if __name__=='__main__':
    unittest.main()
