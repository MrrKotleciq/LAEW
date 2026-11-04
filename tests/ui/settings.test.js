const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {memoryModelSelection}=require('../../laew/ui/ui-state.js');
test('memory model selection preserves active-model inheritance and configured account identity',()=>{
  assert.equal(memoryModelSelection(''),null);
  assert.deepEqual(memoryModelSelection('["gemini","exact-model",""]'),{provider:'gemini',model:'exact-model',account_id:null});
  assert.deepEqual(memoryModelSelection('["chatgpt","same-model","account-b"]'),{provider:'chatgpt',model:'same-model',account_id:'account-b'});
});
test('existing Settings contains the only theme control and functional memory forms',()=>{
  const html=fs.readFileSync(path.join(__dirname,'../../laew/ui/index.html'),'utf8');
  assert.equal((html.match(/id="theme"/g)||[]).length,1);
  assert.match(html,/<main id="settings-view"[\s\S]*id="theme"/);
  assert.doesNotMatch(html,/<header[\s\S]*id="theme"[\s\S]*<\/header>/);
  assert.match(html,/id="nav-settings" class="nav-item settings-item">/);
  assert.match(html,/id="project-settings-dialog"[\s\S]*id="project-memory-form"/);
  assert.match(html,/id="chat-permission-mode"/);
});
