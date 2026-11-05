"""Local n8n REST adapter. No redirects, proxies, arbitrary URLs or retries."""
from copy import deepcopy
import http.client
import json
import os
import re
import secrets
import socket
from pathlib import Path
from urllib.parse import urlsplit
from ..core.request_binding import digest
from .policy import executable, PROFILE

LIMIT = 1_000_000


def configuration(project):
    path = Path(project) / 'local_config' / 'n8n.json'
    if not path.exists():
        return {'enabled': False}
    raw = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(raw, dict) or set(raw) - {'enabled', 'base_url', 'api_key_env'}:
        raise ValueError('invalid_n8n_configuration')
    if raw.get('enabled') is not True:
        return {'enabled': False}
    if not isinstance(raw.get('base_url'), str):
        raise ValueError('invalid_n8n_configuration')
    url = urlsplit(raw['base_url'])
    if url.scheme != 'http' or url.hostname != '127.0.0.1' or url.username or url.password or url.path not in ('', '/') or url.query or url.fragment or not url.port or not 1024 <= url.port <= 65535:
        raise ValueError('n8n_requires_numeric_loopback_url')
    env = raw.get('api_key_env', 'SEDRA_N8N_API_KEY')
    if not isinstance(env, str) or not re.fullmatch('[A-Z][A-Z0-9_]{2,63}', env):
        raise ValueError('invalid_n8n_key_reference')
    return {'enabled': True, 'base_url': f'http://127.0.0.1:{url.port}', 'api_key_env': env}


def inputs(value):
    if not isinstance(value, dict):
        raise ValueError('n8n_inputs_must_be_object')
    try:
        raw = json.dumps(value, allow_nan=False)
    except (ValueError, TypeError, RecursionError) as exc:
        raise ValueError('invalid_n8n_inputs') from exc
    if len(raw.encode('utf-8')) > 65536:
        raise ValueError('n8n_input_size_limit')
    return deepcopy(value)


class EngineError(RuntimeError):
    pass


class LocalN8n:
    def __init__(self, config):
        self.config = config
        if not config.get('enabled'):
            raise EngineError('n8n_not_configured')
        self.key = os.environ.get(config['api_key_env'])
        if not self.key or '\n' in self.key or '\r' in self.key:
            raise EngineError('n8n_api_key_missing')
        self.port = urlsplit(config['base_url']).port

    def request(self, method, path, body=None, *, api=True):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=12 if not api else 5)
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        if api:
            headers['X-N8N-API-KEY'] = self.key
        try:
            conn.request(method, path, body=json.dumps(body, allow_nan=False).encode('utf-8') if body is not None else None, headers=headers)
            response = conn.getresponse()
            data = response.read(LIMIT + 1)
            if len(data) > LIMIT:
                raise EngineError('n8n_response_size_limit')
            if not 200 <= response.status < 300:
                raise EngineError('n8n_http_' + str(response.status))
            try:
                return json.loads(data) if data else None
            except (ValueError, UnicodeError) as exc:
                raise EngineError('n8n_invalid_response') from exc
        finally:
            conn.close()

    def run(self, workflow, input_data):
        doc = executable(workflow)
        payload = inputs(input_data)
        path = 'sedra-' + secrets.token_hex(24)
        start_name = '__SEDRA_' + secrets.token_hex(8)
        original = next(n for n in doc['nodes'] if n['type'] == 'n8n-nodes-base.manualTrigger')
        original.update(type='n8n-nodes-base.set', typeVersion=3.4,
                        parameters={'mode': 'raw', 'jsonOutput': '={{ $json.body }}', 'options': {}})
        doc['nodes'].append({'id': secrets.token_hex(16), 'name': start_name, 'type': 'n8n-nodes-base.webhook',
                             'typeVersion': 2, 'position': [-250, 0], 'webhookId': secrets.token_hex(16),
                             'parameters': {'httpMethod': 'POST', 'path': path, 'responseMode': 'lastNode',
                                            'responseData': 'allEntries', 'options': {}}})
        doc['connections'][start_name] = {'main': [[{'node': original['name'], 'type': 'main', 'index': 0}]]}
        doc['name'] = 'SEDRA temporary ' + path[-12:]
        doc['settings'].update(saveDataSuccessExecution='none', saveDataErrorExecution='none', saveManualExecutions=False)
        remote_id, attempted = None, False
        result = {'status': 'failed', 'profile': PROFILE, 'cleanup_errors': [], 'remote_workflow_name': doc['name']}
        try:
            created = self.request('POST', '/api/v1/workflows', doc)
            remote_id = created.get('id') if isinstance(created, dict) else None
            if not isinstance(remote_id, str) or not re.fullmatch('[A-Za-z0-9_-]{1,100}', remote_id):
                raise EngineError('n8n_creation_outcome_unknown')
            result['remote_workflow_id'] = remote_id
            self.request('POST', f'/api/v1/workflows/{remote_id}/activate', {})
            observed = self.request('GET', f'/api/v1/workflows/{remote_id}')
            fields = ('id', 'name', 'type', 'typeVersion', 'parameters', 'position', 'webhookId')
            expected_nodes = [{k: n[k] for k in fields if k in n} for n in doc['nodes']]
            actual_nodes = [{k: n[k] for k in fields if k in n} for n in observed.get('nodes', [])]
            if digest(expected_nodes) != digest(actual_nodes) or observed.get('connections') != doc['connections']:
                raise EngineError('n8n_remote_workflow_changed')
            attempted = True
            result['output'] = self.request('POST', '/webhook/' + path, payload, api=False)
            result['status'] = 'completed'
        except (EngineError, OSError, http.client.HTTPException, ValueError, TypeError, KeyError) as exc:
            result['error'] = 'UNKNOWN_REMOTE_OUTCOME' if attempted else (
                str(exc) if isinstance(exc, EngineError) else 'n8n_connection_or_protocol_error')
            result['remote_outcome'] = 'unknown' if attempted else 'not_triggered'
            if remote_id is None:
                result['error'] = 'n8n_creation_outcome_unknown'
                result['cleanup_errors'].append('Creation outcome unknown; inspect temporary workflow by name')
        finally:
            if remote_id and re.fullmatch('[A-Za-z0-9_-]{1,100}', remote_id):
                for method, suffix in (('POST', '/deactivate'), ('DELETE', '')):
                    try:
                        self.request(method, f'/api/v1/workflows/{remote_id}' + suffix)
                    except (EngineError, OSError, http.client.HTTPException, ValueError):
                        result['cleanup_errors'].append(method + ' temporary workflow')
        return result
