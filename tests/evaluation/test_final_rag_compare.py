"""Contract checks for the approved batching and post-collection diagnostics."""
import pytest

from laew.eval import final_rag_embedding_job as job
from laew.eval.final_rag_compare import target_conflicts
from laew.eval.final_rag_preflight import digest


def _input(text, arm):
    return dict(text=text, sha256=digest(text), arms=[arm])


def test_batches_keep_arm_order_and_use_utf8_length(monkeypatch):
    monkeypatch.setattr(job, 'COUNTS', {'adaptive': 2, 'contextual': 1})
    monkeypatch.setattr(job, 'REQUESTS', {'adaptive': 2, 'contextual': 1})
    first = _input('ę' * 1200, 'adaptive')
    second = _input('ó' * 1200, 'adaptive')
    last = _input('small', 'contextual')
    assert list(job.schedule([last, first, second])) == [
        ('adaptive', [first]), ('adaptive', [second]), ('contextual', [last])]


def test_modified_input_hash_is_rejected_before_scheduling(monkeypatch):
    monkeypatch.setattr(job, 'COUNTS', {'adaptive': 1})
    row = _input('original', 'adaptive')
    row['text'] = 'modified'
    with pytest.raises(ValueError, match='Unapproved input'):
        list(job.schedule([row]))


def test_explicit_target_conflicts_leave_cross_version_and_accessory_scope_open():
    manuals = ['prusa-mini-pl', 'prusa-xl-de', 'prusa-mmu3-en']
    assert target_conflicts('P02', manuals) == ['prusa-xl-de']
    postgres = ['postgresql-11-continuous-archiving', 'postgresql-12-release-12']
    assert target_conflicts('S04', postgres) == ['postgresql-11-continuous-archiving']
    assert target_conflicts('S12', postgres) == []
