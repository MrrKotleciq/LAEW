"""Real loopback HTTP security boundary with mocked credential persistence."""
import threading
from http.server import ThreadingHTTPServer

import pytest
import requests

from laew.web import WorkspaceService, make_handler


@pytest.fixture
def endpoint(tmp_path, monkeypatch):
    project=tmp_path/'project';project.mkdir()
    service=WorkspaceService(tmp_path/'manifest',project,tmp_path)
    writes=[]
    monkeypatch.setattr('laew.api_credentials.save_api_key',lambda provider,value:writes.append((provider,value)))
    server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(service))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    yield f'http://127.0.0.1:{server.server_port}',service,writes
    server.shutdown();server.server_close();thread.join(2)


@pytest.mark.parametrize('origin,content_type',[(None,'application/json'),('https://external.invalid','application/json'),('same','text/plain')])
def test_key_endpoint_requires_same_origin_json(endpoint,origin,content_type):
    base,service,writes=endpoint
    headers={'Content-Type':content_type}
    if origin:headers['Origin']=base if origin=='same' else origin
    response=requests.post(base+'/api/cloud/key',json={'session_id':'fixture-session-123','provider':'gemini','api_key':'synthetic-secret'},headers=headers,timeout=3)
    assert response.status_code==403 and not writes
    assert 'synthetic-secret' not in response.text


def test_success_never_returns_key_and_active_run_blocks_changes(endpoint):
    base,service,writes=endpoint
    body={'session_id':'fixture-session-123','provider':'gemini','api_key':'synthetic-secret'}
    headers={'Origin':base}
    with service._lock:
        response=requests.post(base+'/api/cloud/key',json=body,headers=headers,timeout=3)
        assert response.status_code==422 and response.json()['code']=='BUSY' and not writes
    response=requests.post(base+'/api/cloud/key',json=body,headers=headers,timeout=3)
    assert response.status_code==200 and response.json()['configured']
    assert writes==[('gemini','synthetic-secret')]
    assert 'synthetic-secret' not in response.text
