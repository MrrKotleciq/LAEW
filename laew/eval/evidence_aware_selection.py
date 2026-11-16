"""Query-associated lexical role coverage, evaluation only; no runtime callers.

Roles and filename applicability are weak cues, never semantic certification.
Inputs contain only a query, native candidates, ordinary metadata and cosine.
"""
from __future__ import annotations

from dataclasses import replace
import math
import re
import unicodedata

from laew.rag.evidence_selection import (
    Selection, SelectionConfig, SEPARATOR, _allocate_scopes, select,
)
from laew.rag.pipeline import RAGPipeline


VERSION='query-role-cover-v1-r1'
VERSIONS=(VERSION,)
SETTINGS=dict(max_candidates=10,window_chars=320,window_stride=160,
    token_weight=.45,role_weight=.30,identity_weight=.15,relevance_weight=.10,
    redundancy_weight=.06,cost_weight=.04,improvement_margin=.025,
    conflict_multiplier=.35,protected_roles=['dependency','constraint'],
    guard='verbatim-query-associated-risk-clauses')

TOPICS={
    'backup':r'backup|kopi\w*|sicherung\w*',
    'recovery':r'recover\w*|restor\w*|odtw\w*|przywr\w*|wiederherstell\w*',
    'configuration':r'config\w*|setting\w*|paramet\w*|konfigur\w*|ustaw\w*|einstell\w*',
    'firmware':r'firmware|oprogramow\w*',
    'loading':r'load\w*|feed\w*|filament\w*|lad\w*|zalad\w*|wprowadz\w*',
    'maintenance':r'maint\w*|clean\w*|tube\w*|czysz\w*|rurk\w*|konserw\w*|reinig\w*|wart\w*|schlauch\w*',
    'publication':r'push\w*|publish\w*|publication\w*|publik\w*|wysyl\w*|veroffentlich\w*',
    'initialization':r'init\w*|clone\w*|klon\w*|zainic\w*',
    'environment':r'environ\w*|power\w*|mains\w*|temperatur\w*|humid\w*|zasil\w*|wilgot\w*|umgeb\w*|spannung\w*',
    'defaults':r'default\w*|domysl\w*|standard\w*',
}
ROLES={
    'configuration':r'config\w*|setting\w*|paramet\w*|default\w*|ustaw\w*|konfigur\w*|einstell\w*|standard\w*|domysl\w*',
    'procedure':r'step\w*|start\w*|stop\w*|run\w*|use|load\w*|connect\w*|flash\w*|init\w*|uruch\w*|uzy\w*|podlacz\w*|lade\w*|ausfuhr\w*|verwenden\w*',
    'dependency':r'before|prior|depend\w*|prerequis\w*|requir\w*|must|session\w*|manifest\w*|przed|wymag\w*|sesj\w*|nalezy|musi\w*|bevor|vorher|erforder\w*|muss\w*',
    'constraint':r'warning|caution|never|not|only|unless|if|except\w*|nie|tylko|jesli|jezeli|ostrzez\w*|nicht|niemals|nur|wenn|achtung|vorsicht',
    'retention':r'retain\w*|retention|keep|history|chain|ancestor\w*|zachow\w*|retenc\w*|histor\w*|lancuch\w*|aufbewahr\w*|behalt\w*',
    'maintenance':r'clean\w*|cool\w*|wear\w*|replac\w*|inspect\w*|czysz\w*|chlod\w*|zuzyc\w*|wymian\w*|reinig\w*|kuhl\w*|verschleiss\w*|austausch\w*',
}
STOP=set(('a an and are as at be been but by can do does for from had has have how i if in into is it its of on or our should than that the their then there these they this to use was we were what when where which while will with would you your '
          'a aby albo ale bez bo by byl byla co czy dla do gdy i jak jaka jakie jaki jest mam ma maja mi na nad nie o od oraz po pod przed przy sa sie tak to ten tez tym w we z za ze '
          'aber als am an auch auf aus bei bin bis das dem den der des die durch ein eine einer einem einen fur habe hat ich im in ist mit nach nicht noch nur oder sein sie sind soll um und von vor war was welche werden wie wir wo zu zum zur').split())


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKD',text.casefold()) if not unicodedata.combining(c)).replace('ł','l').replace('ß','ss')


def terms(text):
    result=set()
    for value in re.findall(r'[a-z0-9_+]+',normalized(text)):
        if value in STOP or len(value)<2 or value.isdigit():
            continue
        result.add(value if '_' in value or any(c.isdigit() for c in value) else value[:6])
        if '_' in value:
            result.update(part[:6] for part in value.split('_') if len(part)>2 and part not in STOP)
    return result


def hits(pattern,text):
    return bool(re.search(r'\b(?:'+pattern+r')\b',text))


def anchor_only(text):
    return bool(re.fullmatch(r'\s*(?:<a\s+id="[^"]+"\s*></a>\s*)+',text))


def _section(chunk):
    return ' '.join(chunk.metadata.get('section_path') or [chunk.metadata.get('section_header') or ''])


def profile_candidates(query,candidates):
    """Explain weak query features without opening any additional source."""
    q=normalized(query)
    query_terms=terms(query)
    query_topics={name for name,pattern in TOPICS.items() if hits(pattern,q)}
    query_products=set(re.findall(r'\b[a-z]+\d+[a-z0-9+]*\b',q))
    query_numbers=set(re.findall(r'(?<!\w)\d+(?:\.\d+)*(?!\w)',q))
    query_versions={}
    source_versions=[]
    for c in candidates:
        basename=c.chunk.file_path.replace('\\','/').rsplit('/',1)[-1].casefold()
        match=re.match(r'([a-z][a-z0-9]*)[-_]v?(\d+(?:\.\d+)*)(?:[-_.]|$)',basename)
        pair=match.groups() if match else None
        source_versions.append(pair)
        if pair and terms(pair[0]) & query_terms and pair[1] in query_numbers:
            query_versions.setdefault(pair[0],set()).add(pair[1])
    docs=[terms(c.chunk.text+' '+_section(c.chunk)+' '+c.chunk.file_path) if not anchor_only(c.chunk.text) else set() for c in candidates]
    weights={t:1+math.log((len(candidates)+1)/(1+sum(t in d for d in docs))) for t in query_terms}
    requested_ids={'product:'+p for p in query_products}
    requested_ids.update('version:'+prefix+':'+v for prefix,values in query_versions.items() for v in values)
    profiles=[]
    for c,doc,version in zip(candidates,docs,source_versions):
        anchor=anchor_only(c.chunk.text)
        filename=normalized(c.chunk.file_path)
        products=set(re.findall(r'\b[a-z]+\d+[a-z0-9+]*\b',filename.replace('-',' ')))
        identity={'product:'+p for p in products & query_products}
        conflict=bool(query_products and products and not query_products & products)
        if version and version[0] in query_versions:
            if version[1] in query_versions[version[0]]:
                identity.add('version:'+version[0]+':'+version[1])
            else:
                conflict=True
        query_features=query_terms & doc if not anchor else set()
        role_features=set()
        body=normalized(c.chunk.text)
        if not anchor:
            for start in range(0,len(body),SETTINGS['window_stride']):
                window=body[start:start+SETTINGS['window_chars']]
                anchors={'topic:'+topic for topic in query_topics if hits(TOPICS[topic],window)}
                anchors.update('term:'+t for t in terms(window) & query_terms)
                for role,pattern in ROLES.items():
                    if hits(pattern,window):
                        role_features.update(a+'|'+role for a in anchors)
        alignment=sum(weights[t] for t in query_features)/max(1,sum(weights.values()))
        association=bool(role_features)
        aligned=min(1,alignment+.25*bool(query_topics & {name for name,pattern in TOPICS.items() if hits(pattern,body)})+.25*bool(identity))
        profiles.append(dict(id=c.chunk.chunk_id,query_features=sorted(query_features),roles=sorted(role_features),
            identities=sorted(identity) if not anchor else [],identity_conflict=conflict,anchor_only=anchor,
            token_alignment=alignment,aligned_relevance=aligned*c.cosine*(SETTINGS['conflict_multiplier'] if conflict else 1),
            body_terms=sorted(terms(c.chunk.text)),query_associated=association))
    return dict(query_terms=sorted(query_terms),query_topics=sorted(query_topics),requested_identities=sorted(requested_ids),
                token_weights=weights,candidates=profiles)


def _feature_score(indices,profiles,key,weights=None):
    maxima={}
    for i in indices:
        p=profiles[i]
        multiplier=SETTINGS['conflict_multiplier'] if p['identity_conflict'] else 1
        for value in p[key]:
            maxima[value]=max(maxima.get(value,0),p['cosine']*multiplier)
    universe=set().union(*(set(p[key]) for p in profiles)) if profiles else set()
    if weights is None:
        return sum(maxima.values())/max(1,len(universe))
    return sum(weights[t]*v for t,v in maxima.items())/max(1,sum(weights.values()))


def risk_clauses(text):
    """Conservative surface spans; no inferred technical obligations."""
    result=[]
    for match in re.finditer(r'[^.!?\n]+(?:[.!?]|$)',text):
        clause=match.group().strip()
        value=normalized(clause)
        technical=bool(re.search(r'\b[a-z][a-z0-9]*_\w+|--[a-z]|\d+(?:[.,]\d+)?\s*(?:%|°[cfk]?|\b[a-z]{1,5}\b)',value))
        if len(clause)>=16 and (technical or any(hits(ROLES[role],value) for role in SETTINGS['protected_roles'])):
            result.append(clause)
    return sorted(set(result))


def _pack(candidates,scope,config,query,version):
    if version not in VERSIONS or config.policy!='ranked_fill':
        raise ValueError('Unknown version or baseline policy')
    if len(candidates)>SETTINGS['max_candidates'] or len(query)>100_000:
        raise ValueError('Native K10/query bound exceeded')
    if any(c.relevance is not None for c in candidates):
        raise ValueError('Original cosine required')
    baseline=select(candidates,scope,config)
    eligible=sorted([c for c in candidates if c.cosine>=config.threshold and c.chunk.text],key=lambda c:-c.cosine)
    if not eligible or not baseline.chunks:
        return baseline
    original={c.chunk.chunk_id:c for c in eligible}
    def fallback(reason):
        return Selection(baseline.context,baseline.chunks,baseline.estimated_tokens,
            [dict(id=c.chunk.chunk_id,reason='baseline_fallback',fallback=reason) for c in candidates])
    if any(chunk.text!=original[chunk.chunk_id].chunk.text for chunk,_ in baseline.chunks):
        return fallback('baseline_clipped')
    profile=profile_candidates(query,eligible)
    profiles=profile['candidates']
    for p,c in zip(profiles,eligible):
        p['cosine']=c.cosine
    matched=set().union(*(set(p['query_features']) for p in profiles))
    if len(matched)<2 and not any(p['roles'] or p['identities'] for p in profiles):
        return fallback('insufficient_query_alignment')
    full=RAGPipeline(None,None,max_context_tokens=config.max_total_chars)
    costs=[len(full._build_context([(c.chunk,c.cosine)])[0]) for c in eligible]
    baseline_ids={c.chunk_id for c,_ in baseline.chunks}
    baseline_mask=sum(1<<i for i,c in enumerate(eligible) if c.chunk.chunk_id in baseline_ids)
    id_guard=set().union(*(set(p['identities']) for i,p in enumerate(profiles) if baseline_mask & (1<<i)))
    required_clauses=set()
    for i,(p,c) in enumerate(zip(profiles,eligible)):
        associated=bool(p['roles'] or len(p['query_features'])>=2 or p['identities'])
        if baseline_mask & (1<<i) and associated and not p['identity_conflict']:
            required_clauses.update((c.chunk.source,c.chunk.file_path,clause) for clause in risk_clauses(c.chunk.text))
    guards=[{(scope,path,clause) for scope,path,clause in required_clauses
             if c.chunk.source==scope and c.chunk.file_path==path and clause in c.chunk.text} for c in eligible]
    role_guard=required_clauses
    body_sets=[set(p['body_terms']) for p in profiles]
    redundancy={}
    for i in range(len(eligible)):
        for j in range(i):
            if eligible[i].chunk.file_path==eligible[j].chunk.file_path:
                overlap=len(body_sets[i]&body_sets[j])/max(1,len(body_sets[i]|body_sets[j]))
                redundancy[i,j]=max(0,(overlap-.8)/.2)
    def utility(indices,chars):
        q=_feature_score(indices,profiles,'query_features',profile['token_weights'])
        roles=_feature_score(indices,profiles,'roles')
        identity=_feature_score(indices,profiles,'identities')
        unique={}
        for i in indices:
            text=eligible[i].chunk.text
            unique[text]=max(unique.get(text,0),profiles[i]['aligned_relevance'])
        relevance=sum(unique.values())/max(1,len(eligible))
        duplicate=sum(value for (i,j),value in redundancy.items() if i in indices and j in indices)/max(1,len(eligible))
        return (SETTINGS['token_weight']*q+SETTINGS['role_weight']*roles+SETTINGS['identity_weight']*identity
            +SETTINGS['relevance_weight']*relevance-SETTINGS['redundancy_weight']*duplicate
            -SETTINGS['cost_weight']*chars/max(1,config.budget*4))
    baseline_indices=[i for i in range(len(eligible)) if baseline_mask & (1<<i)]
    baseline_utility=utility(baseline_indices,len(baseline.context))
    best_mask,best_key=baseline_mask,(baseline_utility,-len(baseline.context),-baseline_mask)
    costs_dp=[0]*(1<<len(eligible))
    feasible=guarded=0
    for mask in range(1,1<<len(eligible)):
        bit=mask & -mask;i=bit.bit_length()-1;rest=mask^bit
        chars=costs_dp[rest]+costs[i]+(len(SEPARATOR) if rest else 0)
        costs_dp[mask]=chars
        if chars>config.budget*4:
            continue
        feasible+=1
        indices=[i for i in range(len(eligible)) if mask & (1<<i)]
        identities=set().union(*(set(profiles[i]['identities']) for i in indices))
        signatures=set().union(*(guards[i] for i in indices))
        if not id_guard<=identities or not role_guard<=signatures:
            continue
        guarded+=1
        key=utility(indices,chars),-chars,-mask
        if key>best_key:
            best_mask,best_key=mask,key
    if best_key[0]-baseline_utility<SETTINGS['improvement_margin']:
        return fallback('insufficient_predicted_gain')
    chosen=[(c.chunk,c.cosine) for i,c in enumerate(eligible) if best_mask & (1<<i)]
    context,used,estimated=RAGPipeline(None,None,max_context_tokens=config.budget)._build_context(chosen)
    if len(used)!=len(chosen) or any(c.text!=original[c.chunk_id].chunk.text for c,_ in used):
        raise AssertionError('Whole-fragment renderer disagreement')
    selected={c.chunk_id for c,_ in used}
    protected_candidates=[c.chunk.chunk_id for i,c in enumerate(eligible) if baseline_mask & (1<<i) and guards[i]]
    decisions=[dict(id=c.chunk.chunk_id,reason='selected' if c.chunk.chunk_id in selected else 'query_role_budget',
        utility=best_key[0],baseline_utility=baseline_utility,predicted_gain=best_key[0]-baseline_utility,
        protected_baseline_candidates=protected_candidates,protected_verbatim_clauses=len(role_guard),
        protected_identity_features=sorted(id_guard),feasible_subsets=feasible,guarded_subsets=guarded)
        for c in candidates]
    return Selection(context,used,estimated,decisions)


def select_evidence_scopes(pools,config:SelectionConfig,query='',overall_budget=8000,version=VERSION):
    """Identical scope allocation; all ranking stays within an authorized scope."""
    return _allocate_scopes(pools,overall_budget,lambda scope,candidates,budget:
        _pack(candidates,scope,replace(config,budget=min(config.budget,budget)),query,version))
