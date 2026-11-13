"""Observe the first serialized dispatch, stopping before any network or answer."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
from unittest.mock import patch

from laew.agent import Agent, AgentConfig, AgentExecutor
from laew.cloud_chat import ResponsesTransport
from laew.llm.cloud import OpenAIProvider
from laew.eval.real_world_retrieval import read, sha, write, check


class DispatchObserved(BaseException):
    """Exit the real executor before a response, continuation or retry exists."""


def observe(question, context):
    payloads=[]
    def capture(self, session, method, path, credential, **kwargs):
        check(method=='POST' and path=='/responses','Unexpected dispatch')
        check(credential=='fixture-not-a-real-credential','Unexpected credential')
        payloads.append(json.loads(json.dumps(kwargs['json'],ensure_ascii=False)))
        raise DispatchObserved()
    def forbidden(*args,**kwargs):
        raise AssertionError('Network/credential access is forbidden during replay')
    provider=OpenAIProvider(provider_type='chatgpt',credential=lambda:'fixture-not-a-real-credential',transport=ResponsesTransport())
    executor=AgentExecutor(Agent(AgentConfig(model='fixture-no-generation',max_iterations=1),provider=provider,tools=[]))
    executor.knowledge_context=context
    with patch.object(ResponsesTransport,'_response',capture),patch.object(socket,'create_connection',forbidden),patch('requests.Session.request',forbidden),patch('laew.cloud_chat.CloudChatService',forbidden):
        try:executor.run(question)
        except DispatchObserved:pass
        else:raise AssertionError('First dispatch was not intercepted')
    check(len(payloads)==1,'Replay must observe exactly one first dispatch')
    p=payloads[0]
    check(p['store'] is False and p['stream'] is True and p.get('tools')==[],'Unexpected effective payload settings')
    check('temperature' not in p and 'max_output_tokens' not in p,'Unsupported OAuth settings introduced')
    check(context in p['instructions'],'Rendered context lost in executor/OAuth serialization')
    check(any(i.get('role')=='user' and i.get('content')==question for i in p['input']),'Question changed during serialization')
    check(not any(i.get('role')=='system' for i in p['input']),'System content was not converted to instructions')
    return dict(first_dispatch_context_received=True,context_sha256=hashlib.sha256(context.encode()).hexdigest(),instructions_sha256=hashlib.sha256(p['instructions'].encode()).hexdigest(),serialized_payload_sha256=hashlib.sha256(json.dumps(p,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),tools=[],network_requests=0,answers_generated=0)


def replay(run,questions,out):
    check(not out.exists(),'Never overwrite replay artifacts')
    inv=read(run/'trace-integrity.json')
    for f in inv['files']:check(sha(run/f['path'])==f['sha256'],'Trace changed before replay')
    check(sha(questions)==read(run/'run-metadata.json')['question_sha256'],'Questions changed before replay')
    qs={q['id']:q['text'] for q in read(questions)}
    rows=[]
    for r in read(run/'retrieval-traces.json'):
        rows.append(dict(question_id=r['question_id'],arm=r['arm'],**observe(qs[r['question_id']],r['enclosing_context'])))
    out.mkdir(parents=True)
    write(out/'payload-replay.json',dict(method='Real AgentExecutor, OpenAIProvider and ResponsesTransport payload construction; first dispatch intercepted before HTTP, no synthetic or generated answer',rows=rows,source_trace_manifest_sha256=sha(run/'trace-integrity.json'),replay_code_sha256=sha(Path(__file__)),generation_calls=0,network_requests=0,real_credentials_accessed=False))
    return dict(rows=len(rows),all_contexts_received=True,sha256=sha(out/'payload-replay.json'),generation_calls=0)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,required=True);ap.add_argument('--questions',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();print(json.dumps(replay(a.run,a.questions,a.output),indent=2))
