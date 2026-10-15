"""Single explicit sandbox attempt per candidate; unknown outcomes never retry."""
import hashlib
import json
from ..candidate_verification import verify_candidate
from ..util import utcnow


def contract(rt, mission):
    if mission['lifecycle']['phase'] != 'CANDIDATE_REVIEW' or verify_candidate(rt.verifier, mission)['status'] != 'PASS':
        raise ValueError('verified_candidate_required')
    path = rt.control.workspace / mission['identity']['mission_id'] / 'candidate-report.json'
    raw = path.read_bytes(); plan = json.loads(raw)['sandbox_plan']
    if plan is None: raise ValueError('bound_test_commands_required')
    return plan, hashlib.sha256(raw).hexdigest()


def run_candidate_tests(rt, mission_id):
    with rt.missions.execution_lock(mission_id):
        mission = rt.missions.load(mission_id)
        try: plan, sha = contract(rt, mission)
        except Exception as exc: return {'status': 'blocked', 'reason': str(exc)}
        attempt = mission['execution'].get('candidate_test')
        if attempt:
            if attempt['plan_digest'] != plan['plan_digest'] or attempt['preparation_sha256'] != sha:
                return {'status': 'blocked', 'reason': 'candidate_test_contract_changed'}
            if attempt['status'] == 'RUNNING':
                return {'status': 'blocked', 'reason': 'UNKNOWN_TEST_OUTCOME', 'attempt': attempt}
            if attempt['status'] in {'FINISHED', 'FAILED'}:
                verified = rt.sandbox.verify(mission_id, attempt['job_id'], attempt['report_sha256'], plan['plan_digest']) if attempt['status'] == 'FINISHED' else {'status':'failed'}
                return {'status': verified['status'], 'verification': verified,
                        'attempt': attempt, 'reused': True, 'ready_for_merge': False}
        else:
            attempt = {'schema': 1, 'plan_digest': plan['plan_digest'], 'preparation_sha256': sha,
                       'status': 'WAITING', 'created_at': utcnow()}
            mission['execution']['candidate_test'] = attempt
        health = rt.sandbox.doctor()
        if not health['execution_ready']:
            rt.missions.save(mission)
            return {'status': 'blocked', 'sandbox': health, 'attempt': attempt}
        attempt['status'] = 'RUNNING'; rt.missions.save(mission)
        token = mission['execution'].get('approval_token')
        out = rt.tools.execute('sandbox', mission_id, 'run', {'plan': plan}, token)
        if token and token.get('status') == 'used': mission['execution'].pop('approval_token', None)
        if out['status'] in {'captain_required', 'blocked'}:
            attempt['status'] = 'WAITING'
            if out.get('gate'):
                gate = out['gate']
                if not any(g['request']['exact_action'] == gate['request']['exact_action'] and g['request']['targets'] == gate['request']['targets'] for g in mission['human_gates']['pending']):
                    mission['human_gates']['pending'].append(gate)
        else:
            attempt['status'] = 'FAILED'; attempt['result_status'] = out['status']
            record = out.get('sandbox')
            if record and record.get('job_id'):
                attempt['job_id'] = record['job_id']
                attempt['report_sha256'] = hashlib.sha256(rt.sandbox.receipt(record['job_id'])).hexdigest()
                verified = rt.sandbox.verify(mission_id, attempt['job_id'], attempt['report_sha256'], plan['plan_digest'])
                attempt['verification'] = verified
                if verified['status'] == 'completed': attempt['status'] = 'FINISHED'
            else: attempt['reason'] = out.get('error', 'no_confirmed_sandbox_result')
            attempt['finished_at'] = utcnow()
        rt.missions.save(mission)
        rt.audit.append('CANDIDATE_TEST_CHECKPOINT', component='candidate-tests', mission_id=mission_id,
                        payload={'status': attempt['status'], 'plan_digest': attempt['plan_digest'], 'job_id': attempt.get('job_id')})
        return dict(out, attempt=attempt, ready_for_merge=False)


def verify_candidate_tests(rt, mission_id):
    with rt.missions.execution_lock(mission_id):
        mission = rt.missions.load(mission_id)
        try: plan, sha = contract(rt, mission)
        except Exception as exc: return {'status': 'failed', 'reason': str(exc), 'ready_for_merge': False}
        attempt = mission['execution'].get('candidate_test') or {}
        if attempt.get('status') != 'FINISHED' or sha != attempt.get('preparation_sha256') or plan['plan_digest'] != attempt.get('plan_digest'):
            return {'status': 'failed', 'reason': 'completed_bound_test_required', 'ready_for_merge': False}
        return rt.sandbox.verify(mission_id, attempt['job_id'], attempt['report_sha256'], attempt['plan_digest'])
