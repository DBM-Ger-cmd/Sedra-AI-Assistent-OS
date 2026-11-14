from __future__ import annotations
import argparse
import json
from pathlib import Path
from .runtime import SedraRuntime


def runtime_from_args(args):
    root = Path(args.root).resolve()
    arch = Path(args.architecture).resolve() if args.architecture else None
    return SedraRuntime(root, arch)


def mission_inputs(args):
    if args.candidate_request:
        if args.project_path is not None or args.files is not None:
            raise ValueError('candidate_request_cannot_mix_with_inspection_flags')
        with Path(args.candidate_request).open('rb') as stream:
            raw = stream.read(1048577)
        if len(raw) > 1048576:
            raise ValueError('candidate_request_file_too_large')
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError('candidate_request_object_required')
        return value
    return {'project_path': args.project_path, 'files': args.files} if args.project_path is not None or args.files is not None else None


def desk_command(args):
    from . import uix_clients
    try:
        if args.cmd == 'objects':
            body = {'type': args.type, **({'id': args.id} if args.id else {})}
            path = '/api/objects'
        else:
            extra = json.loads(args.args)
            if not isinstance(extra, dict):
                raise ValueError('args_must_be_an_object')
            body = {'type': args.type, 'verb': args.verb, 'args': extra, **({} if args.id == '-' else {'id': args.id})}
            path = '/api/actions'
        status, out = uix_clients.call(Path(args.root).resolve(), 'cli', path, body)
    except ValueError as exc:
        print(json.dumps({'status': 'refused', 'error': str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if status == 200 else 2


def code_stand_command(args):
    from .harness.code_stand import konsole, utf8_ausgabe
    utf8_ausgabe()
    code, text = konsole(args.root, args.projekt, args.uebernehmen)
    print(text)
    return code


def main(argv=None):
    p = argparse.ArgumentParser(prog='sedra')
    p.add_argument('--root', default='.')
    p.add_argument('--architecture', default=None)
    sub = p.add_subparsers(dest='cmd', required=True)

    sub.add_parser('doctor')
    bf = sub.add_parser('buildflow', help='the build workflow: tasks, queue, build, report, adoption (docs/BUILDFLOW_2026-10-13.md)')
    bf.add_argument('rest', nargs=argparse.REMAINDER)
    d = sub.add_parser('demo')
    d.add_argument('--intent', default='Create a SEDRA demo artifact')
    d.add_argument('--class', dest='mission_class', default='S1', choices=['S0', 'S1', 'S2'])
    n = sub.add_parser('new-mission')
    n.add_argument('--intent', required=True)
    n.add_argument('--objective')
    n.add_argument('--class', dest='mission_class', default='S1', choices=['S0', 'S1', 'S2'])
    n.add_argument('--project-path')
    n.add_argument('--files', nargs='*')
    n.add_argument('--candidate-request')
    n.add_argument('--plan-request')
    mi = sub.add_parser('mission-inputs')
    mi.add_argument('mission_id')
    mi.add_argument('--project-path')
    mi.add_argument('--files', nargs='*')
    mi.add_argument('--candidate-request')
    r = sub.add_parser('run')
    r.add_argument('mission_id')
    r.add_argument('--max-steps', type=int, default=20)
    rs = sub.add_parser('resume')
    rs.add_argument('mission_id')
    rs.add_argument('--max-steps', type=int, default=20)
    fc = sub.add_parser('execution-check')
    fc.add_argument('mission_id')
    fc.add_argument('--request', required=True)
    l = sub.add_parser('list-missions')
    a = sub.add_parser('approve')
    a.add_argument('mission_id')
    a.add_argument('--gate-id')
    a = sub.add_parser('model-remove-preview', help='plan the safe removal of model files (recipe ids or gguf paths)')
    a.add_argument('targets', nargs='+')
    a = sub.add_parser('model-remove', help='move the files of an approved plan into quarantine')
    a.add_argument('mission_id')
    a.add_argument('--plan', required=True)
    a = sub.add_parser('model-restore', help='put a removal back')
    a.add_argument('removal_id')
    a = sub.add_parser('routing-profile', help='show or switch the model combination (local_config/routing_profiles.yaml)')
    a.add_argument('action', choices=['list', 'use'])
    a.add_argument('name', nargs='?')
    rc = sub.add_parser('recover')
    rc.add_argument('mission_id')
    rc.add_argument('--resolution', required=True, choices=['abort', 'retry_readonly'])
    cs = sub.add_parser('candidate-status')
    cs.add_argument('mission_id')
    cc = sub.add_parser('candidate-cleanup')
    cc.add_argument('mission_id')
    cc.add_argument('--attempt-id', required=True)
    ct = sub.add_parser('candidate-test')
    ct.add_argument('mission_id')
    cv = sub.add_parser('candidate-test-verify')
    cv.add_argument('mission_id')
    for name in ('accept-preview', 'accept', 'rollback-preview', 'rollback'):
        ap = sub.add_parser('candidate-' + name)
        ap.add_argument('mission_id')
        ap.add_argument('--plan')
    for name in ('integrate-preview', 'integrate', 'rollback-preview', 'rollback'):
        si = sub.add_parser('self-' + name)
        si.add_argument('mission_id')
        si.add_argument('--plan')
    sub.add_parser('list-tools')
    sub.add_parser('list-skills')
    sub.add_parser('list-topics')
    tp = sub.add_parser('topic-propose')
    tp.add_argument('--title', required=True)
    tp.add_argument('--description', default='')
    cr = sub.add_parser('route')
    cr.add_argument('--intent', required=True)
    cr.add_argument('--objective')
    cr.add_argument('--topic')
    cr.add_argument('--class', dest='mission_class', default='S1', choices=['S0', 'S1', 'S2'])
    mr = sub.add_parser('mission-route')
    mr.add_argument('mission_id')
    tc = sub.add_parser('tool-call')
    tc.add_argument('mission_id')
    tc.add_argument('tool')
    tc.add_argument('operation')
    tc.add_argument('--args-json', default='{}')
    sub.add_parser('hardware')
    sub.add_parser('hardware-state')
    sub.add_parser('hardware-inventory')
    sub.add_parser('hardware-capabilities')
    sub.add_parser('hardware-profiles')
    hp = sub.add_parser('hardware-preview')
    hp.add_argument('--profile-id', required=True)
    hp.add_argument('--output')
    hs = sub.add_parser('hardware-save-preview')
    hs.add_argument('--request', required=True)
    hs.add_argument('--output')
    hr = sub.add_parser('hardware-restore-preview')
    hr.add_argument('--output')
    hb = sub.add_parser('hardware-rebind', help='bind the hardware profile to this PC again after a driver/BIOS update (preview unless --yes)')
    hb.add_argument('--yes', action='store_true')
    for name in ('hardware-apply', 'hardware-save', 'hardware-restore'):
        h = sub.add_parser(name)
        h.add_argument('mission_id')
        h.add_argument('--plan', required=True)
    hd = sub.add_parser('hardware-dashboard')
    hd.add_argument('--port', type=int, default=0)
    hd.add_argument('--open', action='store_true')
    hc = sub.add_parser('hardware-record')
    hc.add_argument('--samples', type=int, default=5)
    hc.add_argument('--interval', type=float, default=2)

    ms = sub.add_parser('model-status')
    ms.add_argument('--check', action='store_true')
    mc = sub.add_parser('model-chat')
    mc.add_argument('mission_id')
    mc.add_argument('--prompt', required=True)
    mc.add_argument('--provider')
    mc.add_argument('--model')
    sub.add_parser('profiles')
    sub.add_parser('model-doctor')
    sub.add_parser('model-scan')
    sub.add_parser('model-catalog')
    mp = sub.add_parser('model-pass')
    mp.add_argument('--profile-id')
    mp.add_argument('--model-size-gb', type=float)
    mp.add_argument('--model-id')
    mp.add_argument('--runtime')
    mb = sub.add_parser('model-benchmark')
    mb.add_argument('--provider', required=True, choices=['llama-cpp-server', 'lm-studio'])
    mb.add_argument('--mission-id')
    mb.add_argument('--model-id')
    mb.add_argument('--model')
    mb.add_argument('--profile-id')
    mb.add_argument('--repeats', type=int, default=3)
    mb.add_argument('--warmups', type=int, default=1)
    mb.add_argument('--max-tokens', type=int, default=128)
    mb.add_argument('--prompt')
    mb.add_argument('--managed-start', action='store_true')
    mb.add_argument('--port', type=int, default=18080)
    mb.add_argument('--keep-running', action='store_true')

    # ---- Factory Commands (F2-02/03/04) ----
    f = sub.add_parser('factory', help='Software Factory: register, build, manage factory types')
    f_sub = f.add_subparsers(dest='factory_cmd', required=True)

    fr = f_sub.add_parser('register', help='Register a new factory type')
    fr.add_argument('typ_id')
    fr.add_argument('name')
    fr.add_argument('--functions', default='')
    fr.add_argument('--manifest-ref')
    fr.add_argument('--gate', action='store_true')

    f_sub.add_parser('list', help='List all factory types')

    # ---- Adapter Commands (F2-04) ----
    fa = f_sub.add_parser('adapter', help='Workflow Adapter: register, parse, validate, execute')
    fa_sub = fa.add_subparsers(dest='adapter_cmd', required=True)

    fa_reg = fa_sub.add_parser('register', help='Register an adapter type')
    fa_reg.add_argument('adapter_id', choices=['native', 'n8n', 'hybrid'])
    fa_reg.add_argument('--name', help='Custom name for the adapter')

    fa_list = fa_sub.add_parser('list', help='List available adapters')

    fa_parse = fa_sub.add_parser('parse', help='Parse workflow file')
    fa_parse.add_argument('file')
    fa_parse.add_argument('--adapter', choices=['native', 'n8n', 'hybrid'], default='native')

    fa_validate = fa_sub.add_parser('validate', help='Validate workflow file')
    fa_validate.add_argument('file')
    fa_validate.add_argument('--adapter', choices=['native', 'n8n', 'hybrid'], default='native')

    fa_dryrun = fa_sub.add_parser('dry-run', help='Dry run workflow')
    fa_dryrun.add_argument('file')
    fa_dryrun.add_argument('--adapter', choices=['native', 'n8n', 'hybrid'], default='native')
    fa_dryrun.add_argument('--params', default='{}')
    fa_dryrun.add_argument('--timeout-ms', type=int, default=300000)

    fa_exec = fa_sub.add_parser('execute', help='Execute workflow')
    fa_exec.add_argument('file')
    fa_exec.add_argument('--adapter', choices=['native', 'n8n', 'hybrid'], default='native')
    fa_exec.add_argument('--params', default='{}')
    fa_exec.add_argument('--timeout-ms', type=int, default=300000)

    fa_export = fa_sub.add_parser('export', help='Export workflow')
    fa_export.add_argument('file')
    fa_export.add_argument('--adapter', choices=['native', 'n8n', 'hybrid'], default='native')
    fa_export.add_argument('--format', choices=['yaml', 'json', 'mermaid', 'n8n.json'], default='yaml')
    fa_export.add_argument('--output', help='Output file (stdout if not specified)')

    fb = f_sub.add_parser('build-project', help='Build a project from factory type')
    fb.add_argument('typ_id')
    fb.add_argument('name')
    fb.add_argument('--gate', action='store_true')

    fm = f_sub.add_parser('build-module', help='Build a module in existing project')
    fm.add_argument('typ_id')
    fm.add_argument('name')
    fm.add_argument('--project', required=True)
    fm.add_argument('--gate', action='store_true')

    fs = f_sub.add_parser('build-service', help='Build a service definition in existing project')
    fs.add_argument('typ_id')
    fs.add_argument('name')
    fs.add_argument('--project', required=True)
    fs.add_argument('--gate', action='store_true')

    fap = f_sub.add_parser('build-adapter-project', help='Build an adapter project (native, n8n, hybrid workflows)')
    fap.add_argument('typ_id')
    fap.add_argument('name')
    fap.add_argument('--gate', action='store_true')

    fsub = f_sub.add_parser('status', help='Show factory type status')
    fsub.add_argument('typ_id')

    ft = f_sub.add_parser('transition', help='Transition factory type lifecycle state')
    ft.add_argument('typ_id')
    ft.add_argument('state', choices=['registered', 'ready', 'active', 'retired'])
    ft.add_argument('--gate', action='store_true')

    # ---- Evidence Store Commands (F2-03) ----
    fe = f_sub.add_parser('evidence', help='Evidence Store: list, show, export runs')
    fe_sub = fe.add_subparsers(dest='evidence_cmd', required=True)

    fe_list = fe_sub.add_parser('list', help='List runs')
    fe_list.add_argument('--typ-id')
    fe_list.add_argument('--limit', type=int, default=50)
    fe_list.add_argument('--success', type=int, choices=[0, 1])

    fe_show = fe_sub.add_parser('show', help='Show run details')
    fe_show.add_argument('run_id')

    fe_export = fe_sub.add_parser('export', help='Export runs to JSONL')
    fe_export.add_argument('output')
    fe_export.add_argument('--typ-id')

    # ---- Benchmark Commands (F2-03) ----
    fbench = f_sub.add_parser('benchmark', help='Benchmark Runner: run, compare, list')
    fbench_sub = fbench.add_subparsers(dest='benchmark_cmd', required=True)

    fbench_run = fbench_sub.add_parser('run', help='Run benchmark for a factory type')
    fbench_run.add_argument('typ_id')
    fbench_run.add_argument('--variant', default='default')
    fbench_run.add_argument('--iterations', type=int, default=3)
    fbench_run.add_argument('--params', default='{}')
    fbench_run.add_argument('--build-type', default='project', choices=['project', 'module', 'service'])
    fbench_run.add_argument('--project-name')
    fbench_run.add_argument('--warmup', type=int, default=0)
    fbench_run.add_argument('--no-cleanup', action='store_true')
    fbench_run.add_argument('--gate', action='store_true')

    fbench_compare = fbench_sub.add_parser('compare', help='Compare variants for a type')
    fbench_compare.add_argument('typ_id')
    fbench_compare.add_argument('--variants', required=True)
    fbench_compare.add_argument('--iterations', type=int, default=3)
    fbench_compare.add_argument('--build-type', default='project', choices=['project', 'module', 'service'])
    fbench_compare.add_argument('--project-name')
    fbench_compare.add_argument('--gate', action='store_true')

    fbench_list = fbench_sub.add_parser('list', help='List benchmarks')
    fbench_list.add_argument('--typ-id')

    # ---- Meta Analyzer Commands (F2-03) ----
    fmeta = f_sub.add_parser('meta', help='Meta Analyzer: analyze, regressions, insights')
    fmeta_sub = fmeta.add_subparsers(dest='meta_cmd', required=True)

    fmeta_analyze = fmeta_sub.add_parser('analyze', help='Run pattern analysis')
    fmeta_analyze.add_argument('--min-runs', type=int, default=10)
    fmeta_analyze.add_argument('--typ-id')

    fmeta_regressions = fmeta_sub.add_parser('regressions', help='Detect regressions for a type')
    fmeta_regressions.add_argument('typ_id')
    fmeta_regressions.add_argument('--window', type=int, default=30)
    fmeta_regressions.add_argument('--threshold', type=float, default=20.0)

    fmeta_insights = fmeta_sub.add_parser('insights', help='List stored insights')
    fmeta_insights.add_argument('--min-confidence', type=float, default=0.5)

    fmeta_report = fmeta_sub.add_parser('report', help='Full analysis report')
    fmeta_report.add_argument('--min-runs', type=int, default=10)

    tp = sub.add_parser('tuning-plan')
    tp.add_argument('--model-id', required=True)
    tp.add_argument('--profile-id')
    tp.add_argument('--axes-json')
    tp.add_argument('--max-candidates', type=int, default=12)
    tr = sub.add_parser('tuning-run')
    tr.add_argument('mission_id')
    tr.add_argument('--plan', required=True)
    sub.add_parser('tuning-list')
    ip = sub.add_parser('dev-image-preview')
    ip.add_argument('--request', required=True)
    ii = sub.add_parser('dev-image-import')
    ii.add_argument('mission_id')
    ii.add_argument('--plan', required=True)
    sub.add_parser('sandbox-doctor')
    sub.add_parser('sandbox-history')
    sp = sub.add_parser('sandbox-preview')
    sp.add_argument('--request', required=True)
    sr = sub.add_parser('sandbox-run')
    sr.add_argument('mission_id')
    sr.add_argument('--plan', required=True)
    sub.add_parser('benchmark-list')
    sub.add_parser('known-good-list')
    kg = sub.add_parser('known-good-promote')
    kg.add_argument('mission_id')
    kg.add_argument('benchmark_id')
    kg.add_argument('--profile-id')
    sub.add_parser('audit-repair', help='move a torn last line of the audit log aside so appends work again')
    ls = sub.add_parser('lessons', help='lesson cards of the coder (E-11): list, propose, approve, reject, sweep; nothing is used before you approve it')
    ls.add_argument('action', choices=['list', 'propose', 'approve', 'reject', 'sweep'])
    ls.add_argument('--text')
    ls.add_argument('--source', default='captain')
    ls.add_argument('--id')
    ls.add_argument('--reason')
    cst = sub.add_parser('code-stand', help='code the Captain has not seen in this version (SPEC_APPS_v1 G4): show it, or take the current state as seen')
    cst.add_argument('projekt')
    cst_art = cst.add_mutually_exclusive_group()
    cst_art.add_argument('--zeigen', action='store_true')
    cst_art.add_argument('--uebernehmen', action='store_true')
    ob = sub.add_parser('objects', help='read desk objects through the running desk (POST /api/objects, Spec 0 D2)')
    ob.add_argument('type')
    ob.add_argument('id', nargs='?')
    ac = sub.add_parser('act', help='run a verb through the running desk (POST /api/actions, gates as in the desk); id - = verb without object')
    ac.add_argument('type')
    ac.add_argument('id')
    ac.add_argument('verb')
    ac.add_argument('--args', default='{}')

    args = p.parse_args(argv)

    if args.cmd in {'objects', 'act'}:
        return desk_command(args)
    if args.cmd == 'code-stand':
        return code_stand_command(args)
    if args.cmd == 'audit-repair':
        from .core.audit import AuditLog
        out = AuditLog(Path(args.root).resolve() / 'runtime_data' / 'audit' / 'events.jsonl').repair()
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'buildflow':
        from .devenv.buildflow_cli import main as buildflow_main
        return buildflow_main(args.rest, Path(args.root).resolve())
    if args.cmd == 'lessons':
        from .devenv.lesson_store import default_path, manage
        try:
            out = manage(default_path(Path(args.root).resolve()), args.action, text=args.text, source=args.source, card_id=args.id, reason=args.reason)
        except (ValueError, KeyError) as exc:
            print(json.dumps({'status': 'refused', 'error': str(exc)}, ensure_ascii=False))
            return 2
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    rt = runtime_from_args(args)
    try:
        return _execute_runtime_command(rt, args)
    finally:
        rt.close()


def _execute_runtime_command(rt, args):
    if args.cmd == 'doctor':
        print(json.dumps(rt.boot(), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'new-mission':
        inputs = mission_inputs(args)
        plan = None
        if args.plan_request:
            with Path(args.plan_request).open('rb') as stream:
                raw = stream.read(1048577)
            if len(raw) > 1048576:
                raise ValueError('plan_request_file_too_large')
            plan = json.loads(raw)
        m = rt.brain.create_mission(args.intent, args.objective, args.mission_class, inputs, plan_request=plan)
        print(m['identity']['mission_id'])
        return 0
    if args.cmd == 'mission-inputs':
        inputs = mission_inputs(args)
        if inputs is None:
            raise ValueError('mission_inputs_required')
        m = rt.brain.set_inputs(args.mission_id, inputs)
        print(json.dumps(m, indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'demo':
        rt.boot()
        m = rt.brain.create_mission(args.intent, mission_class=args.mission_class)
        m = rt.brain.run(m['identity']['mission_id'])
        print(json.dumps(m, indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'resume':
        rt.brain.resume(args.mission_id)
        print(json.dumps(rt.brain.run(args.mission_id, max_steps=args.max_steps), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'execution-check':
        with Path(args.request).open('rb') as stream:
            raw = stream.read(1048577)
        if len(raw) > 1048576:
            raise ValueError('execution_request_too_large')
        req = json.loads(raw)
        if not isinstance(req, dict):
            raise ValueError('execution_request_object_required')
        print(json.dumps(rt.control.check_execution(rt.missions.load(args.mission_id), req), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'recover':
        print(json.dumps(rt.brain.recover(args.mission_id, args.resolution), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'candidate-status':
        m = rt.missions.load(args.mission_id)
        print(json.dumps(m['execution'].get('candidate_attempts', []), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'candidate-cleanup':
        from .selfdev.candidate_lifecycle import discard
        with rt.missions.execution_lock(args.mission_id):
            m = rt.missions.load(args.mission_id)
            out = discard(rt.control, m, args.attempt_id, m['execution'].get('approval_token'))
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0
    if args.cmd in {'candidate-test', 'candidate-test-verify'}:
        from .selfdev.candidate_tests import run_candidate_tests, verify_candidate_tests
        out = (run_candidate_tests if args.cmd == 'candidate-test' else verify_candidate_tests)(rt, args.mission_id)
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0 if out.get('status') == 'completed' else 2
    if args.cmd in {'candidate-accept-preview', 'candidate-accept', 'candidate-rollback-preview', 'candidate-rollback'}:
        from .selfdev.candidate_acceptance import command
        plan = json.loads(Path(args.plan).read_text(encoding='utf-8-sig')) if args.plan else None
        out = command(rt, args.mission_id, args.cmd.removeprefix('candidate-'), plan)
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0 if out.get('status') == 'completed' else 2
    if args.cmd in {'self-integrate-preview', 'self-integrate', 'self-rollback-preview', 'self-rollback'}:
        from .selfdev.self_integration import command as integration_command
        plan = json.loads(Path(args.plan).read_text(encoding='utf-8-sig')) if args.plan else None
        out = integration_command(rt, args.mission_id, args.cmd.removeprefix('self-'), plan)
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0 if out.get('status') == 'completed' else 2
    if args.cmd == 'run':
        print(json.dumps(rt.brain.run(args.mission_id, max_steps=args.max_steps), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'list-missions':
        print(json.dumps(rt.missions.list(), indent=2, ensure_ascii=False))
        return 0
    if args.cmd in {'model-remove-preview', 'model-remove', 'model-restore'}:
        from .models.model_removal import command as removal_command
        if args.cmd == 'model-remove-preview':
            out = removal_command(rt, None, 'preview', targets=args.targets)
        elif args.cmd == 'model-restore':
            out = removal_command(rt, None, 'restore', removal_id=args.removal_id)
        else:
            out = removal_command(rt, args.mission_id, 'remove', plan=json.loads(Path(args.plan).read_text(encoding='utf-8-sig')))
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0 if out.get('status') in {'completed', 'restored'} else 2
    if args.cmd == 'routing-profile':
        prof = getattr(rt, 'routing_profiles', None)
        if prof is None:
            print(json.dumps({'status': 'unavailable', 'error': getattr(rt, 'routing_profiles_error', None) or 'role_routing_disabled'}, indent=2))
            return 2
        if args.action == 'use':
            if not args.name:
                raise SystemExit('routing-profile use <name>')
            out = prof.use(args.name)
            rt.audit.append('ROUTING_PROFILE_CHANGED', component='role-routing', payload={'active': args.name})
        else:
            out = prof.view()
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'list-tools':
        print(json.dumps(rt.tools.list(), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'list-skills':
        print(json.dumps({k: v.get('data', {}) for k, v in rt.registry.skills.items()}, indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'list-topics':
        print(json.dumps(rt.capability_router.topic_catalog(), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'topic-propose':
        print(json.dumps(rt.topic_store.propose(args.title, args.description), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'route':
        print(json.dumps(rt.capability_router.route(args.intent, args.objective, args.mission_class, args.topic), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'mission-route':
        m = rt.missions.load(args.mission_id)
        route = (m.get('routing') or {}).get('route') or rt.capability_router.route_mission(m)
        print(json.dumps(route, indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'hardware':
        print(json.dumps(rt.hardware.to_dict(), indent=2, ensure_ascii=False))
        return 0
    if args.cmd.startswith('hardware-'):
        hw = rt.hardware_manager
        if args.cmd == 'hardware-dashboard':
            from .hardware_manager.dashboard import serve
            if not 0 <= args.port <= 65535:
                raise SystemExit('Invalid dashboard port')
            serve(hw, args.port, args.open)
            return 0
        reads = {'hardware-state': hw.get_state, 'hardware-inventory': hw.inventory,
                 'hardware-capabilities': hw.capabilities, 'hardware-profiles': hw.profiles}
        if args.cmd in reads:
            out = reads[args.cmd]()
        elif args.cmd == 'hardware-record':
            out = hw.record_run(args.samples, args.interval)
        elif args.cmd == 'hardware-rebind':
            out = hw.rebind_preview()
            if args.yes and out['needed']:
                out = {'preview': out, 'result': hw.rebind(out)}
        elif args.cmd in {'hardware-preview', 'hardware-save-preview', 'hardware-restore-preview'}:
            if args.cmd == 'hardware-preview':
                out = hw.preview_profile(args.profile_id)
            elif args.cmd == 'hardware-restore-preview':
                out = hw.restore_preview()
            else:
                request = json.loads(Path(args.request).read_text(encoding='utf-8-sig'))
                out = hw.save_preview(request['profile_id'], request['profile'])
            if args.output:
                from .core.util import atomic_write_json
                atomic_write_json(Path(args.output).resolve(), out)
        else:
            op = {'hardware-apply': 'apply_profile', 'hardware-save': 'save_profile', 'hardware-restore': 'restore_defaults'}[args.cmd]
            m = rt.missions.load(args.mission_id)
            token = m.get('execution', {}).get('approval_token')
            plan = json.loads(Path(args.plan).read_text(encoding='utf-8-sig'))
            out = rt.tools.execute('hardware-manager', args.mission_id, op, {'plan': plan}, token)
            if out.get('status') == 'captain_required' and out.get('gate'):
                m['human_gates']['pending'].append(out['gate'])
            elif token and token.get('status') == 'used':
                m.get('execution', {}).pop('approval_token', None)
            rt.missions.save(m)
            print(json.dumps(out, indent=2, ensure_ascii=False))
            return 0 if out.get('status') == 'completed' else 2
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    if args.cmd == 'model-status':
        print(json.dumps(rt.model_router.status(check_health=args.check), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'profiles':
        print(json.dumps({'recommended': rt.recommended_model_profile, 'all': rt.model_profiles.all()}, indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'model-doctor':
        print(json.dumps({'hardware': rt.hardware.to_dict(), 'recommended_profile': rt.model_runtime.profile_for(), 'runtime': rt.model_runtime.status()}, indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'model-scan':
        print(json.dumps(rt.model_runtime.scan_portable(), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'model-catalog':
        print(json.dumps(rt.model_runtime.model_list(), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'model-pass':
        print(json.dumps(rt.model_runtime.profile_for(args.profile_id, args.model_size_gb, model_id=args.model_id, runtime=args.runtime), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'tuning-plan':
        kw = {'model_id': args.model_id, 'profile_id': args.profile_id, 'max_candidates': args.max_candidates}
        if args.axes_json is not None:
            kw['axes'] = json.loads(args.axes_json)
        print(json.dumps(rt.model_runtime.tuning.plan(**kw), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'tuning-list':
        print(json.dumps(rt.model_runtime.tuning.history(), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'tuning-run':
        m = rt.missions.load(args.mission_id)
        token = m.get('execution', {}).get('approval_token')
        plan = json.loads(Path(args.plan).read_text(encoding='utf-8-sig'))
        out = rt.tools.execute('model-runtime', args.mission_id, 'tuning_run', {'plan': plan}, token)
        if out.get('status') == 'captain_required' and out.get('gate'):
            m['human_gates']['pending'].append(out['gate'])
            rt.missions.save(m)
        elif token and token.get('status') == 'used':
            m.get('execution', {}).pop('approval_token', None)
            rt.missions.save(m)
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'dev-image-preview':
        req = json.loads(Path(args.request).read_text(encoding='utf-8-sig'))
        out = rt.sandbox.execute('IMAGE-PREVIEW', 'image_preview', req)
        print(json.dumps(out['plan'], indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'dev-image-import':
        with rt.missions.execution_lock(args.mission_id):
            m = rt.missions.load(args.mission_id)
            token = m['execution'].get('approval_token')
            plan = json.loads(Path(args.plan).read_text(encoding='utf-8-sig'))
            out = rt.tools.execute('sandbox', args.mission_id, 'image_import', {'plan': plan}, token)
            if out.get('status') == 'captain_required':
                m['human_gates']['pending'].append(out['gate'])
            elif token and token.get('status') == 'used':
                m['execution'].pop('approval_token', None)
            rt.missions.save(m)
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0 if out.get('status') == 'completed' else 2
    if args.cmd == 'sandbox-doctor':
        print(json.dumps(rt.sandbox.doctor(), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'sandbox-history':
        print(json.dumps(rt.sandbox.history(), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'sandbox-preview':
        req = json.loads(Path(args.request).read_text(encoding='utf-8-sig'))
        print(json.dumps(rt.sandbox.preview(**req), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'sandbox-run':
        m = rt.missions.load(args.mission_id)
        token = m.get('execution', {}).get('approval_token')
        plan = json.loads(Path(args.plan).read_text(encoding='utf-8-sig'))
        out = rt.tools.execute('sandbox', args.mission_id, 'run', {'plan': plan}, token)
        if out.get('status') == 'captain_required' and out.get('gate'):
            m['human_gates']['pending'].append(out['gate'])
        elif token and token.get('status') == 'used':
            m.get('execution', {}).pop('approval_token', None)
        rt.missions.save(m)
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0 if out.get('status') == 'completed' else 2
    if args.cmd == 'benchmark-list':
        print(json.dumps(rt.model_runtime.benchmark.store.list(), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'known-good-list':
        print(json.dumps(rt.model_profiles.known_good_records(), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'model-benchmark':
        payload = {'provider': args.provider, 'model_id': args.model_id, 'model': args.model, 'profile_id': args.profile_id, 'repeats': args.repeats, 'warmups': args.warmups, 'max_tokens': args.max_tokens, 'managed_start': args.managed_start, 'port': args.port, 'keep_running': args.keep_running}
        if args.prompt is not None:
            payload['prompt'] = args.prompt
        if args.managed_start:
            if not args.mission_id:
                raise SystemExit('--mission-id is required with --managed-start')
            m = rt.missions.load(args.mission_id)
            token = m.get('execution', {}).get('approval_token')
            out = rt.tools.execute('model-runtime', args.mission_id, 'benchmark', payload, token)
            if out.get('status') == 'captain_required' and out.get('gate'):
                m['human_gates']['pending'].append(out['gate'])
                rt.missions.save(m)
            elif token and token.get('status') == 'used':
                m.get('execution', {}).pop('approval_token', None)
                rt.missions.save(m)
        else:
            out = rt.tools.execute('model-runtime', args.mission_id or 'M-BENCHMARK', 'benchmark', payload)
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'known-good-promote':
        m = rt.missions.load(args.mission_id)
        token = m.get('execution', {}).get('approval_token')
        out = rt.tools.execute('model-runtime', args.mission_id, 'promote_known_good', {'benchmark_id': args.benchmark_id, 'profile_id': args.profile_id}, token)
        if out.get('status') == 'captain_required' and out.get('gate'):
            m['human_gates']['pending'].append(out['gate'])
            rt.missions.save(m)
        elif token and token.get('status') == 'used':
            m.get('execution', {}).pop('approval_token', None)
            rt.missions.save(m)
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'model-chat':
        out = rt.model_router.chat(args.mission_id, [{'role': 'user', 'content': args.prompt}], provider=args.provider, model=args.model)
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'tool-call':
        payload = json.loads(args.args_json)
        m = rt.missions.load(args.mission_id)
        token = m.get('execution', {}).get('approval_token')
        out = rt.tools.execute(args.tool, args.mission_id, args.operation, payload, token)
        if out.get('status') == 'captain_required' and out.get('gate'):
            m['human_gates']['pending'].append(out['gate'])
            rt.missions.save(m)
        elif token and token.get('status') == 'used':
            m.get('execution', {}).pop('approval_token', None)
            rt.missions.save(m)
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0
    if args.cmd == 'approve':
        with rt.missions.execution_lock(args.mission_id):
            m = rt.missions.load(args.mission_id)
            if not m['human_gates']['pending']:
                raise SystemExit('No pending human gate')
            index = next((i for i, g in enumerate(m['human_gates']['pending']) if g['gate_id'] == args.gate_id), None) if args.gate_id else 0
            if index is None:
                raise SystemExit('Gate ID not pending')
            gate = m['human_gates']['pending'][index]
            token = rt.guard.approve(gate)
            m['human_gates']['pending'].pop(index)
            m['human_gates']['resolved'].append(gate)
            m['execution']['approval_token'] = token
            rt.missions.save(m)
        print(json.dumps(token, indent=2))
        return 0

    # ---- Factory Commands Execution (F2-02/03/04) ----
    if args.cmd == 'factory':
        from .factory_registry import FactoryRegistry, FactoryRegistryError
        from .factory_builder import FactoryBuilder
        from .evidence_store import EvidenceStore, get_default_store
        from .benchmark_runner import BenchmarkRunner, BenchmarkConfig
        from .meta_analyzer import MetaAnalyzer, run_full_analysis
        from .adapters.adapter_base import AdapterRegistry, AdapterType
        from .adapters.native.native_adapter import NativeWorkflowAdapter
        from .adapters.n8n.n8n_adapter import N8nWorkflowAdapter
        from .adapters.hybrid.hybrid_adapter import HybridWorkflowAdapter
        from .adapters.adapter_base import ExecutionContext

        registry_path = Path(args.root).resolve() / 'local_config' / 'factory_registry.json'
        registry = FactoryRegistry.load(registry_path)
        builder = FactoryBuilder(registry, Path(args.root).resolve())
        store = get_default_store()
        runner = BenchmarkRunner(store, builder, registry, Path(args.root).resolve())
        analyzer = MetaAnalyzer(store)

        adapter_registry = AdapterRegistry()
        adapter_registry.register(NativeWorkflowAdapter())
        adapter_registry.register(N8nWorkflowAdapter())
        adapter_registry.register(HybridWorkflowAdapter())

        if args.factory_cmd == 'register':
            functions = args.functions.split(',') if args.functions else []
            try:
                ft = registry.registriere_typ(args.typ_id, args.name, functions, args.manifest_ref, gate_freigabe=args.gate)
                registry.save(registry_path)
                print(json.dumps({'typ_id': ft.typ_id, 'name': ft.name, 'zustand': ft.zustand, 'funktionen': sorted(ft.functionen)}, indent=2, ensure_ascii=False))
                return 0
            except FactoryRegistryError as exc:
                print(json.dumps({'status': 'refused', 'error': str(exc)}, ensure_ascii=False))
                return 2
        elif args.factory_cmd == 'list':
            print(json.dumps(registry.liste_typen(), indent=2, ensure_ascii=False))
            return 0
        elif args.factory_cmd == 'build-project':
            result = builder.build_project(args.typ_id, args.name, gate_freigabe=args.gate)
            print(json.dumps({'success': result.success, 'path': str(result.path) if result.path else None, 'message': result.message, 'artifacts': [str(a) for a in result.artifacts]}, indent=2, ensure_ascii=False))
            return 0 if result.success else 2
        elif args.factory_cmd == 'build-module':
            project = Path(args.project).resolve()
            result = builder.build_module(args.typ_id, args.name, project, gate_freigabe=args.gate)
            print(json.dumps({'success': result.success, 'path': str(result.path) if result.path else None, 'message': result.message, 'artifacts': [str(a) for a in result.artifacts]}, indent=2, ensure_ascii=False))
            return 0 if result.success else 2
        elif args.factory_cmd == 'build-service':
            project = Path(args.project).resolve()
            result = builder.build_service(args.typ_id, args.name, project, gate_freigabe=args.gate)
            print(json.dumps({'success': result.success, 'path': str(result.path) if result.path else None, 'message': result.message, 'artifacts': [str(a) for a in result.artifacts]}, indent=2, ensure_ascii=False))
            return 0 if result.success else 2
        elif args.factory_cmd == 'build-adapter-project':
            result = builder.build_adapter_project(args.typ_id, args.name, gate_freigabe=args.gate)
            print(json.dumps({'success': result.success, 'path': str(result.path) if result.path else None, 'message': result.message, 'artifacts': [str(a) for a in result.artifacts]}, indent=2, ensure_ascii=False))
            return 0 if result.success else 2
        elif args.factory_cmd == 'status':
            ft = registry.get(args.typ_id)
            if ft is None:
                print(json.dumps({'status': 'not_found', 'typ_id': args.typ_id}, indent=2, ensure_ascii=False))
                return 2
            print(json.dumps({'typ_id': ft.typ_id, 'name': ft.name, 'zustand': ft.zustand, 'funktionen': sorted(ft.functionen), 'manifest_ref': ft.manifest_ref, 'gate_freigabe': args.typ_id in registry._gate_erlaubt}, indent=2, ensure_ascii=False))
            return 0
        elif args.factory_cmd == 'transition':
            try:
                ft = registry.wechsel_zustand(args.typ_id, args.state, gate_freigabe=args.gate)
                registry.save(registry_path)
                print(json.dumps({'typ_id': ft.typ_id, 'name': ft.name, 'zustand': ft.zustand}, indent=2, ensure_ascii=False))
                return 0
            except FactoryRegistryError as exc:
                print(json.dumps({'status': 'refused', 'error': str(exc)}, ensure_ascii=False))
                return 2
        elif args.factory_cmd == 'evidence':
            if args.evidence_cmd == 'list':
                runs = store.list_runs(typ_id=args.typ_id, limit=args.limit)
                print(json.dumps([{'run_id': r.run_id, 'typ_id': r.typ_id, 'name': r.name, 'build_type': r.build_type, 'started_at': r.started_at.isoformat(), 'finished_at': r.finished_at.isoformat() if r.finished_at else None, 'duration_ms': r.duration_ms, 'success': r.success, 'artifacts_count': r.artifacts_count, 'error_message': r.error_message} for r in runs], indent=2, ensure_ascii=False))
                return 0
            elif args.evidence_cmd == 'show':
                run = store.get_run(args.run_id)
                if run is None:
                    print(json.dumps({'status': 'not_found', 'run_id': args.run_id}, indent=2, ensure_ascii=False))
                    return 2
                print(json.dumps({'run_id': run.run_id, 'typ_id': run.typ_id, 'name': run.name, 'build_type': run.build_type, 'started_at': run.started_at.isoformat(), 'finished_at': run.finished_at.isoformat() if run.finished_at else None, 'duration_ms': run.duration_ms, 'success': run.success, 'artifacts_count': run.artifacts_count, 'error_message': run.error_message, 'metrics': run.metrics}, indent=2, ensure_ascii=False))
                return 0
            elif args.evidence_cmd == 'export':
                count = store.export_runs_jsonl(Path(args.output), typ_id=args.typ_id)
                print(json.dumps({'exported': count, 'output': args.output}, indent=2, ensure_ascii=False))
                return 0
        elif args.factory_cmd == 'benchmark':
            if args.benchmark_cmd == 'run':
                config = BenchmarkConfig(
                    typ_id=args.typ_id,
                    variant=args.variant,
                    params=json.loads(args.params),
                    iterations=args.iterations,
                    build_type=args.build_type,
                    project_name=args.project_name,
                    warmup=args.warmup,
                    cleanup_between=not args.no_cleanup,
                )
                result = runner.run_benchmark(config)
                print(json.dumps({'benchmark_id': result.benchmark_id, 'typ_id': result.typ_id, 'variant': result.variant, 'score': result.score, 'runs': len(result.runs), 'aggregated_metrics': result.aggregated_metrics}, indent=2, ensure_ascii=False))
                return 0
            elif args.benchmark_cmd == 'compare':
                variant_names = args.variants.split(',')
                variants = []
                for v in variant_names:
                    variants.append(BenchmarkConfig(
                        typ_id=args.typ_id,
                        variant=v,
                        iterations=args.iterations,
                        build_type=args.build_type,
                        project_name=args.project_name,
                    ))
                results = runner.compare_variants(args.typ_id, variants)
                print(json.dumps([{'variant': r.variant, 'score': r.score, 'runs': len(r.runs), 'aggregated_metrics': r.aggregated_metrics} for r in results], indent=2, ensure_ascii=False))
                return 0
            elif args.benchmark_cmd == 'list':
                benches = store.get_benchmarks(typ_id=args.typ_id)
                print(json.dumps([{'benchmark_id': b.benchmark_id, 'typ_id': b.typ_id, 'variant': b.variant, 'score': b.score, 'runs_count': b.runs_count, 'aggregated_metrics': b.aggregated_metrics} for b in benches], indent=2, ensure_ascii=False))
                return 0
        elif args.factory_cmd == 'meta':
            if args.meta_cmd == 'analyze':
                insights = analyzer.analyze(min_runs=args.min_runs, typ_id=args.typ_id)
                print(json.dumps([{'pattern': i.pattern, 'confidence': i.confidence, 'recommendation': i.recommendation, 'supporting_runs': len(i.supporting_run_ids)} for i in insights], indent=2, ensure_ascii=False))
                return 0
            elif args.meta_cmd == 'regressions':
                regs = analyzer.detect_regressions(args.typ_id, window=args.window, threshold_pct=args.threshold / 100.0)
                print(json.dumps([{'typ_id': r.typ_id, 'metric': r.metric, 'current_value': r.current_value, 'baseline_value': r.baseline_value, 'change_pct': r.change_pct, 'severity': r.severity, 'window_runs': r.window_runs} for r in regs], indent=2, ensure_ascii=False))
                return 0
            elif args.meta_cmd == 'insights':
                insights = analyzer.get_insights(min_confidence=args.min_confidence)
                print(json.dumps([{'insight_id': i.insight_id, 'pattern': i.pattern, 'confidence': i.confidence, 'supporting_run_ids': i.supporting_run_ids, 'recommendation': i.recommendation} for i in insights], indent=2, ensure_ascii=False))
                return 0
            elif args.meta_cmd == 'report':
                report = run_full_analysis(store, min_runs=args.min_runs)
                print(json.dumps(report, indent=2, ensure_ascii=False))
                return 0
        elif args.factory_cmd == 'adapter':
            if args.adapter_cmd == 'register':
                adapter = adapter_registry.get(AdapterType(args.adapter_id))
                if adapter:
                    print(json.dumps({'adapter_id': args.adapter_id, 'name': args.name or adapter.name, 'status': 'registered', 'formats': adapter.supported_formats}, indent=2, ensure_ascii=False))
                    return 0
                else:
                    print(json.dumps({'status': 'refused', 'error': f'Unknown adapter: {args.adapter_id}'}, ensure_ascii=False))
                    return 2
            elif args.adapter_cmd == 'list':
                adapters = []
                for atype in AdapterType:
                    adapter = adapter_registry.get(atype)
                    if adapter:
                        adapters.append({'adapter_id': atype.value, 'name': adapter.name, 'formats': adapter.supported_formats})
                print(json.dumps(adapters, indent=2, ensure_ascii=False))
                return 0
            elif args.adapter_cmd in {'parse', 'validate', 'dry-run', 'execute', 'export'}:
                # Load workflow file
                file_path = Path(args.file).resolve()
                if not file_path.exists():
                    print(json.dumps({'status': 'refused', 'error': f'File not found: {args.file}'}, ensure_ascii=False))
                    return 2
                content = file_path.read_text(encoding='utf-8')

                adapter_type = AdapterType(args.adapter)
                adapter = adapter_registry.get(adapter_type)
                if not adapter:
                    print(json.dumps({'status': 'refused', 'error': f'Adapter not available: {args.adapter}'}, ensure_ascii=False))
                    return 2

                try:
                    spec = adapter.parse(content)
                except Exception as exc:
                    print(json.dumps({'status': 'refused', 'error': f'Parse failed: {exc}'}, ensure_ascii=False))
                    return 2

                if args.adapter_cmd == 'parse':
                    print(json.dumps({'workflow_id': spec.id, 'name': spec.name, 'version': spec.version, 'steps': len(spec.steps), 'adapter_type': spec.adapter_type.value}, indent=2, ensure_ascii=False))
                    return 0

                if args.adapter_cmd == 'validate':
                    result = adapter.validate(spec)
                    print(json.dumps({'valid': result.valid, 'errors': [i.code for i in result.errors], 'warnings': [i.code for i in result.warnings], 'infos': [i.code for i in result.infos]}, indent=2, ensure_ascii=False))
                    return 0 if result.valid else 2

                if args.adapter_cmd == 'export':
                    try:
                        exported = adapter.export(spec, args.format)
                        if args.output:
                            Path(args.output).write_text(exported, encoding='utf-8')
                            print(json.dumps({'success': True, 'output': args.output, 'format': args.format}, indent=2, ensure_ascii=False))
                        else:
                            print(exported)
                        return 0
                    except Exception as exc:
                        print(json.dumps({'status': 'refused', 'error': f'Export failed: {exc}'}, ensure_ascii=False))
                        return 2

                context = ExecutionContext(
                                    workflow_id=spec.id,
                                    adapter_type=adapter_type,
                                    parameters=json.loads(args.params) if args.params else {},
                                    timeout_ms=args.timeout_ms,
                                )

                if args.adapter_cmd == 'dry-run':
                    result = adapter.dry_run(spec, context)
                    print(json.dumps({'success': result.success, 'estimated_duration_ms': result.estimated_duration_ms, 'simulated_steps': len(result.simulated_steps), 'warnings': result.warnings, 'errors': result.errors}, indent=2, ensure_ascii=False))
                    return 0 if result.success else 2

                if args.adapter_cmd == 'execute':
                                    import asyncio
                                    from .evidence_store import get_default_store
                    
                                    store = get_default_store()
                                    run_record = store.record_run_start(
                                        typ_id=f"adapter-{adapter_type.value}",
                                        name=f"{spec.name} ({adapter_type.value})",
                                        build_type="adapter_execute",
                                    )
                                    run_id = run_record.run_id
                    
                                    result = asyncio.run(adapter.execute(spec, context))
                    
                                    # Record in evidence store
                                    store.record_run_end(
                                        run_id=run_id,
                                        success=result.success,
                                        artifacts=[],
                                        error=result.error,
                                        metrics={
                                            "steps_executed": result.steps_executed,
                                            "steps_total": result.steps_total,
                                            "duration_ms": result.duration_ms,
                                        } if result.duration_ms else {},
                                    )
                    
                                    print(json.dumps({'workflow_id': result.workflow_id, 'status': result.status.value, 'success': result.success, 'steps_executed': result.steps_executed, 'steps_total': result.steps_total, 'duration_ms': result.duration_ms, 'error': result.error}, indent=2, ensure_ascii=False))
                                    return 0 if result.success else 2

    return 1


if __name__ == '__main__':
    raise SystemExit(main())
