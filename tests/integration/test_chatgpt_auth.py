"""OAuth, signed ID tokens and protected-store behavior without real accounts."""

import copy
import json
import time
import threading
from urllib.parse import urlencode
from unittest.mock import Mock

import pytest

pytest.importorskip('authlib')
from authlib.jose import JsonWebKey, JsonWebToken

from laew.chatgpt_auth import ChatGPTAuth, CredentialStore, ISSUER, SCOPES
from laew.cloud_chat import CloudError


class Store:
    def __init__(self): self.data = {'accounts': {}}
    def load(self): return copy.deepcopy(self.data)
    def save(self, data): self.data = copy.deepcopy(data)


@pytest.fixture
def auth(tmp_path, monkeypatch):
    monkeypatch.setattr('laew.chatgpt_auth.tempfile.gettempdir', lambda: str(tmp_path))
    service = ChatGPTAuth(Store())
    key = JsonWebKey.generate_key('RSA', 2048, {'kid':'fixture'}, is_private=True)
    service._metadata = lambda: {'jwks_uri': ISSUER + '/fixture/jwks', 'revocation_endpoint': ISSUER + '/fixture/revoke'}
    service.fixture_key = key
    yield service
    service.close()


def prepare(auth, monkeypatch, claims_update=None, token_update=None, account=None):
    result = auth.start('browser-session-123', account)
    attempt = auth._attempts[result['attempt_id']]
    client_id = attempt['client_id'] or 'oaiapp_fixture'
    claims = {'iss':ISSUER, 'aud':client_id, 'sub':'fixture-subject', 'email':'fixture@example.invalid',
              'iat':int(time.time()), 'exp':int(time.time())+300, 'nonce':attempt['nonce']}
    claims.update(claims_update or {})
    encoded = JsonWebToken(['RS256']).encode({'alg':'RS256','kid':'fixture'}, claims, auth.fixture_key).decode()
    tokens = {'access_token':'access-secret', 'refresh_token':'refresh-secret', 'id_token':encoded,
              'expires_in':3600,'token_type':'Bearer','scope':SCOPES}
    tokens.update(token_update or {})
    calls = []
    def request(method, url, **kwargs):
        calls.append((method,url,kwargs))
        return {'keys':[auth.fixture_key.as_dict(is_private=False)]} if method == 'GET' else tokens
    monkeypatch.setattr(auth, '_json_request', request)
    return result, attempt, calls


def finish(auth, result, attempt, **updates):
    params = {'state':attempt['state'],'code':'code-secret','client_id':attempt['client_id'] or 'oaiapp_fixture'}
    params.update(updates)
    auth._complete(result['attempt_id'], params)


def test_registration_identity_storage_replay_and_safe_status(auth, monkeypatch):
    result, attempt, calls = prepare(auth, monkeypatch)
    finish(auth, result, attempt)
    account = attempt['account_id']
    assert auth.credential(account) == 'access-secret'
    assert auth.store.data['host_id'].startswith('urn:uuid:')
    status = json.dumps(auth.status('browser-session-123'))
    assert 'access-secret' not in status and 'refresh-secret' not in status and 'id_token' not in status
    assert len(auth.status('browser-session-123')['accounts']) == 1
    with pytest.raises(CloudError): finish(auth, result, attempt)
    assert len([c for c in calls if c[0] == 'POST']) == 1


@pytest.mark.parametrize('claims', [{'nonce':'wrong'}, {'iss':'https://evil.invalid'}, {'aud':'wrong'},
                                   {'exp':1}, {'sub':''}])
def test_invalid_identity_does_not_store_tokens(auth, monkeypatch, claims):
    result, attempt, _ = prepare(auth, monkeypatch, claims_update=claims)
    with pytest.raises(CloudError): finish(auth, result, attempt)
    assert not auth.store.data['accounts']


def test_bad_state_and_signature_and_denial(auth, monkeypatch):
    result, attempt, calls = prepare(auth, monkeypatch, token_update={'id_token':'not-a-signed-token'})
    with pytest.raises(CloudError): finish(auth, result, attempt, state='wrong')
    assert not calls
    with pytest.raises(CloudError): finish(auth, result, attempt)
    assert not auth.store.data['accounts']
    result, attempt, _ = prepare(auth, monkeypatch)
    with pytest.raises(CloudError, match='denied'): finish(auth, result, attempt, error='access_denied')
    assert not auth.store.data['accounts']


def test_missing_plan_scope_is_not_successful_login(auth, monkeypatch):
    result, attempt, _ = prepare(auth, monkeypatch, token_update={'scope':'openid profile email'})
    with pytest.raises(CloudError) as exc: finish(auth, result, attempt)
    assert exc.value.code == 'PLAN_PERMISSION_REQUIRED'
    assert not auth.store.data['accounts']


def test_cancel_and_timeout_attempts_cannot_complete(auth, monkeypatch):
    result, attempt, _ = prepare(auth, monkeypatch)
    auth.cancel_attempt('browser-session-123', result['attempt_id'])
    with pytest.raises(CloudError): finish(auth, result, attempt)
    result, attempt, _ = prepare(auth, monkeypatch)
    attempt['expires'] = 0
    with pytest.raises(CloudError): finish(auth, result, attempt)
    assert not auth.store.data['accounts']


def test_refresh_rotates_atomically_and_returning_login_checks_identity(auth, monkeypatch):
    result, attempt, _ = prepare(auth, monkeypatch)
    finish(auth, result, attempt)
    account = attempt['account_id']
    auth.store.data['accounts'][account]['expires_at'] = 0
    request = Mock(return_value={'access_token':'replacement-access','refresh_token':'replacement-refresh',
                                'scope':SCOPES,'token_type':'Bearer','expires_in':3600})
    monkeypatch.setattr(auth, '_json_request', request)
    results = []
    workers = [threading.Thread(target=lambda: results.append(auth.credential(account))) for _ in range(2)]
    for worker in workers: worker.start()
    for worker in workers: worker.join(3)
    assert results == ['replacement-access', 'replacement-access']
    assert request.call_count == 1
    assert auth.store.data['accounts'][account]['refresh_token'] == 'replacement-refresh'
    host = auth.store.data['host_id']
    result, attempt, _ = prepare(auth, monkeypatch, claims_update={'sub':'different-subject'}, account=account)
    with pytest.raises(CloudError): finish(auth, result, attempt)
    assert auth.store.data['accounts'][account]['subject'] == 'fixture-subject'
    assert auth.store.data['host_id'] == host


def test_callback_http_and_separate_registrations_with_same_email(auth, monkeypatch):
    import requests
    result, attempt, _ = prepare(auth, monkeypatch)
    callback = requests.get(attempt['redirect_uri'] + '?' + urlencode({
        'state':attempt['state'], 'code':'synthetic', 'client_id':'oaiapp_fixture'}), timeout=3)
    assert callback.status_code == 200
    first = attempt['account_id']
    result, attempt, _ = prepare(auth, monkeypatch, claims_update={'aud':'oaiapp_second'})
    finish(auth, result, attempt, client_id='oaiapp_second')
    assert len(auth.store.data['accounts']) == 2 and first != attempt['account_id']
    assert len({record['email'] for record in auth.store.data['accounts'].values()}) == 1


def test_logout_erases_tokens_even_if_revocation_fails(auth, monkeypatch):
    import requests
    result, attempt, _ = prepare(auth, monkeypatch)
    finish(auth, result, attempt)
    monkeypatch.setattr('laew.chatgpt_auth.requests.post', Mock(side_effect=requests.ConnectionError('private-fixture')))
    data = auth.logout(attempt['account_id'])
    assert data['signed_out'] and not data['revocation_confirmed']
    record = auth.store.data['accounts'][attempt['account_id']]
    assert not {'access_token','refresh_token','id_token'}.intersection(record)
    assert record['client_id'] == 'oaiapp_fixture'
    with pytest.raises(CloudError): auth.credential(attempt['account_id'])


def test_keyring_large_records_and_failed_rotation_keep_previous(monkeypatch):
    store = CredentialStore()
    class Backend:
        values = {}
        def get_password(self, service, name): return self.values.get(name)
        def set_password(self, service, name, value):
            assert len(value) <= 1000
            self.values[name] = value
        def delete_password(self, service, name): self.values.pop(name, None)
    backend = Backend()
    monkeypatch.setattr(store, '_backend', lambda: backend)
    data = {'accounts':{'fixture':{'id_token':'x' * 16000}}}
    store.save(data)
    assert store.load() == data
    original = backend.set_password
    def fail_manifest(service, name, value):
        if name == 'registrations': raise RuntimeError('private-fixture')
        original(service, name, value)
    monkeypatch.setattr(backend, 'set_password', fail_manifest)
    with pytest.raises(CloudError): store.save({'accounts':{}})
    assert store.load() == data


def test_plaintext_keyring_is_rejected(monkeypatch):
    import keyring
    class Plaintext:
        priority = 100
    monkeypatch.setattr(keyring, 'get_keyring', lambda: Plaintext())
    with pytest.raises(CloudError, match='supported OS'): CredentialStore().load()
