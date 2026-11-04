const test=require('node:test');
const assert=require('node:assert/strict');
const {selectionForApproval,reviewable}=require('../../laew/ui/knowledge.js');

test('batch approval preserves reviewed versions and excludes applied and rejected proposals',()=>{
  const rows=[{id:'new',version:2,status:'pending_review'},{id:'later',version:3,status:'deferred'},{id:'saved',version:4,status:'applied'},{id:'no',version:5,status:'rejected'}];
  assert.deepEqual(selectionForApproval(rows,new Map(rows.map(row=>[row.id,row.version]))),[{id:'new',version:2},{id:'later',version:3}]);
  assert.equal(reviewable(rows[2]),false);
});

class Element{
  constructor(){this.children=[];this.handlers={};this.attributes={};this.hidden=false;this.disabled=false;this.value='';this.textContent='';}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this.children=nodes;}
  addEventListener(name,handler){this.handlers[name]=handler;}
  setAttribute(name,value){this.attributes[name]=value;}
  contains(){return false;}
  focus(){document.activeElement=this;}
  async fire(name){return this.handlers[name]?.({currentTarget:this,submitter:this,preventDefault(){}});}
}
function fixture(){
  const nodes=new Map(),events={};
  global.document={activeElement:null,querySelector(selector){if(!nodes.has(selector))nodes.set(selector,new Element());return nodes.get(selector);},createElement(){return new Element();},createTextNode(text){return {textContent:text};},addEventListener(name,fn){events[name]=fn;}};
  global.window={LAEWMarkdown:{renderMarkdown(target,source){target.textContent=source;}}};
  delete require.cache[require.resolve('../../laew/ui/knowledge.js')];
  const api=require('../../laew/ui/knowledge.js');
  let project=null,requests=[];
  const row={id:'proposal',title:'Technical note',version:2,status:'pending_review',operation:'create',content:'# Confirmed'};
  let state={settings:{extraction_enabled:true,interval_completed_turns:5},proposals:[row],status:{pending_index_updates:0},extraction_model:null};
  global.fetch=async(url,options)=>{
    requests.push({url,body:options.body?JSON.parse(options.body):undefined});
    const result=url.includes('/preview')?{...row,markdown:'---\nname: Note\n---\n# Confirmed',target_path:'@knowledge/topics/note.md',diff:'+ confirmed',sources:[{evidence:'<script>bad()</script>'}]}:state;
    return {ok:true,json:async()=>result};
  };
  const ui=api.create({project:()=>project,conversation:()=> 'conversation'}),q=selector=>document.querySelector(selector);
  return {ui,q,events,requests,row,setProject(value){project=value;},setState(value){state=value;}};
}

test('review remains nonmodal, shows actual source and diff, and does not write on close',async()=>{
  const f=fixture();await f.ui.refresh();
  assert.equal(f.q('#knowledge-count').textContent,'1');
  await f.q('#knowledge-list').children[0].children[3].children[1].fire('click');
  // Preview fetch is asynchronous; the click handler intentionally does not block navigation.
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(f.q('#knowledge-path').textContent,'@knowledge/topics/note.md');
  assert.equal(f.q('#knowledge-diff').textContent,'+ confirmed');
  assert.match(f.q('#knowledge-sources').textContent,/<script>bad\(\)<\/script>/);
  f.ui.close();assert.equal(f.q('#knowledge-review').hidden,true);
  assert.equal(f.requests.some(request=>request.url.endsWith('/decide')),false);
});

test('edited draft cannot be approved until saved and a fresh preview is loaded',async()=>{
  const f=fixture();await f.ui.refresh();await f.q('#knowledge-list').children[0].children[3].children[1].fire('click');await new Promise(resolve=>setImmediate(resolve));
  f.q('#knowledge-editor').value='# Edited';await f.q('#knowledge-editor').fire('input');
  assert.equal(f.q('#knowledge-approve').disabled,true);
  await f.q('#knowledge-approve').fire('click');
  assert.equal(f.requests.some(request=>request.url.endsWith('/decide')),false);
  await f.q('#knowledge-save').fire('click');
  assert.deepEqual(f.requests.find(request=>request.url.endsWith('/edit')).body,{project_id:null,id:'proposal',version:2,content:'# Edited'});
  assert.equal(f.q('#knowledge-approve').disabled,false);
});

test('scope switch discards displayed source material and requests the selected scope',async()=>{
  const f=fixture();await f.ui.refresh();f.setProject('project-b');await f.ui.refresh();
  assert.equal(f.q('#knowledge-preview').hidden,true);
  assert.match(f.requests.at(-1).url,/project_id=project-b$/);
  f.q('#knowledge-review').hidden=false;f.events.keydown({key:'Escape',preventDefault(){}});
  assert.equal(f.q('#knowledge-review').hidden,true);
  assert.equal(document.activeElement,f.q('#knowledge-toggle'));
});

test('ambiguous destination requires an explicit choice and updates only a displayed match',async()=>{
  const f=fixture();f.row.needs_target_decision=true;f.row.matches=[{target:'@knowledge/topics/existing.md'}];
  await f.ui.refresh();await f.q('#knowledge-list').children[0].children[3].children[1].fire('click');await new Promise(resolve=>setImmediate(resolve));
  assert.equal(f.q('#knowledge-approve').disabled,true);
  assert.equal(f.q('#knowledge-matches').hidden,false);
  await f.q('#knowledge-save').fire('click');
  assert.equal(f.requests.some(request=>request.url.endsWith('/edit')),false);
  f.q('#knowledge-destination').value='@knowledge/topics/existing.md';await f.q('#knowledge-destination').fire('change');
  await f.q('#knowledge-save').fire('click');
  const edit=f.requests.find(request=>request.url.endsWith('/edit')).body;
  assert.equal(edit.kind,'update');assert.equal(edit.target,'@knowledge/topics/existing.md');
});

test('active model is sent only when selected in Knowledge settings',async()=>{
  const f=fixture();await f.ui.refresh();
  assert.equal(f.q('#knowledge-model-source').value,'memory');
  f.q('#knowledge-model-source').value='active';
  await f.q('#knowledge-settings-form').fire('submit');
  const saved=f.requests.find(request=>request.url.endsWith('/settings'));
  assert.equal(saved.body.settings.model_source,'active');
});
