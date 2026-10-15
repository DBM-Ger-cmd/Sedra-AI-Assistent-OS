from .base import BaseModule


class PlanningContextModule(BaseModule):
    id = 'planning-context'

    def __init__(self, knowledge=None):
        self.knowledge = knowledge
        self.binder = None

    def build_plan(self, mission):
        if 'manual_plan' in mission:
            from ..manual_plan import artifact_plan
            return artifact_plan(mission['manual_plan'])
        objective = mission['objective']['current']
        refs = []
        if self.knowledge:
            hits = self.knowledge.search(objective[:40]) if objective else []
            refs = [h['id'] for h in hits[:5]]

        route = (mission.get('routing') or {}).get('route') or {}
        selected_skills = [x.get('id') for x in route.get('skills', []) if x.get('id')]
        selected_tools = [x.get('id') for x in route.get('tools', []) if x.get('id')]
        selected_modules = [x.get('id') for x in route.get('modules', []) if x.get('id')]

        # Unbound routes retain the legacy planning-artifact path. The closed
        # binder below replaces it for supported, validated inspection missions.
        steps = [{
            'id': 'STEP-1',
            'action': 'create_text_artifact',
            'description': objective,
            'routing': {
                'primary_intent': route.get('primary_intent'),
                'skills': selected_skills,
                'tools': selected_tools,
            },
        }]

        plan = {
            'version': 2,
            'status': 'ready',
            'steps': steps,
            'dependencies': [],
            'acceptance_criteria': [{'type': 'artifact_exists', 'min_count': 1}],
            'context_refs': refs,
            'selected_skills': selected_skills,
            'selected_tools': selected_tools,
            'selected_modules': selected_modules,
            'selected_topics': [x['id'] for x in route.get('topics', [])],
            'proposed_topics': route.get('proposed_topics', []),
            'capability_gaps': route.get('unresolved', []),
            'execution_requirements':route.get('execution_requirements',{}),
            'execution_status': route.get('execution_status', 'blueprint_only'),
            'model_policy': route.get('model_policy', {}),
            'risk': route.get('risk', {}),
            'execution_blueprint': route.get('execution_blueprint', []),
            'routing_status': route.get('status', 'not_resolved'),
        }
        if self.binder:
            binding=self.binder.bind(mission)
            if binding:
                plan.update(binding)
                plan['version']=3
        return plan

    def handle(self, message):
        return {'plan': self.build_plan(message.payload['mission'])}
