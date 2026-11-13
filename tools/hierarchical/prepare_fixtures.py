"""Author and freeze Task 3B fixtures BEFORE embeddings or method evaluation."""
import hashlib
import json
from pathlib import Path


def main():
    root = Path('tests/rag/hierarchical_long_v1')
    if root.exists():
        raise RuntimeError('Never overwrite a frozen fixture')
    manuals = [
        ('global', 'orion', 'Orion recorder', 'en',
         'Before servicing the Orion recorder, isolate the optical transmitter and preserve the last recovery certificate.',
         'Orion acceptance requires a 55-second uninterrupted trace and clock drift below 65 microseconds.'),
        ('global', 'mira', 'Mira cooling plant', 'en',
         'Before draining Mira, close the bypass valve and record the coolant batch identifier.',
         'Mira acceptance requires stable pressure for 18 minutes and a return temperature below 31 degrees Celsius.'),
        ('global', 'polar', 'Polar enclosure', 'de',
         'Vor dem Öffnen von Polar muss die Heizung getrennt und die Dichtungscharge notiert werden.',
         'Die Polar-Abnahme verlangt 22 Minuten ohne Feuchtealarm und einen Isolationswiderstand über 9 Megaohm.'),
        ('project', 'delta', 'Delta deployment', 'en',
         'Before the Delta deployment, preserve the rollback manifest and stop the export scheduler.',
         'Delta release approval requires two matching snapshot digests and a 25-minute successful replay.'),
    ]
    filler = [
        ('Inventory', 'The custodian inventories replaceable components, checks storage locations and records ownership changes.'),
        ('Scheduling', 'Operators coordinate maintenance windows with adjacent teams and retain the schedule in the shift register.'),
        ('Transport', 'During transport, protect connectors, use labeled containers and compare package counts at handover.'),
        ('Calibration', 'Routine calibration uses traceable references; the log records instrument identity, range and operator.'),
        ('Archive', 'The archive stores previous maintenance logs with source identifiers, dates and review responsibility.'),
    ]
    for scope, key, title, language, prerequisite, acceptance in manuals:
        folder = root/scope
        folder.mkdir(parents=True, exist_ok=True)
        sections = [f'# {title} maintenance manual\n\nThis synthetic {language} manual is an evaluation source for {title}.']
        for i in range(20):
            label, sentence = filler[i % len(filler)]
            if i == 2:
                label, sentence = 'Preparation', prerequisite
            elif i == 17:
                label, sentence = 'Acceptance', acceptance
            sections.append(f'## {label} {i+1}\n\n{sentence}\n\n'
                            f'{title} procedure register {i+1} also records custody, the inspection date and the responsible reviewer. '
                            'A routine housekeeping observation is not a replacement for the acceptance record. '
                            'Keep the original source reference with any copied observation so later reviews can identify its revision.')
        (folder/f'{key}.md').write_text('\n\n'.join(sections)+'\n', encoding='utf-8')
    def atom(doc, index):
        entry = next(m for m in manuals if m[1] == doc)
        alias = '@knowledge' if entry[0] == 'global' else '@project'
        return {'document_id': f'{alias}/{doc}.md', 'passage': entry[index]}
    questions = [
        ('l01','pl','global','Co zabezpieczyć przed serwisem rejestratora Orion i jakie wyniki potwierdzają odbiór?', [atom('orion',4),atom('orion',5)]),
        ('l02','en','global','Which preparation and acceptance records are required for Mira cooling maintenance?', [atom('mira',4),atom('mira',5)]),
        ('l03','de','global','Was muss vor dem Öffnen von Polar geschehen und welche Nachweise verlangt die Abnahme?', [atom('polar',4),atom('polar',5)]),
        ('l04','pl','project','Co zachować przed wdrożeniem Delta i jakie są wymagania zatwierdzenia wydania?', [atom('delta',4),atom('delta',5)]),
        ('l05','en','global','Compare the acceptance requirements for Orion, Mira and Polar.', [atom('orion',5),atom('mira',5),atom('polar',5)]),
        ('l06','pl','hybrid','Jakie warunki odbioru mają Orion i wdrożenie Delta?', [atom('orion',5),atom('delta',5)]),
        ('l07','en','hybrid','List the preparation requirements for Orion, Mira, Polar and the Delta deployment.', [atom(k,4) for k in ('orion','mira','polar','delta')]),
        ('l08','en','global','What battery endurance does the Neptune submarine guarantee?', []),
    ]
    rows=[]
    for id_,language,scope,text,evidence in questions:
        docs=list(dict.fromkeys(a['document_id'] for a in evidence))
        rows.append({'id':id_,'language':language,'allowed_scope':scope,'text':text,'evidence':evidence,
                     'expected_document_ids':docs,'relevance':dict.fromkeys(docs,2),'no_answer':None if evidence else 'unsupported',
                     'topic_id':'authored_long_manuals','phenomenon':'long_document_multi_document', 'split':'agent_authored_validation'})
    dataset={'id':'laew-hierarchical-long-v1','version':1,'judgment':'Agent-authored and frozen before scoring; not independently human judged.',
             'queries':rows,'document_languages':{('@knowledge/' if m[0]=='global' else '@project/')+m[1]+'.md':m[3] for m in manuals}}
    (root/'dataset.json').write_text(json.dumps(dataset,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    hashes={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file()}
    (root/'FREEZE.json').write_text(json.dumps({'date':'2026-11-11','authorship':dataset['judgment'],'sha256':hashes},indent=2)+'\n')
    print(f'Frozen {len(hashes)} files, {len(rows)} queries; no embeddings or retrieval performed.')


if __name__=='__main__':
    main()
