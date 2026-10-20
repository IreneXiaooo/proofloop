import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from proofloop.core import HarnessError, git, write_json
from proofloop.codex import build_command, run_codex, usage_summary
from proofloop.evolution import Evolution, load_evolution, evaluation_result, reflection_result
from proofloop.evolution_demo import create_evolution_demo, EVALUATOR

ACTOR = str(Path(__file__).with_name('evolution_actor.py').resolve())
PACKAGE = str(Path(__file__).resolve().parents[1])


class EvolutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / 'repo'
        self.path = create_evolution_demo(self.repo)

    def tearDown(self):
        self.tmp.cleanup()

    def commit(self):
        git(self.repo, 'add', '.')
        git(self.repo, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@localhost',
            'commit', '--allow-empty', '-m', 'test configuration')

    def configure(self, mode=None, **overrides):
        c = json.loads(self.path.read_text())
        if mode:
            # Standalone subprocess fixture imports the source package explicitly.
            c['evolver'] = {'command':['{python}', '-c',
                'import runpy,sys;sys.path.insert(0,sys.argv.pop(1));runpy.run_path(sys.argv.pop(1),run_name="__main__")',
                PACKAGE, ACTOR, mode], 'timeout_s':2}
        for key, value in overrides.items():
            c[key] = value
        write_json(self.path, c)
        self.commit()
        return c

    def run_search(self):
        h = Evolution(self.repo, self.path)
        with contextlib.redirect_stdout(io.StringIO()):
            status = h.run()
        self.assertEqual(len([x for x in git(self.repo,'worktree','list','--porcelain').splitlines()
                              if x.startswith('worktree ')]), 1)
        return h, status

    def test_offline_dual_role_directed_improvement(self):
        self.configure()
        root = git(self.repo, 'rev-parse', 'HEAD')
        h, status = self.run_search()
        self.assertEqual(status, 'COMPLETE')
        self.assertEqual(h.state['calls'], 3)
        self.assertEqual(h.state['evaluations'], 5)
        self.assertEqual([n['score'] for n in h.state['nodes']], [1/3, 2/3, 1])
        self.assertEqual(h.state['best'], '0001-directed')
        self.assertEqual(git(self.repo, 'rev-parse', 'HEAD'), root)
        self.assertNotEqual(git(self.repo, 'rev-parse', h.ref), root)
        self.assertEqual((self.repo / 'harness.py').read_text(), git(self.repo, 'show', root+':harness.py')+'\n')
        reflection = json.loads((h.home/'0001-reflection/reflection.json').read_text())
        self.assertGreater(reflection['execution_reward'], 0)
        self.assertTrue((h.home/'0001-autonomous/diff.patch').is_file())
        self.assertEqual(usage_summary(h.home)['unknown_usage_calls'], 3)
        self.assertFalse((h.common/'proofloop/RUNNING.lock').exists())

    def test_keep_uses_no_directed_call(self):
        self.configure('keep')
        h,_=self.run_search()
        self.assertEqual(h.state['calls'], 2)
        self.assertEqual(h.state['evaluations'], 3)
        self.assertEqual(h.state['best'], '0001-autonomous')
        self.assertEqual(json.loads((h.home/'0001-reflection/reflection.json').read_text())['execution_reward'], 0)

    def test_no_activation_cannot_promote_or_get_positive_credit(self):
        self.configure('no-activation')
        h,_=self.run_search()
        node=h.state['nodes'][1]
        self.assertGreater(node['delta'], 0)
        self.assertEqual(node['execution_reward'], 0)
        self.assertEqual(node['decision'], 'NO_ACTIVATION')
        self.assertEqual(h.state['best'], 'root')

    def test_regression_is_archived_but_not_promoted(self):
        self.configure('regression')
        h,_=self.run_search()
        self.assertEqual(h.state['nodes'][1]['decision'],'REGRESSION')
        self.assertEqual(h.state['best'], 'root')
        self.assertEqual(git(self.repo,'rev-parse',f'refs/proofloop-evolution/json-harness/0001-autonomous'),
                         h.state['nodes'][1]['commit'])

    def test_no_change_scope_exit_and_startup_fail_closed(self):
        for mode in ['nochange','scope','exit','startup']:
            with self.subTest(mode=mode):
                c=self.configure(mode)
                c['id']='bad-'+mode
                write_json(self.path,c)
                self.commit()
                h,_=self.run_search()
                self.assertEqual(h.state['best'],'root')
                self.assertEqual(h.state['nodes'][1]['decision'],'INVALID')

    def test_frozen_evaluator_is_protected_even_with_broad_writable(self):
        c=self.configure('scope', writable=['**'], protected=['evolution.json'])
        h,_=self.run_search()
        self.assertEqual(h.state['nodes'][1]['error'],'PROPOSER_SCOPE_VIOLATION')
        self.assertIn('SystemExit',(h.home/'0001-autonomous/diff.patch').read_text())

    def test_invalid_or_mutating_reflector_cannot_request_a_revision(self):
        for mode in ['reflect-write','invalid-reflection','unknown-donor']:
            with self.subTest(mode=mode):
                c=self.configure(mode)
                c['id']=mode
                write_json(self.path,c)
                self.commit()
                h,_=self.run_search()
                self.assertEqual(h.state['calls'],2)
                self.assertTrue((h.home/'0001-reflection/error.json').is_file())
                self.assertEqual(len(h.state['nodes']),2)

    def test_crossover_records_donor_and_rechecks_directed_child(self):
        c=self.configure('crossover')
        c['budget'].update(max_rounds=2,max_calls=5,max_evaluations=9)
        write_json(self.path,c)
        self.commit()
        h,_=self.run_search()
        directed=h.state['nodes'][-1]
        self.assertEqual(directed['id'],'0002-directed')
        self.assertEqual(directed['donor'],'0001-autonomous')
        self.assertEqual(directed['parent'],'0002-autonomous')
        self.assertEqual(directed['score'],1)
        self.assertIn('parent_evaluation',directed)

    def test_matched_task_ids_executor_and_seeds_for_every_pair(self):
        c=self.configure()
        c['evaluation']['repeats']=2
        c['budget']['max_evaluations']=10
        write_json(self.path,c)
        self.commit()
        h,_=self.run_search()
        for kind in ['autonomous','directed']:
            for repeat in range(2):
                a=json.loads((h.home/f'0001-{kind}/parent-evaluation/{repeat}.request.json').read_text())
                b=json.loads((h.home/f'0001-{kind}/child-evaluation/{repeat}.request.json').read_text())
                a.pop('output'); b.pop('output')
                self.assertEqual(a,b)
                self.assertEqual(a['seed'],repeat)
        self.assertEqual(h.state['evaluations'],10)

    def test_evaluation_budget_reserves_complete_comparison(self):
        c=self.configure()
        c['budget']['max_evaluations']=2
        write_json(self.path,c); self.commit()
        h,status=self.run_search()
        self.assertEqual(status,'EVALUATION_BUDGET')
        self.assertEqual(h.state['calls'],0)
        self.assertEqual(h.state['evaluations'],1)

    def test_call_budget_stops_before_extra_model_launch(self):
        c=self.configure()
        c['budget']['max_calls']=1
        write_json(self.path,c); self.commit()
        h,_=self.run_search()
        self.assertEqual(h.state['calls'],1)
        self.assertTrue((h.home/'0001-reflection/error.json').is_file())
        self.assertEqual(h.state['best'],'0001-autonomous')

    def test_evaluator_mutation_is_fatal_and_never_promotes(self):
        self.configure()
        (self.repo/'evaluate.py').write_text(EVALUATOR+"\nPath('harness.py').write_text('bad')\n")
        self.commit()
        h=Evolution(self.repo,self.path)
        with self.assertRaisesRegex(HarnessError,'EVALUATOR_MODIFIED_HARNESS'):
            h.run()
        self.assertEqual(h.state['status'],'ERROR')
        self.assertEqual(git(self.repo,'rev-parse',h.ref),git(self.repo,'rev-parse','HEAD'))

    def test_missing_output_cannot_be_read_as_success(self):
        self.configure()
        (self.repo/'evaluate.py').write_text('pass\n')
        self.commit()
        h=Evolution(self.repo,self.path)
        with self.assertRaisesRegex(HarnessError,'Missing'):
            h.run()
        self.assertEqual(h.state['evaluations'],1)

    def test_interrupt_releases_lock_and_keeps_root(self):
        self.configure()
        h=Evolution(self.repo,self.path)
        with patch.object(h,'role_call',side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            h.run()
        self.assertEqual(h.state['status'],'INTERRUPTED')
        self.assertFalse((h.common/'proofloop/RUNNING.lock').exists())
        self.assertEqual(git(self.repo,'rev-parse',h.ref),git(self.repo,'rev-parse','HEAD'))

    def test_existing_id_is_rejected_without_resetting_budget(self):
        self.configure('keep')
        h,_=self.run_search()
        with self.assertRaisesRegex(HarnessError,'already exists'):
            Evolution(self.repo,self.path).run()
        self.assertEqual(json.loads(h.state_path.read_text())['calls'],2)

    def test_pool_is_bounded_and_keeps_root_and_champion(self):
        self.configure()
        h=Evolution(self.repo,self.path)
        h.state={'attempts':2,'best':'n5','nodes':[{'id':'root','score':0,'depth':0}] +
                 [{'id':f'n{i}','score':i/10,'depth':i} for i in range(1,8)]}
        h.config['search']['pool_size']=3
        h.select_parent()
        self.assertEqual(len(h.state['pool']),3)
        self.assertIn('root',h.state['pool']); self.assertIn('n5',h.state['pool'])

    def test_codex_roles_have_distinct_permissions_and_output_schemas(self):
        spec={'model':'fixture'}
        for role,permission in [('proposer','workspace-write'),('reflector','read-only')]:
            self.assertIn(permission,build_command(spec,role,Path('final')))

    def test_changed_executor_identity_and_task_membership_are_rejected(self):
        c=self.configure()
        row={'executor':{'name':'different'},'tasks':[]}
        with self.assertRaises(HarnessError):
            evaluation_result(row,c['evaluation'])
        row['executor']=c['evaluation']['executor']
        row['tasks']=[{'id':'plain','score':1,'active_mechanisms':[]}] * 3
        with self.assertRaises(HarnessError):
            evaluation_result(row,c['evaluation'])

    def test_time_budget_kills_model_and_keeps_root(self):
        c=self.configure('slow')
        c['budget']['max_seconds']=.8
        write_json(self.path,c); self.commit()
        h,_=self.run_search()
        self.assertEqual(h.state['best'],'root')
        self.assertEqual(h.state['nodes'][1]['error'],'PROPOSER_TIMEOUT')

    def test_result_branch_movement_is_not_overwritten(self):
        self.configure('keep')
        h=Evolution(self.repo,self.path)
        ensure=h.ensure_detached
        calls=0
        def move_ref():
            nonlocal calls
            calls+=1
            if calls==2:
                root=git(self.repo,'rev-parse','HEAD')
                tree=git(self.repo,'rev-parse','HEAD^{tree}')
                moved=git(self.repo,'-c','user.name=Fixture','-c','user.email=fixture@localhost',
                          'commit-tree',tree,'-p',root,'-m','external branch movement')
                git(self.repo,'update-ref',h.ref,moved)
            return ensure()
        with patch.object(h,'ensure_detached',side_effect=move_ref), contextlib.redirect_stdout(io.StringIO()), self.assertRaises(HarnessError):
            h.run()
        self.assertEqual(json.loads(h.state_path.read_text())['status'],'PUBLICATION_CONFLICT')
        self.assertNotEqual(git(self.repo,'rev-parse',h.ref),h.state['nodes'][1]['commit'])

    def test_codex_structured_evolution_roles_use_schema_files(self):
        from proofloop.core import invoke
        fake=Path(__file__).with_name('fake_codex.py').resolve()
        # The fixture returns non-evolution JSON, but transport/schema routing is real.
        for role in ['proposer','reflector']:
            log=Path(self.tmp.name)/(role+'.log')
            result=run_codex({'command':['{python}',str(fake)],'model':'fixture'},
                             role,self.repo,'{}',log,invoke,5)
            self.assertEqual(result['status'],'OK')
            schema=json.loads(log.with_suffix('.schema.json').read_text())
            self.assertIn('strategy' if role=='proposer' else 'action',schema['properties'])

    def test_config_validation_and_protocol_rejections(self):
        c=self.configure()
        bad=[('search',{'pool_size':1}),('search',{'root_share':1}),('search',{'seed':True}),
             ('evaluation',{**c['evaluation'],'tasks':['x','x']}),
             ('evaluation',{**c['evaluation'],'repeats':True}),('writable',[]),('protected',[]),
             ('budget',{**c['budget'],'max_calls':0}),('surprise',True)]
        for key,value in bad:
            write_json(self.path,{**c,key:value})
            with self.subTest(key=key,value=value), self.assertRaises(HarnessError):
                load_evolution(self.path)
        row={'executor':c['evaluation']['executor'],'tasks':[
            {'id':t,'score':1,'active_mechanisms':[]} for t in c['evaluation']['tasks']]}
        evaluation_result(row,c['evaluation'])
        for val in [True,float('nan'),-1,2,'1']:
            row['tasks'][0]['score']=val
            with self.assertRaises(HarnessError):
                evaluation_result(row,c['evaluation'])
        with self.assertRaises(HarnessError):
            reflection_result({'action':'crossover','directive':'do it','donor':'unknown'}, {})


if __name__ == '__main__':
    unittest.main()
