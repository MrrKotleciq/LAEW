"""Descriptive, offline diagnostics for fixed real-world retrieval arms."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import statistics
import numpy as np
from laew.eval.real_world_retrieval import read, write, sha, check, coverage_of, span_present


def distribution(values):
    values=[v for v in values if v is not None]
    return dict(n=len(values),mean=statistics.mean(values),p50=float(np.percentile(values,50)),p95=float(np.percentile(values,95)),maximum=max(values)) if values else dict(n=0,mean=None,p50=None,p95=None,maximum=None)


def analyze(corpus,run,score,datasets,out):
    check(not out.exists(),'New analysis output required')
    rows=read(score/'per-question.json');traces=read(run/'retrieval-traces.json')
    by={(r['question_id'],r['arm']):r for r in rows}
    spans={s['id']:s for d in datasets for s in read(d/'evidence-spans.json')}
    units=read(corpus/'corpus/source-manifest.json')['source_units']
    texts={u['id']:(corpus/'corpus'/u['normalized_path']).read_text(encoding='utf-8') for u in units}
    risks=read(corpus/'review/r3d/inherited-unresolved-risk-register.json')
    uninspected={(r['source_id'],r['page']) for r in read(corpus/'review/r3d/uninspected-high.json')}
    diag=[]
    for r in traces:
        s=by[r['question_id'],r['arm']]
        stages={}
        for stage in ['raw','eligible','selected']:
            cov=coverage_of(r[stage]);hit=[v for v in spans.values() if span_present(v,cov,texts)]
            stages[stage]=dict(fragments=len(r[stage]),source_ids=sorted(cov),proposed_spans_present=[v['id'] for v in hit],proposed_span_languages=sorted({v['actual_evidence_language'] for v in hit}))
        raw_text={c['id']:c['text'] for c in r['raw']}
        attribution_invalid=sum(c['source_id'] not in texts or c['source_sha256']!=next(u['normalized_sha256'] for u in units if u['id']==c['source_id']) or not c['source_ranges'] for c in r['selected'])
        selected_cov=coverage_of(r['selected'])
        exposed=[dict(source_id=risk['source_id'],page=risk['page'],original_severity=risk['original_severity'],uninspected_high=(risk['source_id'],risk['page']) in uninspected) for risk in risks if any(max(a,risk['start'])<min(z,risk['end']) for a,z in selected_cov.get(risk['source_id'],[]))]
        diag.append(dict(question_id=r['question_id'],family_id=r['family_id'],split=r['split'],arm=r['arm'],language=r['language'],stages=stages,rendered_characters=len(r['context']),enclosing_characters=len(r['enclosing_context']),estimated_tokens=r['estimated_tokens'],actual_embedding_tokenizer_tokens=r['actual_tokens'],selected_fragments=len(r['selected']),clipped_fragments=sum(c['text']!=raw_text[c['id']] for c in r['selected']),unsupported_attribution_fragments=attribution_invalid,index_complete=s['index_available']['complete'],errors=s['errors'],open_page_risk_exposure=exposed))
    grouped={}
    for split in ['pilot','sealed']:
        for arm in ['A','B','C']:
            items=[d for d in diag if d['split']==split and d['arm']==arm];scored=[by[d['question_id'],arm] for d in items]
            answerable=[r for r in scored if r['raw']['complete'] is not None]
            grouped[split+'/'+arm]=dict(questions=len(items),answerable_questions=len(answerable),tokens=distribution([d['estimated_tokens'] for d in items]),actual_embedding_tokenizer_tokens=distribution([d['actual_embedding_tokenizer_tokens'] for d in items]),rendered_characters=distribution([d['rendered_characters'] for d in items]),fragments=distribution([d['selected_fragments'] for d in items]),clipped_fragments=sum(d['clipped_fragments'] for d in items),unsupported_attribution_fragments=sum(d['unsupported_attribution_fragments'] for d in items),index_incomplete_questions=sum(d['index_complete'] is False for d in items),error_fact_counts=dict(Counter(e['reason'] for d in items for e in d['errors'])),complete_counts={stage:sum(r[stage]['complete'] is True for r in answerable) for stage in ['raw','eligible','selected']},facts_delivered_per_1000_estimated_tokens=1000*sum(len(r['selected']['facts_hit']) for r in answerable)/sum(r['estimated_tokens'] for r in answerable) if sum(r['estimated_tokens'] for r in answerable) else None)
    paired=[];regressions=[]
    for before,after in [('A','B'),('B','C')]:
        for split in ['pilot','sealed']:
            ids=[r['question_id'] for r in rows if r['split']==split and r['arm']==before and r['raw']['complete'] is not None]
            family=defaultdict(list)
            for q in ids:
                a,b=by[q,before],by[q,after]
                item=dict(question_id=q,family_id=a['family_id'],before=before,after=after,stages={stage:dict(recall_delta=b[stage]['fact_recall']-a[stage]['fact_recall'],complete_before=a[stage]['complete'],complete_after=b[stage]['complete']) for stage in ['raw','eligible','selected']},token_delta=b['estimated_tokens']-a['estimated_tokens'])
                family[a['family_id']].append(item)
                if any(x['recall_delta']<0 or (x['complete_before'] and not x['complete_after']) for x in item['stages'].values()):regressions.append(item)
            paired.append(dict(split=split,before=before,after=after,answerable_families=len(family),answerable_questions=len(ids),family_mean_recall_delta={stage:statistics.mean(statistics.mean(i['stages'][stage]['recall_delta'] for i in group) for group in family.values()) for stage in ['raw','eligible','selected']},family_mean_token_delta=statistics.mean(statistics.mean(i['token_delta'] for i in group) for group in family.values()),uncertainty='Descriptive only; translations and connected sealed clusters are dependent; no significance claim'))
    timing=read(run/'timing.json')
    latency={arm:distribution([v for t in timing['warm'] if t['arm']==arm for v in t['samples_ms']]) for arm in ['A','B','C']}
    rebuild={arm:dict(checks=sum(r['arm']==arm for r in timing['rebuild_checks']),membership_changes=sum(r['arm']==arm and r['membership_changed'] for r in timing['rebuild_checks']),order_changes=sum(r['arm']==arm and r['order_changed'] for r in timing['rebuild_checks'])) for arm in ['A','B','C']}
    native={'S01':'en','S05':'en','S06':'de','S07':'de','S08':'pl','S09':'pl'}
    cross={}
    for arm in ['A','B','C']:
        items=[r for r in rows if r['arm']==arm and r['family_id'] in native and r['language']!=native[r['family_id']]]
        check(len(items)==12,'Expected twelve predeclared required cross-language cases')
        for direction in sorted({r['language']+'->'+native[r['family_id']] for r in items}):
            group=[r for r in items if r['language']+'->'+native[r['family_id']]==direction]
            cross[arm+'/'+direction]=dict(questions=len(group),families=len({r['family_id'] for r in group}),status='Agent-draft cross-language necessity; independent adjudication pending',stages={stage:dict(fact_recall=statistics.mean(r[stage]['fact_recall'] for r in group),complete=statistics.mean(r[stage]['complete'] for r in group)) for stage in ['raw','eligible','selected']})
    out.mkdir(parents=True)
    write(out/'context-diagnostics.json',diag)
    write(out/'analysis.json',dict(status='exploratory-provisional-agent-draft',grouped=grouped,paired=paired,predeclared_cross_language=cross,warm_search_latency_ms=latency,rebuild=rebuild,regressions=regressions,trace_manifest_sha256=sha(run/'trace-integrity.json'),scoring_provenance_sha256=sha(score/'provenance.json'),analysis_code_sha256=sha(Path(__file__)),unjudged_context_policy='Unknown relevance, never automatically irrelevant',risk_exposure_policy='Page-level open flags are retained; targeted span QA does not clear a page or certify all context',generation_calls=0))
    return dict(output=str(out),questions_arms=len(diag),regressions=len(regressions),sha256=sha(out/'analysis.json'))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ['corpus','run','score','output']:ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--dataset',type=Path,action='append',required=True)
    a=ap.parse_args();print(json.dumps(analyze(a.corpus,a.run,a.score,a.dataset,a.output),indent=2))
