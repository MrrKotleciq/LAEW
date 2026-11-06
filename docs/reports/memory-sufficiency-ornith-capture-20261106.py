import json
from pathlib import Path
import requests
import laew.eval.memory_sufficiency_eval as evaluation
records=[]
original=requests.post
def capture(*args,**kwargs):
    response=original(*args,**kwargs)
    if '/chat/completions' in args[0]:
        body=response.json()
        choice=body['choices'][0]
        records.append({'request':kwargs['json'], 'usage':body.get('usage'), 'finish_reason':choice.get('finish_reason'), 'message':choice.get('message')})
        Path('docs/reports/memory-sufficiency-ornith-replay-http-20261106.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return response
requests.post=capture
cases=json.loads(evaluation.DATASET.read_text(encoding='utf-8-sig'))
result=evaluation.evaluate(cases,{'active':('Ornith-1.5-9B','http://127.0.0.1:8080'),'dedicated':(None,'http://127.0.0.1:8080')})
Path('docs/reports/memory-sufficiency-ornith-replay-20261106.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Captured',len(records),'responses')
