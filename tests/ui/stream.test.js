const test = require('node:test');
const assert = require('node:assert/strict');
const { readEventStream } = require('../../laew/ui/stream.js');

test('partial response reaches the UI consumer before the final event', async () => {
  let controller;
  const response = new Response(new ReadableStream({ start(value) { controller = value; } }));
  const visible = [];
  let firstDelta;
  const partialShown = new Promise((resolve) => { firstDelta = resolve; });
  const consuming = readEventStream(response, (event) => {
    if (event.type === 'delta') { visible.push(event.text); firstDelta(); }
  });

  controller.enqueue(new TextEncoder().encode('{"type":"start"}\n{"type":"delta","text":"First part"}\n'));
  await partialShown;
  assert.deepEqual(visible, ['First part']);

  controller.enqueue(new TextEncoder().encode('{"type":"delta","text":" second part"}\n'));
  await new Promise((resolve) => setImmediate(resolve));
  assert.deepEqual(visible, ['First part', ' second part']);
  controller.enqueue(new TextEncoder().encode('{"type":"done","response":"First part second part"}\n'));
  controller.close();
  await consuming;
});

test('incomplete streams fail instead of appearing completed', async () => {
  const response = new Response('{"type":"delta","text":"partial"}\n');
  await assert.rejects(readEventStream(response, () => {}), /ended before LAEW reported completion/);
});

test('UTF-8 split inside emoji survives NDJSON streaming', async () => {
  const sample = 'Zażółć gęślą jaźń — 25°C — 🐕 🧬 🤝 🐶';
  const bytes = new TextEncoder().encode(JSON.stringify({type:'delta', text:sample}) + '\n' + JSON.stringify({type:'done', response:sample}) + '\n');
  const dog = bytes.findIndex((value, index) => value === 0xf0 && bytes[index + 1] === 0x9f && bytes[index + 2] === 0x90 && bytes[index + 3] === 0x95);
  const response = new Response(new ReadableStream({start(controller) {
    controller.enqueue(bytes.slice(0, dog + 1)); controller.enqueue(bytes.slice(dog + 1, dog + 3)); controller.enqueue(bytes.slice(dog + 3)); controller.close();
  }}));
  const events = []; await readEventStream(response, event => events.push(event));
  assert.equal(events[0].text, sample); assert.equal(events[1].response, sample);
});
