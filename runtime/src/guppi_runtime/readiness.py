"""Collect prerequisites without executing models, guest code or hardware writes."""
from pathlib import Path
from . import __version__
from .util import utcnow

PENDING_ACCEPTANCE = [
    'Windows startup, shutdown, standby and USB relocation',
    'Windows telemetry and target sensor comparison',
    'Hardware profile approval, rollback and interrupted-operation recovery',
    'Model startup, inference and representative load benchmark',
    'MicroVM host filesystem and network isolation',
    'MicroVM resource limits, timeout, cancellation and confirmed cleanup',
    'Candidate export validation and Captain review',
]


def build_report(runtime):
    """A prerequisite PASS never promotes a release or qualifies a device."""
    report = {
        'schema_version': 1, 'created_at': utcnow(), 'runtime_version': __version__,
        'scope': 'prerequisites_only; no_model_or_guest_execution; no_hardware_writes',
        'checks': {}, 'blockers': [], 'warnings': [],
        'pending_acceptance': list(PENDING_ACCEPTANCE),
        'release_ready': False, 'unsafe_fallback': False,
        'microvm_boundary_test': 'PENDING_REAL_PC_ACCEPTANCE',
        'hardware_manager': {'hardware_write_acceptance': 'PENDING_REAL_PC_ACCEPTANCE',
                             'fan_write_ready': False, 'gcc_profile_automation_ready': False},
    }

    def check(name, probe, evaluate):
        try:
            value = probe()
            reasons = evaluate(value)
            report['checks'][name] = {'status': 'BLOCKED' if reasons else 'PASS'}
            report['blockers'].extend(f'{name}:{reason}' for reason in reasons)
            return value
        except Exception as exc:
            report['checks'][name] = {'status': 'ERROR', 'error': str(exc),
                                     'error_type': type(exc).__name__}
            report['blockers'].append(f'{name}:probe_failed')
            return None

    boot = check('core', runtime.boot,
                 lambda value: [] if value['state'] == 'READY' else ['core_not_ready'])
    report['core_state'] = boot['state'] if boot is not None else 'UNKNOWN'
    report['sandbox'] = check('sandbox', runtime.sandbox.doctor,
                              lambda value: list(value['blockers']))
    hardware = report['hardware_manager']
    hardware['state'] = check('hardware_state', lambda: runtime.hardware_manager.get_state(fresh=True),
                              lambda value: ['profile_error'] if value.get('profile_error') else [])
    hardware['capabilities'] = check('hardware_capabilities', runtime.hardware_manager.capabilities,
                                    lambda value: [] if isinstance(value, dict) else ['invalid_response'])
    # Use the manager's actual rules for thermal state, profile recovery and RAM.
    check('hardware_admission', runtime.hardware_manager.preflight, lambda value: [])
    if hardware['state'] and hardware['state'].get('thermal_state') == 'UNQUALIFIED':
        report['warnings'].append('thermal_limits_unqualified; no_temperature_safety_claim')
    for name, path in (
        ('hardware_operation', Path(runtime.hardware_manager.root) / 'mutation.lock'),
        ('sandbox_operation', Path(runtime.sandbox.data_root) / 'active.lock'),
    ):
        check(name, path.exists, lambda present: ['active_or_interrupted_operation'] if present else [])
    report['status'] = 'PRECHECK_BLOCKED' if report['blockers'] else 'PRECHECK_PASS_PC_TEST_PENDING'
    return report


def initialization_failure(exc):
    """Still write a reviewable report if runtime construction fails."""
    return {'schema_version': 1, 'created_at': utcnow(), 'runtime_version': __version__,
            'status': 'PRECHECK_BLOCKED', 'core_state': 'UNKNOWN',
            'checks': {'initialization': {'status': 'ERROR', 'error_type': type(exc).__name__,
                                           'error': str(exc)}},
            'blockers': ['initialization:probe_failed'], 'warnings': [],
            'pending_acceptance': list(PENDING_ACCEPTANCE),
            'release_ready': False, 'unsafe_fallback': False}
