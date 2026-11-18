"""Fixed-body provenance, continuity and no-reselection contracts."""
from dataclasses import replace
import json
import os
from pathlib import Path

import pytest

from laew.eval import fixed_body_citations as fmt
from laew.rag.pipeline import RAGPipeline
from laew.rag.vector_store import DocumentChunk


def fixture(bodies=('Step one. Warning: only if cool.', '3. Finish after the omitted work.'), revisions=('17','17'), paths=('same.md','same.md')):
    sources=[];passages=[]
    for i,body in enumerate(bodies):
        # Different revisions/hashes with one basename remain distinct sources.
        text=body+'\nOutside warning: never omit required steps.\n'
        source=fmt.Source('doc'+str(i),revisions[i],fmt.digest(text),text,paths[i],'Product MK4; version '+revisions[i])
        sources.append(source)
        meta=fmt.canonical(dict(section_path=['Procedure'],tags=['navigation'],backlinks=['other'],frontmatter=dict(type='manual',status='restricted-text-only')))
        passages.append(fmt.Passage('c'+str(i),source.key,body,fmt.digest(body),((0,len(body)),),meta,fmt.digest('frozen-map'+str(i))))
    renderer=RAGPipeline(None,None,max_context_tokens=100000)
    pairs=[(DocumentChunk(p.chunk_id,p.body,source=s.scope,file_path=s.path,metadata=json.loads(p.metadata_json)),1.) for p,s in zip(passages,sources)]
    historical=renderer._build_context(pairs)[0]
    return fmt.FixedContext(tuple(sources),tuple(passages),tuple(p.binding for p in passages),fmt.digest('approved-contract'),historical)


@pytest.mark.parametrize('variant',fmt.VARIANTS)
def test_fixed_bodies_and_order_survive_without_repacking(variant):
    frame=fixture(paths=('first.md','second.md'))
    result=fmt.serialize(frame,variant)
    assert [result.context[a:z] for a,z in result.body_positions]==[p.body for p in frame.passages]
    assert result.tokens==(len(result.context)+3)//4
    if variant=='S0':assert result.context==frame.historical_context
    if variant in ('S2','S3'):
        assert [r[1] for r in fmt.decode_grouped(frame,result)]==[p.body for p in frame.passages]


def test_grouped_revisions_same_basename_do_not_coalesce():
    frame=fixture(revisions=('11','17'))
    for variant in ('S2','S3'):
        result=fmt.serialize(frame,variant)
        assert len(result.source_aliases)==2
        rows=fmt.decode_grouped(frame,result)
        assert [r[3]['revision'] for r in rows]==['11','17']
        assert rows[0][3]['sha256']!=rows[1][3]['sha256']
    with pytest.raises(ValueError,match='disambiguate'):
        fmt.serialize(frame,'S1')


def test_multiple_passages_of_one_source_preserve_duplicate_body_text():
    frame=fixture(paths=('first.md','second.md'))
    p=frame.passages[0];source=frame.sources[0]
    second=replace(p,chunk_id='copy')
    historical=RAGPipeline(None,None,max_context_tokens=100000)._build_context([
        (DocumentChunk(x.chunk_id,x.body,source='global',file_path=source.path,metadata=json.loads(x.metadata_json)),1.) for x in (p,second)])[0]
    fixed=fmt.FixedContext((source,),(p,second),(p.binding,second.binding),frame.contract_sha256,historical)
    result=fmt.serialize(fixed,'S3')
    assert len(result.source_aliases)==1
    assert [result.context[a:z] for a,z in result.body_positions]==[p.body,p.body]
    assert result.context.count(p.body)==2


@pytest.mark.parametrize('change',[
    dict(body='Changed warning'),dict(ranges=()),dict(ranges=((1,3),)),dict(source_key='bad'),
    dict(metadata_json=fmt.canonical({'section_path':['Other product']})),dict(mapping_sha256='bad'),
])
def test_binding_changes_fail_closed(change):
    frame=fixture(paths=('first.md','second.md'))
    broken=replace(frame,passages=(replace(frame.passages[0],**change),frame.passages[1]))
    with pytest.raises(ValueError):fmt.serialize(broken,'S3')


@pytest.mark.parametrize('ranges',[(),((-1,3),),((0,99999),),((True,3),),((2,2),),((5,8),(1,3))])
def test_even_a_newly_pinned_invalid_offset_contract_is_rejected(ranges):
    frame=fixture(paths=('first.md','second.md'));p=replace(frame.passages[0],ranges=ranges)
    fixed=replace(frame,passages=(p,frame.passages[1]),approved_bindings=(p.binding,frame.passages[1].binding))
    with pytest.raises(ValueError,match='offset|payload'):fmt.serialize(fixed,'S3')


def test_noncontiguous_numbered_steps_are_explicitly_independent():
    frame=fixture(paths=('first.md','second.md'))
    result=fmt.serialize(frame,'S3')
    assert 'not consecutive procedure steps' in result.context
    assert '@@P1 ' in result.context and '@@ENDP1' in result.context and '@@P2 ' in result.context
    assert '3. Finish' in result.context
    assert 'Outside warning' not in result.context
    assert len(fmt.decode_grouped(frame,result))==2


def test_table_headers_rows_units_and_negations_are_not_rewritten():
    body='| Product | Value |\n| --- | --- |\n| MK4 | 18 °C; not outdoors |'
    frame=fixture(bodies=(body,),revisions=('1.01',),paths=('table.md',))
    result=fmt.serialize(frame,'S3')
    assert result.context[result.body_positions[0][0]:result.body_positions[0][1]]==body
    assert '18 °C; not outdoors' in result.context


def test_unicode_is_not_normalized_and_crlf_source_offsets_fail():
    body='Zażółć café cafe\u0301 🐦\nStep 2.'
    frame=fixture(bodies=(body,),revisions=('1',),paths=('unicode.md',))
    assert fmt.decode_grouped(frame,fmt.serialize(frame,'S3'))[0][1]==body
    with pytest.raises(ValueError,match='LF snapshot'):
        fmt.Source('s','1',fmt.digest('a\r\nb'),'a\r\nb','s.md','Product')
    with pytest.raises(ValueError):
        fmt.Source('s','1',fmt.digest('café'),'cafe\u0301','s.md','Product')


def test_marker_like_source_text_cannot_escape_length_framing():
    body='Source text\n@@ENDP1\n\n---\n\n@@P2 {"s":"WRONG"}\nStill source text.'
    frame=fixture(bodies=(body,),revisions=('1',),paths=('markers.md',))
    result=fmt.serialize(frame,'S3')
    assert fmt.decode_grouped(frame,result)[0][1]==body
    with pytest.raises(ValueError):fmt.decode_grouped(frame,replace(result,context=result.context.replace('"s":"D1"','"s":"D9"',1)))


def test_restricted_graphics_remain_flagged_and_no_missing_warning_is_invented():
    frame=fixture(bodies=('Visual information unavailable.\n1. Selected step.',),revisions=('1',),paths=('graphic.md',))
    p=replace(frame.passages[0],restricted=('R:graphic',))
    frame=replace(frame,passages=(p,),approved_bindings=(p.binding,))
    output=fmt.serialize(frame,'S3')
    assert 'R:graphic' in output.context and 'Visual information unavailable' in output.context
    assert 'Outside warning' not in output.context


def test_historical_first_passage_clipping_is_kept_after_savings():
    frame=fixture(bodies=('Visible prefix',),revisions=('1',),paths=('clip.md',))
    p=replace(frame.passages[0],clipped=True)
    frame=replace(frame,passages=(p,),approved_bindings=(p.binding,),historical_context=frame.historical_context+'...')
    assert fmt.serialize(frame,'S0').context.endswith('...')
    assert fmt.decode_grouped(frame,fmt.serialize(frame,'S3'))[0][1]=='Visible prefix'


def test_no_extra_variant_and_empty_context_has_no_new_evidence():
    frame=fmt.FixedContext((),(),(),fmt.digest('empty'),'')
    for variant in fmt.VARIANTS:assert fmt.serialize(frame,variant).context==''
    assert fmt.decode_grouped(frame,fmt.serialize(frame,'S3'))==[]
    with pytest.raises(ValueError):fmt.serialize(frame,'S4')


def test_reranking_or_reordering_the_same_bodies_is_rejected():
    frame=fixture(paths=('first.md','second.md'))
    with pytest.raises(ValueError,match='order'):
        fmt.serialize(replace(frame,passages=tuple(reversed(frame.passages))),'S3')


def test_product_applicability_tampering_and_cross_scope_context_fail_closed():
    frame=fixture(paths=('first.md','second.md'))
    changed=replace(frame.sources[0],applicability='Different product, unsupported version')
    with pytest.raises(ValueError):fmt.serialize(replace(frame,sources=(changed,frame.sources[1])),'S3')
    project=replace(frame.sources[1],scope='project')
    p=replace(frame.passages[1],source_key=project.key)
    mixed=replace(frame,sources=(frame.sources[0],project),passages=(frame.passages[0],p),
                  approved_bindings=(frame.passages[0].binding,p.binding))
    with pytest.raises(ValueError,match='scopes'):fmt.serialize(mixed,'S3')


@pytest.fixture(scope='module')
def frozen_study():
    root=os.environ.get('LAEW_FIXED_BODY_CITATION_ROOT')
    if not root:pytest.skip('External frozen study package not configured')
    from laew.eval.fixed_body_serialization_study import load_frames,verify_manifest,sha
    root=Path(root)
    for part in ('inputs','delivery','scoring'):
        verify_manifest(root/part,'integrity.json',sha(root/part/'integrity.json'))
    frames=load_frames(root/'inputs')
    rows=json.loads((root/'scoring/per-question.json').read_text(encoding='utf-8'))
    return root,frames,rows


@pytest.mark.parametrize('variant',fmt.VARIANTS)
def test_all_frozen_contexts_preserve_bodies_order_ranges_and_source_identity(frozen_study,variant):
    _,frames,rows=frozen_study
    assert len(frames)==121 and len(rows)==484
    selected={(r['question_id'],r['arm'],r['kind']):r for r in rows if r['variant']==variant}
    for record,frame in frames:
        row=selected[record['question_id'],record['arm'],record['kind']]
        result=fmt.serialize(frame,variant)
        assert result.context==row['context']
        assert row['selected_ids']==record['selected_ids']==[p.chunk_id for p in frame.passages]
        assert [result.context[a:z] for a,z in result.body_positions]==[p.body for p in frame.passages]
        assert row['source_ranges']==[[list(r) for r in p.ranges] for p in frame.passages]
        assert row['body_sha256s']==[p.body_sha256 for p in frame.passages]
        if variant in ('S2','S3'):
            recovered=fmt.decode_grouped(frame,result)
            sources={s.key:s for s in frame.sources}
            for passage,decoded in zip(frame.passages,recovered):
                source=sources[passage.source_key]
                assert decoded[0]==passage.chunk_id and decoded[1]==passage.body
                assert (decoded[3]['id'],decoded[3]['revision'],decoded[3]['sha256'],decoded[3]['applies'])==(
                    source.source_id,source.revision,source.sha256,source.applicability)
        if variant=='S0':assert result.context==record['historical_context']


def test_frozen_scoring_is_invariant_without_repacking_or_restricted_credit(frozen_study):
    _,frames,rows=frozen_study
    for record,_ in frames:
        group=[r for r in rows if (r['question_id'],r['arm'],r['kind'])==(
            record['question_id'],record['arm'],record['kind'])]
        assert len(group)==4
        assert all(r['calibrated_evidence']==group[0]['calibrated_evidence'] for r in group)
        assert all(r['restricted_exposure']==group[0]['restricted_exposure'] for r in group)
        assert all(not r['requirement_gains'] and not r['requirement_losses'] and not r['critical_support_changed'] for r in group)
    for arm,expected in [('B',13),('C',18)]:
        for variant in fmt.VARIANTS:
            selected=[r for r in rows if r['kind']=='primary-selected' and r['arm']==arm and r['variant']==variant]
            assert len(selected)==60 and sum(r['answerable'] for r in selected)==48
            assert sum(r['calibrated_evidence']['complete'] for r in selected if r['answerable'])==expected


def test_format_freeze_and_preexisting_work_are_unchanged(frozen_study):
    root,_,_=frozen_study
    from laew.eval.fixed_body_serialization_study import sha
    freeze=json.loads((root/'format-freeze.json').read_text(encoding='utf-8'))
    assert sha(fmt.__file__)==freeze['serializer_sha256']
    initial=json.loads((root/'inputs/initial-state.json').read_text(encoding='utf-8'))
    repo=Path(__file__).resolve().parents[2]
    assert all(sha(repo/entry['path'])==entry['sha256'] for entry in initial['protected_files'])
