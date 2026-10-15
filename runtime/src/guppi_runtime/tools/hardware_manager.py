from .base import BaseTool, ToolValidationError


class HardwareManagerTool(BaseTool):
    id = 'hardware-manager'
    version = '0.1.0'
    supported_operations = {'get_inventory', 'get_capabilities', 'get_state', 'get_history',
                            'profiles', 'preview_profile', 'apply_profile', 'preview_save',
                            'save_profile', 'preview_restore', 'restore_defaults', 'record_run'}

    def __init__(self, root, manager, guard=None, audit=None):
        super().__init__(root, guard, audit)
        self.manager = manager

    def execute(self, mission_id, operation, args=None, approval_token=None):
        args = args or {}
        m = self.manager
        readers = {'get_inventory': lambda: {'inventory': m.inventory()},
                   'get_capabilities': lambda: {'capabilities': m.capabilities()},
                   'get_state': lambda: {'hardware_state': m.get_state()},
                   'get_history': lambda: {'samples': m.history(args.get('limit', 120))},
                   'profiles': lambda: {'profiles': m.profiles()},
                   'preview_profile': lambda: {'plan': m.preview_profile(args.get('profile_id'))},
                   'preview_save': lambda: {'plan': m.save_preview(args.get('profile_id'), args.get('profile'))},
                   'preview_restore': lambda: {'plan': m.restore_preview()}}
        if operation in readers: return {'status': 'completed', **readers[operation]()}
        if operation == 'record_run':
            # Recording only; bounded count/duration, no hardware changes.
            return {'status': 'completed', **m.record_run(args.get('samples', 5), args.get('interval', 2))}
        if operation not in {'apply_profile', 'save_profile', 'restore_defaults'}:
            raise ToolValidationError('unsupported_hardware_operation')
        plan = args.get('plan')
        if not isinstance(plan, dict): raise ToolValidationError('hardware_plan_required')
        if operation == 'apply_profile': rebuilt = m.preview_profile(plan.get('profile_id'))
        elif operation == 'save_profile': rebuilt = m.save_preview(plan.get('profile_id'), plan.get('profile'))
        else: rebuilt = m.restore_preview()
        if plan != rebuilt: raise ToolValidationError('hardware_plan_changed_repreview')
        if plan.get('blockers'): return {'status': 'blocked', 'blockers': plan['blockers']}
        if self.guard is None: return {'status': 'blocked', 'error': 'hardware_guard_required'}
        target = operation + ':' + plan['plan_digest']
        verdict = self.guard.evaluate('hardware_profile_control', mission_id=mission_id, target=target)
        if verdict['decision'] == 'BLOCK': return {'status': 'blocked', 'guard': verdict}
        if verdict['decision'] == 'CAPTAIN_REQUIRED':
            auth = self.guard.authorize(approval_token, mission_id=mission_id,
                                        action='hardware_profile_control', target=target)
            if not auth['authorized']:
                gate = self.guard.create_gate(mission_id, 'hardware_profile_control', target,
                    risks=['Changes GUPPI admission/runtime policy; optional Windows power plan',
                           'Manufacturer fan profiles are references only; no fan writes'], rollback_available=True)
                return {'status': 'captain_required', 'guard': verdict, 'gate': gate}
        try:
            if operation == 'apply_profile': result = m.apply_profile(plan)
            elif operation == 'save_profile': result = m.save_profile(plan)
            else: result = m.restore(plan)
            self._audit('EXECUTION_COMPLETED', mission_id, {'operation': operation, 'digest': plan['plan_digest']})
            return {'status': 'completed', 'result': result}
        except Exception as exc:
            self._audit('EXECUTION_FAILED', mission_id, {'operation': operation, 'error': str(exc)})
            return {'status': 'failed', 'error': str(exc)}
