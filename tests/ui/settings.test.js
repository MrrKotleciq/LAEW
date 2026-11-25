const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
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

test('backup placeholders are presentational and empty fields export no example values',()=>{
  const ui=path.join(__dirname,'../../laew/ui');
  const html=fs.readFileSync(path.join(ui,'index.html'),'utf8');
  for(const value of ['D:\\LAEW-Backups','192.168.1.100 or hostname','22','backup_user','/backups/laew']){
    assert.ok(html.includes('placeholder="'+value+'"'),value);
    assert.ok(!html.includes('value="'+value+'"'),value);
  }
  assert.match(html,/<option value="" disabled selected>Select SSH private key<\/option>/);
  const sandbox={window:{}};
  vm.runInNewContext(fs.readFileSync(path.join(ui,'settings.js'),'utf8'),sandbox);
  const draft=sandbox.window.LAEWSettings.backupProposal('settings','revision',
    {enabled:false,directory:'',host:'',port:'',user:'',remote_directory:'',key:''});
  assert.equal(draft.enabled,false);
  assert.equal(draft.port,null);
  for(const name of ['directory','host','user','remote_directory','key'])assert.equal(draft[name],'');
});
