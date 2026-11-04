/* Settings and memory management share the application's existing API and scope. */
(function(root){
  'use strict';
  const q=selector=>document.querySelector(selector);
  async function request(path,body){
    const response=await fetch(path,body===undefined?{cache:'no-store'}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const data=await response.json(); if(!response.ok) throw new Error(data.error || 'Settings operation failed.'); return data;
  }
  function option(value,label){const node=document.createElement('option');node.value=value;node.textContent=label;return node;}
  function create(app){
    let state=null,editor=null,deleting=null,project=null,menuProject=null,trigger=null,refreshId=0;
    const result=q('#settings-result'),menu=q('#project-settings-menu');
    const selectedProject=()=>q('#memory-project').value || null;
    const report=error=>{result.textContent=error.message || error;};
    async function action(name,body={}){const data=await request('/api/memory/'+name,{project_id:selectedProject(),...body});await refresh();return data;}
    function closeMenu(restore=false){menu.hidden=true;if(restore && trigger?.isConnected) trigger.focus();menuProject=null;trigger=null;}
    function projectMenu(id,x,y,source){menuProject=id;trigger=source;menu.hidden=false;const rect=menu.getBoundingClientRect();menu.style.left=Math.max(4,Math.min(x,innerWidth-rect.width-4))+'px';menu.style.top=Math.max(4,Math.min(y,innerHeight-rect.height-4))+'px';menu.querySelector('button').focus();}
    async function openProject(id){
      closeMenu();q('#project-settings-error').textContent='';project=null;
      try {
        const data=await request('/api/project/config',{project_id:id});project=id;
        q('#project-settings-title').textContent=data.name+' · Settings';
        q('#project-language-override').value=data.overrides.documentation_language || '';
        q('#project-settings-effective').textContent='Workspace default: '+data.defaults.documentation_language+' · Effective: '+data.effective.documentation_language;
        renderProjectMemory(data);
        q('#project-settings-dialog').showModal();
      }catch(error){report(error);}
    }
    const memoryFields=[['recall_enabled','Use Long-Term Memory','boolean'],['extraction_mode','Automatic Memory',['off','review','auto']],['interval_completed_turns','Analyze every N completed turns','number'],['extraction_model','Extraction model','model'],['max_memories','Maximum memories','number'],['token_budget','Token budget','number'],['semantic_enabled','Semantic retrieval','boolean'],['fallback_to_fts','FTS5 fallback','boolean']];
    function renderProjectMemory(data){
      const fields=q('#project-memory-fields');fields.replaceChildren();q('#project-memory-result').textContent='';
      memoryFields.forEach(([key,title,type])=>{
        const row=document.createElement('div');row.className='project-memory-field';
        const label=document.createElement('label'),override=document.createElement('input');override.type='checkbox';override.dataset.override=key;override.checked=Object.hasOwn(data.memory_overrides,key);label.append(override,document.createTextNode(' Override '+title));
        const value=data.memory_effective[key];let control;
        if(type==='boolean'){control=document.createElement('select');control.append(option('true','On'),option('false','Off'));control.value=String(value);}
        else if(Array.isArray(type)){control=document.createElement('select');type.forEach(item=>control.append(option(item,item)));control.value=value;}
        else if(type==='model'){
          control=document.createElement('select');control.append(option('','Same as active chat model'));app.catalogs().forEach(group=>group.options.forEach(model=>control.append(option(model.value,group.label+' · '+model.label))));
          if(value){const selected=JSON.stringify([value.provider,value.model,value.account_id || '']);if(!Array.from(control.options).some(item=>item.value===selected))control.append(option(selected,value.model+' · catalog unavailable'));control.value=selected;}
        }else{control=document.createElement('input');control.type='number';control.value=value;const limits={interval_completed_turns:[2,20],max_memories:[1,20],token_budget:[100,2000]}[key];control.min=limits[0];control.max=limits[1];}
        control.dataset.memoryKey=key;control.setAttribute('aria-label',title);control.disabled=!override.checked;override.addEventListener('change',()=>{control.disabled=!override.checked;});row.append(label,control);fields.append(row);
      });
    }
    q('#project-memory-form').addEventListener('submit',async event=>{
      event.preventDefault();event.submitter.disabled=true;
      try{
        const overrides={};memoryFields.forEach(([key,title,type])=>{
          if(!q(`[data-override="${key}"]`).checked)return;const value=q(`[data-memory-key="${key}"]`).value;
          if(type==='boolean')overrides[key]=value==='true';else if(type==='number')overrides[key]=Number(value);else if(type==='model'){overrides[key]=root.LAEWUI.memoryModelSelection(value);}else overrides[key]=value;
        });
        const data=await request('/api/project/config',{project_id:project,memory_overrides:overrides});renderProjectMemory(data);q('#project-memory-result').textContent='Project memory overrides saved.';
      }catch(error){q('#project-memory-result').textContent=error.message;}finally{event.submitter.disabled=false;}
    });
    menu.querySelector('button').addEventListener('click',()=>{const id=menuProject;if(id) openProject(id);});
    menu.addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();closeMenu(true);}});
    document.addEventListener('pointerdown',event=>{if(!menu.contains(event.target))closeMenu();});
    q('#project-settings-close').addEventListener('click',()=>q('#project-settings-dialog').close());
    q('#project-settings-form').addEventListener('submit',async event=>{
      event.preventDefault();const button=event.submitter;button.disabled=true;
      try {await request('/api/project/config',{project_id:project,overrides:{documentation_language:q('#project-language-override').value || null}});q('#project-settings-error').textContent='Project language saved.';app.onProjectSaved();}
      catch(error){q('#project-settings-error').textContent=error.message;}finally{button.disabled=false;}
    });
    q('#memory-delete-cancel').addEventListener('click',()=>{deleting=null;q('#memory-delete-dialog').close();});
    q('#memory-delete-confirm').addEventListener('click',async()=>{
      const button=q('#memory-delete-confirm');if(!deleting)return;button.disabled=true;
      try{await action('delete',{id:deleting.id,version:deleting.version});deleting=null;q('#memory-delete-dialog').close();}
      catch(error){q('#memory-delete-error').textContent=error.message;}finally{button.disabled=false;}
    });
    function renderRecords(){
      const container=q('#memory-list');container.replaceChildren();if(!state)return;
      const filter=q('#memory-filter').value;
      const rows=[...state.memories.map(item=>({...item,pending:false})),...state.proposals.map(item=>({...item,pending:true}))];
      rows.filter(row=>filter==='all' || (filter==='pending'?row.pending:filter==='active'?!row.pending:row.scope===filter)).forEach(row=>{
        const article=document.createElement('article');article.className='memory-record';
        const content=document.createElement('p');content.textContent=row.content;
        const details=document.createElement('small');details.textContent=`${row.category} · ${row.scope==='user'?'User Memory':'Project '+row.project_id} · ${row.pending?'Pending Review · '+row.operation+(row.target_id?' · replaces '+row.target_id:''):row.status} · Created ${new Date(row.created_at*1000).toLocaleString()} · Updated ${new Date(row.updated_at*1000).toLocaleString()}`;
        const controls=document.createElement('div');controls.className='settings-actions';
        function button(label,handler){const b=document.createElement('button');b.type='button';b.textContent=label;b.addEventListener('click',async()=>{b.disabled=true;try{await handler();}catch(error){report(error);}finally{b.disabled=false;}});controls.append(b);}
        if(row.pending){
          button('Approve',()=>action('decide',{id:row.id,approve:true}));
          button('Reject',()=>action('decide',{id:row.id,approve:false}));
          button('Edit before approval',()=>openEditor(row));
        }else{
          button('Edit',()=>openEditor(row));
          button('Delete',()=>{deleting=row;q('#memory-delete-content').textContent=row.content;q('#memory-delete-error').textContent='';q('#memory-delete-dialog').showModal();q('#memory-delete-cancel').focus();});
        }
        button('View source',async()=>{
          const data=row.pending?row:await request('/api/memory/get?'+new URLSearchParams({id:row.id,...(selectedProject()?{project_id:selectedProject()}:{})}));
          const sources=data.sources || [];
          const source=sources.find(source=>source.conversation_id);
          if(source){await app.openConversation(source.conversation_id);}
          else report('Source: manual entry.');
        });
        const sourceLabel=document.createElement('small');sourceLabel.textContent=(row.sources || []).map(source=>source.conversation_id?' · Source: '+source.conversation_id+(source.event_id?' / '+source.event_id:''):' · Source: '+source.origin).join('') || ' · Source: manual entry';article.append(content,details,sourceLabel);if(row.target){const previous=document.createElement('p');previous.textContent='Current record (version '+row.target.version+'): '+row.target.content;article.append(previous);}article.append(controls);container.append(article);
      });
      if(!container.childNodes.length){const empty=document.createElement('p');empty.className='muted-note';empty.textContent='No memories or pending proposals in this scope.';container.append(empty);}
    }
    function openEditor(row=null){
      editor=row;q('#memory-editor-title').textContent=row?.pending?'Edit & approve proposal':row?'Edit memory':'Add memory';
      q('#memory-content').value=row?.content || '';q('#memory-category').value=row?.category || 'fact';q('#memory-category').disabled=!!row?.pending;q('#memory-scope').value=row?.scope || 'user';q('#memory-scope').disabled=!!row;
      q('#memory-editor-error').textContent='';q('#memory-editor').showModal();q('#memory-content').focus();
    }
    q('#memory-add').addEventListener('click',()=>openEditor());
    q('#memory-editor-cancel').addEventListener('click',()=>q('#memory-editor').close());
    q('#memory-editor-form').addEventListener('submit',async event=>{
      event.preventDefault();event.submitter.disabled=true;
      try{
        const content=q('#memory-content').value,category=q('#memory-category').value,scope=q('#memory-scope').value;
        if(editor?.pending)await action('decide',{id:editor.id,approve:true,content});
        else if(editor)await action('update',{id:editor.id,version:editor.version,content,category});
        else {if(scope==='project'&&!selectedProject())throw new Error('Select a project first.');await action('add',{content,category,scope});}
        q('#memory-editor').close();
      }catch(error){q('#memory-editor-error').textContent=error.message;}finally{event.submitter.disabled=false;}
    });
    async function refresh(){
      const id=++refreshId,projectId=selectedProject();
      try{
        const [data,defaults]=await Promise.all([request('/api/memory/state'+(projectId?'?'+new URLSearchParams({project_id:projectId}):'')),request('/api/settings')]);
        if(id!==refreshId)return;state=data;
        const categorySelect=q('#memory-category'),previousCategory=categorySelect.value;
        categorySelect.replaceChildren();
        Object.entries(data.categories).forEach(([category,description])=>{const node=option(category,category);node.title=description;categorySelect.append(node);});
        categorySelect.value=previousCategory || 'fact';
        q('#default-language').value=defaults.defaults.documentation_language;
        const settings=data.settings;
        q('#memory-recall').checked=settings.recall_enabled;q('#memory-mode').value=settings.extraction_mode;q('#memory-interval').value=settings.interval_completed_turns;
        q('#memory-max').value=settings.max_memories;q('#memory-budget').value=settings.token_budget;q('#memory-semantic').checked=settings.semantic_enabled;q('#memory-fts').checked=settings.fallback_to_fts;
        const models=q('#memory-model');models.replaceChildren(option('','Same as active chat model'));
        app.catalogs().forEach(group=>{const node=document.createElement('optgroup');node.label=group.label;group.options.forEach(model=>node.append(option(model.value,model.label)));models.append(node);});
        if(settings.extraction_model){const value=JSON.stringify([settings.extraction_model.provider,settings.extraction_model.model,settings.extraction_model.account_id || '']);if(!Array.from(models.options).some(item=>item.value===value))models.append(option(value,settings.extraction_model.model+' · catalog unavailable'));models.value=value;}
        const projects=q('#memory-project');projects.replaceChildren(option('','User Memory only'));app.projects().forEach(project=>projects.append(option(project.id,project.name)));projects.value=projectId || '';
        const status=data.status;q('#memory-status').textContent=`SQLite: ${status.sqlite_available?'available':'unavailable'} · ChromaDB: ${status.chroma_available?'available':'unavailable'} · Retrieval: ${status.retrieval_mode} · ${data.proposals.length} pending proposals · ${status.pending_index_updates} pending index updates · ${status.extraction_jobs.length} pending analyses`+(status.last_sync?' · Last sync '+new Date(status.last_sync*1000).toLocaleString():'')+(status.error?' · '+status.error:'')+status.extraction_jobs.filter(job=>job.error).map(job=>' · '+job.error).join('');
        renderRecords();
      }catch(error){if(id===refreshId){report(error);q('#memory-status').textContent='Memory status unavailable: '+error.message;}}
    }
    q('#memory-project').addEventListener('change',refresh);q('#memory-filter').addEventListener('change',renderRecords);q('#settings-refresh').addEventListener('click',refresh);
    q('#defaults-form').addEventListener('submit',async event=>{event.preventDefault();try{await request('/api/settings',{defaults:{documentation_language:q('#default-language').value}});report('Workspace defaults saved.');app.onProjectSaved();}catch(error){report(error);}});
    q('#memory-settings-form').addEventListener('submit',async event=>{
      event.preventDefault();event.submitter.disabled=true;
      try{const selected=q('#memory-model').value;const [provider,model,account_id]=selected?JSON.parse(selected):[];
        await action('settings',{settings:{recall_enabled:q('#memory-recall').checked,extraction_mode:q('#memory-mode').value,interval_completed_turns:Number(q('#memory-interval').value),max_memories:Number(q('#memory-max').value),token_budget:Number(q('#memory-budget').value),semantic_enabled:q('#memory-semantic').checked,fallback_to_fts:q('#memory-fts').checked,extraction_model:root.LAEWUI.memoryModelSelection(selected)}});report('Memory settings saved.');
      }catch(error){report(error);}finally{event.submitter.disabled=false;}
    });
    q('#memory-analyze').addEventListener('click',async()=>{try{const id=app.conversation();if(!id)throw new Error('Open a saved conversation first.');q('#memory-project').value=app.project() || '';const data=await action('analyze',{conversation_id:id,project_id:app.project(),selection:app.selection()});report(data.message);}catch(error){report(error);}});
    for(const name of ['sync','rebuild'])q('#memory-'+name).addEventListener('click',async()=>{try{if(name==='rebuild'&&!window.confirm('Rebuild only the Long-Term Memory semantic index from SQLite?'))return;const data=await action(name);report(data.message);}catch(error){report(error);}});
    return {refresh,projectMenu,openProject};
  }
  root.LAEWSettings={create};
})(window);
