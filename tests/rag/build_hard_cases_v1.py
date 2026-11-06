"""Generate fixed hard-case fixtures; labels are independent of chunk boundaries."""
import json
from pathlib import Path

root = Path('tests/rag/hard_cases_v1')
(root / 'global').mkdir(parents=True, exist_ok=True)
(root / 'project').mkdir(exist_ok=True)
queries = []
languages = {}

def add(name, content, questions, language='en'):
    (root/'global'/name).write_text(content, encoding='utf8')
    source = '@knowledge/' + name
    languages[source] = language
    for text, passages, category, split, lang in questions:
        queries.append(dict(id=f'h{len(queries)+1:02}', text=text, language=lang,
            phenomenon=category, split=split, allowed_scope='global',
            expected_document_ids=[source], relevance={source:2}, no_answer=None,
            evidence=[dict(document_id=source, passage=p) for p in passages]))

add('startup.md', '# Controller\n## Startup\nCommunication must be initialized before the actuator to reject stale commands.\n```python\ninitialize_communication()\nenable_actuator()\n```\nThis order is mandatory even after a warm restart.\n\n## Diagnostics\n' + 'The diagnostic recorder stores startup timestamps for later inspection.\n'*40,
    [('Why initialize communication before enabling the actuator, including warm restarts?', ['Communication must be initialized before the actuator to reject stale commands.','initialize_communication()','This order is mandatory even after a warm restart.'], 'description_code','dev','en')])
add('motor.md', '# Drive\n## Nominal ratings\nThese measurements apply at nominal load and 20 C ambient temperature.\n| Parameter | Value | Unit |\n| --- | --- | --- |\n| Voltage | 24 | V |\n| Current | 2.5 | A |\n| Speed | 3000 | rpm |\nThese ratings are not maximum operating limits.\n## Maximum ratings\nThe emergency voltage ceiling is 29 V.\n',
    [('Is 24 V a maximum motor limit, and under which conditions does it apply?', ['These measurements apply at nominal load and 20 C ambient temperature.','| Voltage | 24 | V |','These ratings are not maximum operating limits.'], 'description_table','dev','en')])
pre='Before starting, disconnect the actuator and create a firmware backup.'
steps=''.join(f'{i}. Record diagnostic channel {i} and confirm stable communication before proceeding.\n' for i in range(1,29))
add('firmware.md', '# Service\n## Firmware update\n'+pre+'\n### Procedure\n'+steps+'29. Upload the image, then verify checksum 0x7A91 before restart.\n',
    [('What must be done before the firmware procedure and what checksum must be verified before restart?', [pre,'29. Upload the image, then verify checksum 0x7A91 before restart.'], 'procedure','dev','en')])
rows=''.join(f'| sensor-{i:02} | {20+i} | 0.1 |\n' for i in range(65))
add('sensors.md', '# Sensors\n## Calibration\nOffsets are measured in millivolts with the actuator disconnected.\n| Sensor | Offset (mV) | Tolerance (mV) |\n| --- | --- | --- |\n'+rows+'These offsets are calibration corrections, not alarm thresholds.\n',
    [('What is the offset of sensor-48, its unit and the calibration safety condition?', ['| sensor-48 | 68 | 0.1 |','Offset (mV)','Offsets are measured in millivolts with the actuator disconnected.'], 'large_table','dev','en'),
     ('Compare offsets of sensor-02 and sensor-61; are these alarm thresholds?', ['| sensor-02 | 22 | 0.1 |','| sensor-61 | 81 | 0.1 |','These offsets are calibration corrections, not alarm thresholds.'], 'comparison','validation','en')])
add('recovery.md', '# Recovery\n## Recovery order\nThe violet snapshot is approved only for the auxiliary controller.\n```sh\nstop_auxiliary\nrestore_snapshot violet\nverify_auxiliary\n```\nNever apply this snapshot to the main controller.\n## Main controller\nThe main controller uses the amber snapshot after manual approval.\n',
    [('Którą migawkę przywrócić dla kontrolera pomocniczego i gdzie nie wolno jej użyć?', ['The violet snapshot is approved only for the auxiliary controller.','restore_snapshot violet','Never apply this snapshot to the main controller.'], 'description_code','validation','pl'),
     ('Which snapshot is approved for the main controller?', ['The main controller uses the amber snapshot after manual approval.'], 'similar_sections','validation','en')])
add('polish.md', '# Instalacja\n## Zasilanie\nPrzed pomiarem odłącz silnik od sterownika.\n| Tryb | Napięcie (V) |\n| --- | --- |\n| nominalny | 48 |\n| serwisowy | 12 |\nWartości dotyczą napięcia wejściowego, nie wyjściowego.\n',
    [('What voltage applies to nominal operation, what should be disconnected, and is it output voltage?', ['Przed pomiarem odłącz silnik od sterownika.','| nominalny | 48 |','Wartości dotyczą napięcia wejściowego, nie wyjściowego.'], 'cross_language','validation','en')], 'pl')
code=''.join(f'def sample_{i}():\n    return read_channel({i})\n\n' for i in range(60))
add('acquisition.md', '# Acquisition\n## Channel sampling\nThe acquisition functions require an isolated power supply; channel numbers are physical ports.\n```python\n'+code+'```\nThe returned values are raw ADC counts, not calibrated temperatures.\n',
    [('What does sample_47 return and what do its channel and units mean?', ['def sample_47():','return read_channel(47)','channel numbers are physical ports.','The returned values are raw ADC counts, not calibrated temperatures.'], 'long_code','validation','en')])
add('unusual.md', '# Odd input\n## Truncated example\nThe following payload is incomplete and must not be executed.\n~~~json\n'+('x'*2300)+'\n',
    [('Can the truncated payload be executed?', ['The following payload is incomplete and must not be executed.'], 'malformed','validation','en')])
# A multi-document question requires every evidence atom from both documents.
queries.append(dict(id='h11', text='Explain startup ordering and the safety condition before firmware updating.',language='en',phenomenon='multi_document',split='validation',allowed_scope='global',expected_document_ids=['@knowledge/startup.md','@knowledge/firmware.md'],relevance={'@knowledge/startup.md':2,'@knowledge/firmware.md':2},no_answer=None,evidence=[dict(document_id='@knowledge/startup.md',passage='Communication must be initialized before the actuator to reject stale commands.'),dict(document_id='@knowledge/firmware.md',passage=pre)]))
for text in ['What is the approved maximum torque of the motor?', 'What private actuator password is recorded in the project?']:
    queries.append(dict(id=f'h{len(queries)+1:02}',text=text,language='en',phenomenon='no_answer',split='validation',allowed_scope='global',expected_document_ids=[],relevance={},evidence=[],no_answer='absent'))
(root/'project'/'private.md').write_text('# Private actuator\nThe private actuator password is PRIVATE-413.\n',encoding='utf8')
(root/'dataset.json').write_text(json.dumps(dict(id='laew-hard-cases',version=1,queries=queries,document_languages=languages),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
