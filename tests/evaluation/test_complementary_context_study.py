"""Integrity, offline execution and optional immutable-artifact acceptance."""
import copy
import os
from pathlib import Path
import socket

import pytest

from laew.eval import complementary_context_study as study
from laew.eval import complementary_context_selection as selector
from laew.rag.evidence_selection import SelectionConfig


def test_manifest_rejects_wrong_anchor_and_modified_member(tmp_path):
    (tmp_path / 'source.txt').write_text('Original.', encoding='utf-8')
    study.write(tmp_path / 'manifest.json', dict(files=[dict(path='source.txt', sha256=study.sha(tmp_path/'source.txt'))]))
    anchor = study.sha(tmp_path / 'manifest.json')
    assert study.verify_manifest(tmp_path, 'manifest.json', anchor)['members'] == 1
    with pytest.raises(ValueError, match='Manifest changed'):
        study.verify_manifest(tmp_path, 'manifest.json', '0' * 64)
    (tmp_path / 'source.txt').write_text('Changed.', encoding='utf-8')
    with pytest.raises(ValueError, match='member changed'):
        study.verify_manifest(tmp_path, 'manifest.json', anchor)


def test_manifest_cannot_escape_root(tmp_path):
    nested = tmp_path / 'nested'
    nested.mkdir()
    (tmp_path / 'outside').write_text('Private.', encoding='utf-8')
    study.write(nested / 'manifest.json', dict(files=[dict(path='../outside', sha256=study.sha(tmp_path/'outside'))]))
    with pytest.raises(ValueError, match='member changed'):
        study.verify_manifest(nested, 'manifest.json', study.sha(nested/'manifest.json'))


def test_offline_guard_blocks_before_connecting():
    with study.offline(), socket.socket() as connection:
        with pytest.raises(RuntimeError, match='Network forbidden'):
            connection.connect(('127.0.0.1', 9))


@pytest.fixture(scope='module')
def frozen():
    root = os.environ.get('LAEW_COMPLEMENTARY_STUDY_ROOT')
    if not root:
        pytest.skip('Set LAEW_COMPLEMENTARY_STUDY_ROOT for the frozen 60-question acceptance checks')
    root = Path(root)
    config = study.read(root / 'study-config.json')
    # The collection path must work with deliberately nonexistent rubric paths.
    selection_config = copy.deepcopy(config)
    selection_config['rubric'] = str(root / 'does-not-exist-rubric')
    selection_config['datasets'] = []
    with study.offline():
        data = study.load_inputs(selection_config, scoring=False)
    return root, config, data


def test_all_native_candidates_reproduce_historical_contexts_without_labels(frozen):
    root, config, data = frozen
    assert len(data['traces']) == 180 and len(data['questions']) == 60
    assert 'rubric' not in data and 'atoms' not in data and 'families' not in data


def test_all_versions_replay_exactly_and_v2_preserves_baseline_bodies(frozen):
    root, config, data = frozen
    originals = {(r['question_id'], r['arm']): r for r in data['traces']}
    for version in ('v1', 'v2'):
        delivery = root / f'{version}-all-delivery'
        study.verify_manifest(delivery, 'integrity.json', study.sha(delivery / 'integrity.json'))
        traces = study.read(delivery / 'selection-traces.json')
        assert len(traces) == 120
        for trace in traces:
            baseline = originals[trace['question_id'], trace['baseline_arm']]
            pool = data['pools'][trace['question_id'], trace['baseline_arm']]
            query = data['questions'][trace['question_id']]['text']
            with study.offline():
                results, enclosing = selector.select_complementary_scopes({'global': pool},
                    SelectionConfig(policy='ranked_fill', budget=1000), query,
                    version=f'complementary-pack-{version}')
            result = results['global']
            assert result.context == trace['context'] and enclosing == trace['enclosing_context']
            if version == 'v2':
                delivered = {c.chunk_id: c.text for c, _ in result.chunks}
                assert all(delivered[c['id']] == c['text'] for c in baseline['selected'])
        pilot = study.read(root / f'{version}-pilot-delivery/selection-traces.json')
        by = {t['question_id'] + t['arm']: t for t in traces}
        assert all(t['context'] == by[t['question_id'] + t['arm']]['context'] for t in pilot)


def test_v2_fixed_branch_scores_have_no_requirement_or_warning_losses(frozen):
    root, _, _ = frozen
    scores = root / 'v2-all-score'
    study.verify_manifest(scores, 'integrity.json', study.sha(scores/'integrity.json'))
    paired = study.read(scores / 'paired.json')
    assert len(paired) == 120
    assert all(not row['requirement_losses'] and not row['critical_losses'] and not row['condition_losses']
               for row in paired)
