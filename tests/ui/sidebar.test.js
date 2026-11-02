const test = require('node:test');
const assert = require('node:assert/strict');
const {conversationGroups, createExpansionState, sidebarWidth} = require('../../laew/ui/ui-state.js');
const fs = require('node:fs');
const path = require('node:path');

test('groups by stable project ID, preserving unavailable and empty projects', () => {
  const projects=[{id:'a',name:'Same name'},{id:'b',name:'Same name'},{id:'empty',name:'Empty'}];
  const conversations=[
    {id:'one',scope_type:'project',project_id:'a',updated_at:'2026-01-01'},
    {id:'two',scope_type:'project',project_id:'a',updated_at:'2026-02-01'},
    {id:'general',scope_type:'general',project_id:null,updated_at:'2026-01-01'},
    {id:'other',scope_type:'project',project_id:'b',updated_at:'2026-01-01'},
    {id:'archived',scope_type:'project',project_id:'gone',updated_at:'2026-01-01'}
  ];
  const groups=conversationGroups(projects,conversations);
  assert.deepEqual(groups.map(group=>group.key),['general','project:a','project:b','project:empty','project:gone']);
  assert.deepEqual(groups.map(group=>group.items.map(item=>item.id)),[['general'],['two','one'],['other'],[],['archived']]);
  assert.equal(groups[4].unavailable,true);
  assert.equal(conversations[0].id,'one');
});
test('sidebar clamps to desktop and available viewport limits', () => {
  assert.equal(sidebarWidth(100,1600,330),210);
  assert.equal(sidebarWidth(700,1600,330),480);
  assert.equal(sidebarWidth(480,1000,290),350);
  assert.equal(sidebarWidth(480,1000,0),480);
  assert.equal(sidebarWidth(260,700,290),210);
  assert.equal(sidebarWidth('bad',1600,330),260);
});

test('expansion is independent, persistent, and restoration respects a manual collapse', () => {
  const values=new Map();
  const storage={get:key=>values.get(key) ?? null, set:(key,value)=>values.set(key,value)};
  let state=createExpansionState(storage);
  assert.equal(state.projectsExpanded,true);
  assert.equal(state.isExpanded('general'),true);
  assert.equal(state.isExpanded('project:a'),false);
  state.setGroup('project:a',true); state.setGroup('general',false); state.setProjects(false);
  state=createExpansionState(storage);
  assert.equal(state.projectsExpanded,false);
  assert.equal(state.isExpanded('general'),false);
  assert.equal(state.isExpanded('project:a'),true);
  state.revealConversation('general',true);
  assert.equal(state.isExpanded('general'),false);
  state.revealConversation('general',false);
  assert.equal(state.isExpanded('general'),true);
  assert.equal(state.isExpanded('project:a'),true);
  state.revealConversation('project:b',true);
  assert.equal(state.isExpanded('project:b'),true);
});
test('navigation markup has one existing project tree and no separate conversation section', () => {
  const html=fs.readFileSync(path.join(__dirname,'../../laew/ui/index.html'),'utf8');
  assert.equal((html.match(/id="project-list"/g)||[]).length,1);
  assert.equal((html.match(/id="projects-toggle"/g)||[]).length,1);
  assert.doesNotMatch(html,/id="conversation-list"|id="conversations-title"/);
  assert.match(html,/id="projects-toggle"[^>]*aria-controls="projects-content"/);
  assert.match(html,/id="projects-content"[\s\S]*id="project-list"/);
});
