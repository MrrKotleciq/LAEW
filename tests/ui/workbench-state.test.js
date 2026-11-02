const test = require('node:test');
const assert = require('node:assert/strict');
const {createPanelState, modelGroups} = require('../../laew/ui/ui-state.js');
const {createThemeController} = require('../../laew/ui/theme.js');

test('tool activity switches once, preserving later manual selection', () => {
  const panel=createPanelState();
  panel.select('sources'); panel.beginRun(); assert.equal(panel.toolEvent(),'run');
  panel.select('context'); assert.equal(panel.toolEvent(),'context');
  panel.select('sources'); assert.equal(panel.toolEvent(),'sources');
  panel.beginRun(); assert.equal(panel.toolEvent(),'run');
});
test('manual tabs, invalid selection, project reset and text-only run', () => {
  const panel=createPanelState(); panel.select('run'); assert.equal(panel.active,'run');
  panel.select('context'); panel.beginRun(); assert.equal(panel.active,'context');
  panel.select('invalid'); assert.equal(panel.active,'context');
  panel.select('sources'); panel.reset(); assert.equal(panel.active,'context');
});
function theme(initial, dark=false) {
  const saved=[], applied=[], media={matches:dark,addEventListener(_,callback){this.change=callback;}};
  const controller=createThemeController({getItem:()=>initial,setItem:(key,value)=>saved.push([key,value])},media,v=>applied.push(v));
  return {controller,media,saved,applied};
}
test('theme defaults to System and follows OS changes', () => {
  const t=theme(null); assert.equal(t.controller.preference,'system'); assert.deepEqual(t.applied,['light']);
  t.media.matches=true;t.media.change();assert.equal(t.applied.at(-1),'dark');
});
test('explicit dark/light preference persists and overrides the system', () => {
  const t=theme('dark');assert.equal(t.applied.at(-1),'dark');
  t.controller.set('light'); t.media.matches=true;t.media.change();assert.equal(t.applied.at(-1),'light');
  assert.deepEqual(t.saved.at(-1),['laew-theme','light']);
  t.controller.set('system');assert.equal(t.applied.at(-1),'dark');
});
test('invalid or inaccessible storage does not break theme startup', () => {
  assert.equal(theme('unknown',true).applied[0],'dark');
  const media={matches:false,addEventListener(){}};const applied=[];
  const controller=createThemeController({getItem(){throw Error();},setItem(){throw Error();}},media,v=>applied.push(v));
  controller.set('dark');assert.equal(applied.at(-1),'dark');
});
test('catalog grouping preserves provider and account identities for model switches', () => {
  const groups=modelGroups([['["chatgpt","a"]',[{id:'same-model',label:'GPT'}]],['["chatgpt","b"]',[{id:'same-model'}]],['["gemini",""]',[{id:'available-gemini'}]]],{chatgpt:'OpenAI',gemini:'Google'},[{id:'a',label:'Account A'},{id:'b',label:'Account B'}]);
  assert.deepEqual(groups.map(g=>g.label),['OpenAI · Account A','OpenAI · Account B','Google']);
  assert.notEqual(groups[0].options[0].value,groups[1].options[0].value);
  assert.deepEqual(JSON.parse(groups[2].options[0].value),['gemini','available-gemini','']);
});
test('empty catalogs do not invent available models',()=>assert.deepEqual(modelGroups([],{gemini:'Google'}),[]));
