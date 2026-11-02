"""Credential writes are mocked: tests never change user environment settings."""
import os
from unittest.mock import MagicMock

import pytest

from laew.api_credentials import save_api_key
from laew.cloud_chat import CloudError


@pytest.mark.parametrize('provider,variable', [('gemini','GEMINI_API_KEY'),('openai-api','OPENAI_API_KEY')])
def test_key_saved_to_user_environment_and_process(monkeypatch, provider, variable):
    monkeypatch.setattr('laew.api_credentials._notify_environment_change',lambda:None)
    winreg=pytest.importorskip('winreg')
    key=MagicMock(); monkeypatch.setattr(winreg,'CreateKeyEx',key)
    write=MagicMock();monkeypatch.setattr(winreg,'SetValueEx',write)
    monkeypatch.setenv(variable,'old-synthetic')
    save_api_key(provider,'synthetic-fixture-key')
    assert os.environ[variable]=='synthetic-fixture-key'
    assert key.call_args.args[1]=='Environment'
    assert write.call_args.args[1:]==(variable,0,winreg.REG_SZ,'synthetic-fixture-key')


@pytest.mark.parametrize('provider,value',[('chatgpt','synthetic-key'),('gemini',''),('gemini','bad key value'),('gemini',None)])
def test_invalid_key_rejected_without_exposing_value(provider,value):
    with pytest.raises(CloudError) as error: save_api_key(provider,value)
    assert error.value.code=='INVALID_REQUEST'
    assert 'synthetic' not in str(error.value)


def test_failed_persistence_leaves_process_key_unchanged(monkeypatch):
    winreg=pytest.importorskip('winreg')
    monkeypatch.setenv('GEMINI_API_KEY','original-synthetic')
    def fail(*args): raise OSError('private-fixture')
    monkeypatch.setattr(winreg,'CreateKeyEx',fail)
    with pytest.raises(CloudError) as error: save_api_key('gemini','new-synthetic-key')
    assert os.environ['GEMINI_API_KEY']=='original-synthetic'
    assert 'private-fixture' not in str(error.value)
