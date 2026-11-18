"""Curator-only exact-source envelopes and feasibility witnesses.

Uses registered proof labels. NEVER import into the production RAG pipeline.
Three fixed envelope libraries are kept separate. Semantic minimality is not
claimed: bare registered text is a necessary-cost floor, reviewed envelopes
provide constructive upper costs. Every supplied byte is frozen source text.
"""
from __future__ import annotations

import re

from laew.eval.real_world_retrieval import coverage_of, span_present, union
from laew.eval.retrieval_budget_diagnostics import method_specs, score_support, subtract_regions
from laew.eval.scoring_calibration import score_evidence

GRANULARITIES = ('sentence', 'paragraph', 'minimal-span')


def ranges_key(coverage):
    return tuple((sid, tuple(union(ranges))) for sid, ranges in sorted(coverage.items()) if ranges)


def combine(*coverages):
    result = {}
    for coverage in coverages:
        for sid, ranges in coverage.items():
            result.setdefault(sid, []).extend(ranges)
    return {sid: union(ranges) for sid, ranges in result.items()}


def blocks(text):
    """Blank-line units, with complete fenced listings and table runs intact."""
    result, start, in_code, fence = [], 0, False, None
    for match in re.finditer(r'.*(?:\n|$)', text):
        line = match.group()
        if not line:
            continue
        stripped = line.lstrip()
        if stripped.startswith(('```', '~~~')):
            marker = stripped[:3]
            if not in_code:
                in_code, fence = True, marker
            elif marker == fence:
                in_code = False
        if not in_code and not line.strip():
            if text[start:match.start()].strip():
                result.append((start, match.start()))
            start = match.end()
    if text[start:].strip():
        result.append((start, len(text)))
    return result


def expand(text, start, end, granularity):
    if granularity == 'minimal-span':
        return [(start, end)]
    result = []
    for a, z in blocks(text):
        if max(a, start) >= min(z, end):
            continue
        body = text[a:z]
        if granularity == 'paragraph' or body.lstrip().startswith(('|','```','~~~')):
            result.append((a,z))
            continue
        boundaries = [a] + [a+m.end() for m in re.finditer(r'[.!?][ \t\n]+(?=[A-ZÀ-Ž])', body)] + [z]
        result.extend((x,y) for x,y in zip(boundaries,boundaries[1:]) if max(x,start)<min(y,end))
    return union(result)


def header_before(text, start):
    """Keep the exact governing Markdown section heading as a separate passage."""
    found = list(re.finditer(r'^#{1,6} .+$',text[:start], re.MULTILINE))
    return [(found[-1].start(), found[-1].end())] if found else []


def make_scope_rules(atoms, texts, *, require_heading_in_candidates=False):
    """Agent-authored source review, intentionally explicit and label-informed.

    These dependencies are diagnostic assumptions, not learned runtime rules.
    They are deliberately conservative for restoration and operational lists.
    """
    dependencies = {
        'W-enable': ['P03.summarizer_parameter','W-minimal'],
        'P03.summarizer_parameter': ['W-enable','W-minimal'],
        'P03.retention_parameter': ['W-retention'],
        'P03.retention_plan': ['P03.retention_parameter','W-retention'],
        'P03.ten_days': ['P03.retention_parameter','W-retention'],
        'P03.chain': ['B-chain','B-normal-recovery'],
        'P03.wal_history': ['B-normal-recovery'],
        'P03.checksum': ['B-chain'],
        'P03.summary_range': ['B-range'],
        'S04.soft': ['S04-soft'],
        'S04.recovery_time': ['S04-soft'],
        'M-clean-start': ['M-clean-tail'],
        'M-clean-tail': ['M-clean-start'],
        'P02.cool_burn': ['M-clean-start','M-clean-tail'],
        'v1:P02-F3/M-smooth-table:0': ['M-smooth-table'],
        'P02.water_fallback': ['M-smooth-table','M-clean-start','M-clean-tail'],
        'S01-light': ['S01-ui'],
        'S06-file': ['S06-first','S06-model'],
        'S06.rollback': ['S06-old'],
        'v1:S07-F1/S07-tool:0': ['S07-tool','S07-material','S07-wait','S07-feed'],
        'S07-material': ['S07-tool','S07-wait','S07-feed'],
        'S07-wait': ['S07-tool','S07-material','S07-feed'],
        'S07-feed': ['S07-tool','S07-material','S07-wait'],
        'S08-main': ['S14-screw'],
        'S09.menu': ['S09-persist'],
        'S09.command': ['S09-persist'],
        'S10.demand-command': ['S10-en-check','S10.demand-guard'],
        'S10.demand-guard': ['S10-en-check','S10.demand-command'],
        'S11-usb': ['S11-first'],
        'S11-micro': ['S11-correct','S11-power','S11-both'],
        'S11-correct': ['S11-micro','S11-power','S11-both'],
        'S12.session': ['S12-session'],
        'S12.stop_api': ['S12-stop'],
        'R-settings': ['R-version','R-no-file'],
        'S13-old': ['S13-new'],
        'S13-new': ['S13-old'],
    }
    result = {}
    for aid, atom in atoms.items():
        selected = [aid] + dependencies.get(aid, [])
        coverage = {}
        for other in selected:
            item = atoms[other]
            coverage.setdefault(item['source_id'], []).append((item['start'],item['end']))
        # Parameter definitions are mandatory even for a short numeric sentence.
        if aid.startswith('S04'):
            sid=atom['source_id']; start=atoms['S04-soft']['start']
            prefix=texts[sid].rfind('`max_wal_size` (`integer`)',0,start)
            coverage[sid].append((prefix,start))
        # Every table cell retains the original table headers and product row.
        if aid.startswith('S05.') and aid!='v1:S05-F1/S05-indoor:0':
            sid=atom['source_id']; text=texts[sid]
            first=text.rfind('|  |  |',0,atom['start'])
            name_end=text.index('\n',text.index('| Name:',first))
            coverage.setdefault(sid,[]).append((first,name_end))
        # Commands embedded in console output retain the complete listing.
        if aid.startswith('v1:S02') or aid=='S10.demand-command':
            sid=atom['source_id']; text=texts[sid]
            fence=text.rfind('```',0,atom['start'])
            closing=text.find('```',atom['end'])
            coverage[sid].append((fence,closing+3))
        if aid.startswith('S03-'):
            sid=atom['source_id']; text=texts[sid]
            closing=text.find('```',atom['end'])
            if closing>=0:
                closing=text.find('```',closing+3)
                coverage[sid].append((atom['start'],closing+3))
        # Step numbers are never presented as a newly synthesized procedure.
        # Keep download + media + completion for firmware installation lists.
        if aid in ('S06-file','S11-usb'):
            sid=atom['source_id']; text=texts[sid]
            first=text.rfind('1. ',0,atom['start'])
            end=text.index('\n\n[Visual information unavailable',atom['end'])
            coverage[sid].append((first,end))
        if aid in ('S07-tool','v1:S07-F1/S07-tool:0','S07-material','S07-wait','S07-feed'):
            sid=atom['source_id']; text=texts[sid]
            a=text.rfind('Bevor Sie das Filament einlegen',0,atoms['S07-tool']['start'])
            z=text.find('\n\n',atoms['S07-feed']['end']+1)
            # End of step 5 (purge confirmation) is part of the same loading flow.
            coverage[sid].append((a,z))
        if aid in ('S11-micro','S11-correct'):
            sid=atom['source_id']; text=texts[sid]
            a=atoms['S11-micro']['start']; z=text.index('\n\nIf the flashing process fails',a)
            coverage[sid].append((a,z))
        if aid in ('S12.session','S12-session'):
            sid=atom['source_id']; text=texts[sid]
            a=text.rfind('  1. Ensure that WAL archiving',0,atom['start'])
            coverage[sid].append((a,atoms['S12-session']['end']))
        if aid in ('S12-stop','S12.stop_api'):
            sid=atom['source_id']; text=texts[sid]
            a=text.rfind('  4. In the same connection',0,atom['start'])
            # Retain primary/standby WAL-switch conditions with stop metadata.
            coverage[sid].append((a,atoms['S12-stop']['end']))
        # Strict-v1 additionally required section-heading bodies in candidates.
        # The main library binds scope through exact source/revision attribution.
        # Do not invent retrieval gaps for a heading already supplied as ordinary
        # section metadata. Full parameter definitions remain mandatory BODY.
        if require_heading_in_candidates:
            for sid, ranges in list(coverage.items()):
                coverage[sid].extend(header_before(texts[sid],min(a for a,z in ranges)))
        if any(a<0 or a>=z or z>len(texts[sid]) for sid,ranges in coverage.items() for a,z in ranges):
            raise ValueError('Invalid source scope rule: '+aid)
        result[aid] = dict(ranges={sid:union(ranges) for sid,ranges in coverage.items()},
            atom_dependencies=selected, reviewer_origin='agent',
            rationale='Exact local section/product/parameter scope; full applicable condition/warning or ordered flow; no independent domain validation')
    return result


def render(coverage, texts, units, *, body_only=False):
    """One version/hash attribution per source, offsets per separated passage.

    Disjoint passages stay visibly separated and in original source order.
    Unicode offsets address the immutable normalized snapshot, not PDF bytes.
    """
    source_parts=[]; body_chars=0; fragments=0
    for sid,ranges in sorted(coverage.items()):
        passages=[]
        for a,z in union(ranges):
            exact=texts[sid][a:z]
            body_chars+=len(exact);fragments+=1
            passages.append(exact if body_only else f'[chars {a}:{z}]\n'+exact)
        if not passages:
            continue
        u=units[sid]
        attribution='' if body_only else f'[{sid} | revision={u["revision"]} | sha256={u["normalized_sha256"]}]\n'
        source_parts.append(attribution + ('\n\n[separate source passage]\n\n' if not body_only else '').join(passages))
    context=('\n\n---\n\n' if not body_only else '').join(source_parts)
    return dict(context=context,chars=len(context),tokens=(len(context)+3)//4,
                body_chars=body_chars,attribution_and_separator_chars=len(context)-body_chars,
                fragments=fragments,sources=len(source_parts))


def solve(family, atoms, texts, units, candidates, regions, rules, granularity, *, floor=False):
    """Exhaust every union of admitted proof packets, with no heuristic pruning.

    Exact ONLY within this finite packet library and renderer, not over every
    semantically defensible excerpt. Unregistered equivalence stays unresolved.
    """
    available=subtract_regions(coverage_of(candidates),regions)
    packets={}; rejected=[]; proof_envelopes={}
    for requirement in family['requirements']:
        for proof in requirement['proofs']:
            coverage={}
            for aid in proof:
                atom=atoms[aid]
                base={atom['source_id']:[(atom['start'],atom['end'])]} if floor else rules[aid]['ranges']
                expanded={sid:union([r for a,z in ranges for r in ([(a,z)] if floor else expand(texts[sid],a,z,granularity))])
                          for sid,ranges in base.items()}
                coverage=combine(coverage,expanded)
            valid=all(span_present(dict(source_id=sid,start=a,end=z),available,texts)
                      for sid,ranges in coverage.items() for a,z in ranges)
            proof_envelopes.setdefault(requirement['id'],[]).append(coverage)
            if valid:
                packets[ranges_key(coverage)]=coverage
            else:
                rejected.append(dict(requirement=requirement['id'],proof=proof,
                                     reason='Mandatory source scope not wholly inside eligible unrestricted candidate ranges',
                                     required_ranges=coverage))
    # All unions are kept; source-grouped attribution makes additive-cost
    # pruning by proof mask invalid. This avoids that optimization shortcut.
    states={():{}}
    for packet in packets.values():
        for previous in list(states.values()):
            combined=combine(previous,packet)
            states[ranges_key(combined)]=combined
    specs=method_specs(family)
    best=None;minimum=None;incoherent=0
    for coverage in states.values():
        supported={r['id']: bool(r.get('contextual')) or any(
            all(span_present(atoms[aid],coverage,texts) for aid in proof) for proof in r['proofs'])
            for r in family['requirements']}
        # A broad packet can incidentally cover another registered proof. Raw
        # span presence must never bypass that proof's declared local closure.
        # Reject such a union rather than calling its partial procedure safe.
        if not floor and any(supported[r['id']] and not r.get('contextual') and not any(
            all(span_present(dict(source_id=sid,start=a,end=z),coverage,texts)
                for sid,ranges in envelope.items() for a,z in ranges)
            for envelope in proof_envelopes[r['id']]) for r in family['requirements']):
            incoherent+=1
            continue
        score=score_support(supported,specs)
        rendering=render(coverage,texts,units,body_only=floor)
        record=dict(coverage=coverage,support=supported,score=list(map(float,score[:3]))+[score[3]],rendering=rendering)
        if score[0] and (minimum is None or rendering['chars']<minimum['rendering']['chars']):
            minimum=record
        objective=(*score[:3],-rendering['chars'])
        if rendering['chars']<=4000 and (best is None or objective>best[0]):
            best=(objective,record)
    witness=best[1]
    scored=score_evidence(family,atoms,witness['coverage'],texts)
    if family['positive_recall_applicable']:
        if scored['positive_recall']!=witness['score'][1] or bool(scored['complete'])!=bool(witness['score'][0]):
            raise ValueError('Oracle witness differs from frozen scorer')
    return dict(complete=bool(witness['score'][0]),coverage=witness['score'][1],
                witness=witness,minimum_complete=minimum,
                min_complete_tokens=minimum['rendering']['tokens'] if minimum else None,
                states=len(states),packets=len(packets),rejected=rejected,
                incoherent_unions_rejected=incoherent,
                optimization='exact within finite admitted packets; semantic/global minimality NOT proved',
                status='necessary proof-only body-cost floor; NOT coherent evidence' if floor else 'agent-reviewed source-envelope witness; independent domain judgment pending')
