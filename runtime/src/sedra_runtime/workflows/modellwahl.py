"""Explicit workflow model choice, sealed by the saved workflow digest and execution gate."""
import re


def selection(workflow):
    value = (workflow.get('meta') or {}).get('sedra_model') or {'provider': 'llama-cpp-server', 'model': None}
    if not isinstance(value, dict) or set(value) - {'provider', 'model'}:
        raise ValueError('workflow_model_selection_invalid')
    provider, model = value.get('provider'), value.get('model')
    if provider not in ('llama-cpp-server', 'nvidia'):
        raise ValueError('workflow_model_provider_not_supported')
    if model is not None and (not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,199}', model)):
        raise ValueError('workflow_model_id_invalid')
    if provider == 'nvidia' and not model:
        raise ValueError('workflow_nvidia_model_required')
    return {'provider': provider, 'model': model}


def options(hub, _oid, args):
    if args.get('nvidia_catalog'):
        data = hub.cloud_models({'provider': 'nvidia'})
        return {'items': [{'provider': 'nvidia', 'model': m, 'label': 'NVIDIA · ' + m} for m in data.get('models', [])]}
    items = [{'provider': 'llama-cpp-server', 'model': None, 'label': 'Lokal · aktuell geladenes Modell'}]
    harness=getattr(hub,'harness',None)
    if harness is not None:
        loaded,_=harness.geladen()
        for m in loaded:
            model=m.get('identifier') or m.get('modelKey')
            if isinstance(model,str):items.append({'provider':'llama-cpp-server','model':model,'label':'Lokal · '+model})
    adapter = getattr(hub.runtime.model_router, 'adapters', {}).get('nvidia')
    if adapter and getattr(adapter, 'default_model', None):
        items.append({'provider': 'nvidia', 'model': adapter.default_model, 'label': 'NVIDIA · ' + adapter.default_model})
    return {'items': items, 'nvidia_configured': bool(adapter)}
