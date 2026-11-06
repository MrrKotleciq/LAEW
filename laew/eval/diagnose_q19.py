"""Inspect q19 ranks without touching persistent or production stores."""
import json
from pathlib import Path
from laew.manifest import load_manifest
from laew.runtime import build_embedding_service
from laew.rag.knowledge_base import KnowledgeBase
from laew.rag.pipeline import RAGPipeline

def main():
    manifest=load_manifest('manifests/SYSTEM_MANIFEST.yaml')
    embedding=build_embedding_service(manifest)
    root=Path('tests/rag/baseline_v1').resolve()
    data=json.loads((root/'dataset.json').read_text(encoding='utf8'))
    q=next(q for q in data['queries'] if q['id']=='q19')
    query=embedding.embed(q['text'])
    report={}
    for strategy in ['legacy','structure-v1','structure-v2']:
        kb=KnowledgeBase(str(root/'project'),str(root/'global'),embedding,chunking_strategy=strategy)
        kb.synchronize(scope='global')
        ranked=kb.global_store.search(query,top_k=kb.global_store.count())
        report[strategy]=[dict(rank=i+1,id=c.chunk_id,score=score,section=c.metadata.get('section_header'),chars=len(c.text)) for i,(c,score) in enumerate(ranked)]
    Path('docs/reports/context-q19-ranks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')

if __name__ == '__main__':
    main()
