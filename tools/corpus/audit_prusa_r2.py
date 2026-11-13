"""R2 offline source/packet audit; no store, retrieval, inference, or admission."""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from laew.rag.knowledge_base import KnowledgeBase
from prusa_pdf_r2 import guard_inputs,sha,dump


def flat(text):
    return re.sub(r'\s+','',text.replace('**','').replace('<br>',' ').replace('\\|','|'))


def chunk(path,text,strategy):
    kb=object.__new__(KnowledgeBase);kb.chunk_size=1000;kb.chunk_overlap=200;kb.chunking_strategy=strategy
    result=kb._load_file(path,'global',path.parent,content=text,embed=False)
    assert all(c.embedding is None for c in result)
    return result


def audit(corpus,r1,output):
    guard_inputs(corpus,r1,output,record=False)
    old=json.loads((r1/'structural-audit-418.json').read_text(encoding='utf-8'))
    original_flags={(r['id'],r['page']):r['flags'] for r in old['records']}
    relations=json.loads((output/'dependency-relations.json').read_text(encoding='utf-8'))
    relation_by_id={r['id']:r for r in relations}
    results=json.loads((output/'candidate-results.json').read_text(encoding='utf-8'))
    all_pages=[];manuals=[];warnings=[]
    priorities={'Critical':4,'High':3,'Medium':2,'Low':1}
    for source in results:
        sid=source['id'];path=output/source['candidate_path'];text=path.read_text(encoding='utf-8')
        mapping=json.loads((output/'maps'/f'{sid}.json').read_text(encoding='utf-8'))
        pages={p['page']:p for p in (json.loads(file.read_text(encoding='utf-8')) for file in sorted((output/'structured'/sid).glob('*.json')))}
        all_blocks={b['id']:b for page in pages.values() for b in page['blocks']}
        all_blocks.update({b['id']:b for b in mapping.get('derived_dependencies',[])})
        stats={};packet_failures=defaultdict(list)
        for strategy in ('legacy','structure-v2'):
            chunks=chunk(path,text,strategy)
            by_header={c.text.splitlines()[0]:c for c in chunks}
            for packet in mapping['packets']:
                header=packet['text'].splitlines()[0]
                # A source heading may create a separate harmless heading chunk; packets remain bounded leaves.
                own=by_header.get(header) or next((c for c in chunks if header in c.text),None)
                if own is None:packet_failures[packet['page']].append(strategy+': missing packet');continue
                for dependency in packet['dependencies']:
                    if all_blocks[dependency]['text'] not in own.text:packet_failures[packet['page']].append(strategy+': incomplete dependency '+dependency)
                if len(own.text)>1000:packet_failures[packet['page']].append(strategy+': oversized packet')
            partition=True
            if strategy=='structure-v2':partition=''.join(text[c.metadata['start_offset']:c.metadata['end_offset']] for c in chunks)==text
            stats[strategy]=dict(chunks=len(chunks),max_characters=max((len(c.text) for c in chunks),default=0),
                delivered_chunk_characters=sum(len(c.text) for c in chunks),source_partition_exact=partition if strategy=='structure-v2' else None,
                dependency_failure_count=sum(len(v) for v in packet_failures.values()))
        source_warnings=[b for b in all_blocks.values() if b['kind'] in ('warning','information','icon-note','callout')]
        for note in source_warnings:
            uses=[p for p in mapping['packets'] if note['id'] in p['dependencies']]
            warnings.append(dict(id=note['id'],source_id=sid,page=note['page'],scope=note.get('scope'),topic=note.get('topic'),
                policy=note.get('dependency_policy'),repeated_packets=len(uses),target_pages=sorted(set(p['page'] for p in uses)),
                status='reviewed-rule-materialized' if uses else 'primary-only-needs-applicability-review'))
        for number,page in pages.items():
            raw=json.loads((output/'geometry'/sid/f'{number:03d}.json').read_text(encoding='utf-8'))
            flags=[];severity='Low'
            def add(level,reason):
                nonlocal severity
                flags.append(dict(severity=level,reason=reason))
                if priorities[level]>priorities[severity]:severity=level
            owners=defaultdict(list)
            for b in page['blocks']:
                for i in b['source_lines']:owners[i].append(b)
            missing=[];duplicate=[];glyph_missing=[];cells_missing=[];numeric_missing=[]
            footer=[line['index'] for line in raw['lines'] if line['top']>raw['height']*.92 and line['text'].strip()==str(number)]
            for line in raw['lines']:
                if line['index'] in footer:continue
                owned=owners[line['index']]
                if not owned:missing.append(line['index']);continue
                if len(owned)>1:duplicate.append(line['index'])
                b=owned[0]
                if b['kind']=='table':continue
                source_text=''.join(c['text'] for c in sorted(line['chars'],key=lambda c:c['x0']))
                source_text=re.sub(r'^[❏□▢]\s*','',source_text)
                if flat(source_text) not in flat(b['text']):glyph_missing.append(line['index'])
            for b in page['blocks']:
                if b['kind']=='table':
                    for row in b['source_rows']:
                        for value in row:
                            if not value:continue
                            source_cell=flat(value).replace('•','')
                            rendered=flat(b['text'].replace('\n- ','')).replace('•','')
                            if source_cell not in rendered:cells_missing.append({'block':b['id'],'row':b['source_rows'].index(row)})
                            for token in re.findall(r'\d+(?:[.,/]\d+)*(?:%\+?)?',value):
                                if token not in b['text']:numeric_missing.append(token)
            if missing or duplicate or glyph_missing:add('Critical','source-line/glyph ownership mismatch')
            if cells_missing or numeric_missing:add('Critical','table cell or numeric value mismatch')
            if packet_failures[number]:add('Critical','warning packet/chunker contract failure')
            for flag in original_flags[(sid,number)]:
                if flag in ('substantial-image-visual-review','merged-or-ambiguous-table-cells','rotated-text-review','complex-vector-grid'):add('High',flag)
                else:add('Medium',flag)
            for flag in page['extraction_flags']:
                add('Critical' if flag=='menu-parent-unresolved' else 'High',flag)
            primary_ids={b['id'] for b in page['blocks']}
            unreviewed=[w for w in source_warnings if w['id'] in primary_ids and not any(w['id'] in p['dependencies'] for p in mapping['packets'])]
            if unreviewed:add('High','callout-applicability-not-certified')
            if any(relation_by_id.get(i,{}).get('candidate_dependencies_not_materialized') for i in primary_ids):add('High','unreviewed-dependency-candidates-not-materialized')
            inline=[b['id'] for b in page['blocks'] if b['kind'] in ('paragraph','step') and re.search(r'\b(must|never|before|unless|ensure|only|bevor|niemals|müssen|nur|przed|nigdy|tylko|upewnij|jeśli|jeżeli)\b',b['text'],re.I)]
            if inline:add('High','inline-condition-applicability-review')
            if any(not page['blocks'][i]['top']<=page['blocks'][i+1]['top'] for i in range(len(page['blocks'])-1)):add('Critical','block reading order inversion')
            source_partitions=[]
            for component in (c for c in mapping['components'] if c['page']==number):
                fragments=[p for p in mapping['packets'] if p['component_id']==component['id']]
                if fragments:
                    intervals=[(p['start'],p['end']) for p in fragments]
                    if intervals[0][0]!=0 or intervals[-1][1]!=len(component['text']) or any(a[1]!=z[0] for a,z in zip(intervals,intervals[1:])):source_partitions.append(component['id'])
            if source_partitions:add('Critical','primary representation range discontinuity')
            all_pages.append(dict(source_id=sid,page=number,severity=severity,flags=flags,
                inspection_outcome='Requires manual review',source_lines=len(raw['lines'])-len(footer),source_lines_missing=missing,
                duplicate_primary_lines=duplicate,glyph_lines_missing=glyph_missing,table_cells_missing=cells_missing,numeric_values_missing=numeric_missing,
                packet_failures=packet_failures[number],inline_condition_blocks=inline,primary_partition_errors=source_partitions,
                source_heading_corrections=sum(b.get('r2_correction')=='source font/numbered subsection recovered' for b in page['blocks']),
                full_page_render_exists=(output/'page-renders'/sid/f'page-{number:03d}.png').is_file()))
        manuals.append({**source,'chunking':stats,'warnings':len(source_warnings)})
        print('Audited candidate',sid,stats,flush=True)
    if len(all_pages)!=418:raise ValueError('All 418 pages must be audited')
    summary=dict(task='3C.2A-R2',status='candidates-only-not-admitted',manuals=manuals,pages=418,
        severity_counts={level:sum(p['severity']==level for p in all_pages) for level in ('Critical','High','Medium','Low')},page_records=all_pages,warning_records=warnings,
        total_characters=sum(m['characters'] for m in manuals),total_primary_characters=sum(m['primary_representation_characters'] for m in manuals),
        total_dependency_repetition_characters=sum(m['dependency_repetition_characters'] for m in manuals),
        total_chunks={s:sum(m['chunking'][s]['chunks'] for m in manuals) for s in ('legacy','structure-v2')},
        note='Flags are risks, not defect proof. Low/unflagged pages are not certified. Applicability coverage is explicitly partial.')
    dump(output/'automated-audit.json',summary)
    with (output/'inspection-queue.csv').open('w',encoding='utf-8',newline='') as file:
        writer=csv.writer(file);writer.writerow(['source_id','pdf_page','severity','outcome','flags'])
        for p in all_pages:writer.writerow([p['source_id'],p['page'],p['severity'],p['inspection_outcome'],';'.join(f['reason'] for f in p['flags'])])
    dump(output/'warning-propagation-audit.json',warnings)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('manuals','page_records','warning_records')},indent=2))
    return summary


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--corpus',type=Path,required=True);ap.add_argument('--r1',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();audit(args.corpus,args.r1,args.output)
