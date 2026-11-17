"""Per-chat provider selection; cloud chats do not require a loaded local GPU model."""
from ..workflows.modellwahl import selection


def validate(payload):
    return selection({'meta': {'sedra_model': {'provider': payload.get('provider') or 'llama-cpp-server', 'model': payload.get('modell')}}})


def loaded(api, session):
    provider = session.get('provider') or 'llama-cpp-server'
    if provider == 'llama-cpp-server':
        models,error=api.geladen()
        selected=session.get('modell')
        if selected:
            matches=[m for m in models if selected in (m.get('identifier'),m.get('modelKey'))]
            return (matches,None) if matches else ([], 'Das für diesen Chat gewählte lokale Modell ist nicht geladen. Wähle es erneut oder lade es im Modellserver.')
        return models,error
    adapter = api.hub.runtime.model_router.adapters.get(provider)
    if adapter is None:
        return [], 'Der ausgewählte API-Anbieter ist nicht eingeschaltet. Prüfe die Verbindungen.'
    if not adapter.health():
        return [], 'Der ausgewählte API-Anbieter ist nicht bereit. Prüfe Schlüssel und Konfiguration.'
    model = session.get('modell') or adapter.default_model
    if not model:
        return [], 'Wähle ein Modell für diesen Chat.'
    return [{'identifier': model, 'modelKey': model, 'provider': provider}], None
