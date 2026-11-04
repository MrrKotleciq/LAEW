/* Review is a user action. This client never approves proposals in the background. */
(function(root){
  'use strict';
  const reviewable=row=>['pending_review','pending','deferred','failed'].includes(row.status);
  function selectionForApproval(rows,selected){
    return rows.filter(row=>selected.get(row.id)===row.version&&reviewable(row)&&!row.needs_target_decision).map(row=>({id:row.id,version:row.version}));
  }
  function create(app){
    const q=selector=>document.querySelector(selector),drawer=q('#knowledge-review');
    let scope=app.project(),requestId=0,previewId=0,rows=[],selected=new Map(),reviewed=new Map(),preview=null,dirty=false,busy=false;
    const report=message=>{q('#knowledge-result').textContent=message;q('#knowledge-settings-result').textContent=message;};
    async function request(action,body){
      const project=app.project();
      const url='/api/knowledge/'+action+(body===undefined&&project?'?'+new URLSearchParams({project_id:project}):'');
      const response=await fetch(url,body===undefined?{cache:'no-store'}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project_id:project,...body})});
      const data=await response.json();if(!response.ok)throw new Error(data.error || 'Knowledge operation failed.');return data;
    }
    function close(){drawer.hidden=true;q('#knowledge-toggle').setAttribute('aria-expanded','false');q('#knowledge-toggle').focus();}
    function open(){drawer.hidden=false;q('#knowledge-toggle').setAttribute('aria-expanded','true');q('#knowledge-close').focus();refresh();}
    function clearPreview(){preview=null;dirty=false;q('#knowledge-preview').hidden=true;q('#knowledge-editor').value='';}
    function renderRows(){
      const list=q('#knowledge-list');list.replaceChildren();
      for(const row of rows){
        const article=document.createElement('article');article.className='knowledge-proposal';
        const title=document.createElement('h3');title.textContent=row.title;
        const summary=document.createElement('p');summary.textContent=row.summary || '';
        const status=document.createElement('p');status.className='muted-note';status.textContent=[row.proposal_type || row.operation,row.status,row.index_status,row.error].filter(Boolean).join(' · ');
        const controls=document.createElement('div');controls.className='settings-actions';
        if(reviewable(row)){
          const label=document.createElement('label'),checkbox=document.createElement('input');checkbox.type='checkbox';checkbox.checked=selected.has(row.id);checkbox.disabled=busy || reviewed.get(row.id)!==row.version || !!row.needs_target_decision;checkbox.addEventListener('change',()=>{if(checkbox.checked)selected.set(row.id,row.version);else selected.delete(row.id);updateBatch();});label.append(checkbox,document.createTextNode(' Select '+row.title));controls.append(label);
        }
        const button=document.createElement('button');button.type='button';button.textContent='Preview & review';button.disabled=busy;button.addEventListener('click',()=>showPreview(row));controls.append(button);
        article.append(title,summary,status,controls);list.append(article);
      }
      if(!rows.length){const empty=document.createElement('p');empty.textContent='No knowledge proposals in this scope.';list.append(empty);}updateBatch();
    }
    function updateBatch(){q('#knowledge-approve-selected').disabled=busy || !selectionForApproval(rows,selected).length;}
    async function refresh(){
      const id=++requestId,project=app.project();
      if(project!==scope){scope=project;selected.clear();reviewed.clear();clearPreview();rows=[];renderRows();q('#knowledge-count').textContent='…';}
      try{
        const data=await request('state');if(id!==requestId||project!==app.project())return;
        rows=data.proposals || [];selected=new Map(selectionForApproval(rows,selected).map(row=>[row.id,row.version]));
        q('#knowledge-count').textContent=String(rows.filter(row=>['pending','pending_review'].includes(row.status)).length);
        q('#knowledge-summary').textContent=rows.filter(reviewable).length+' proposals awaiting review · '+(project?'Project '+project:'General Chat');
        if(!q('#knowledge-settings-form').contains(document.activeElement)){
          q('#knowledge-enabled').checked=data.settings.extraction_enabled;q('#knowledge-interval').value=data.settings.interval_completed_turns;
          q('#knowledge-model-source').value=data.settings.model_source || 'memory';
        }
        const model=data.extraction_model;q('#knowledge-model').textContent=model?((model.provider || '')+' · '+model.model):'Analysis is waiting for an available model.';
        q('#knowledge-status').textContent=JSON.stringify(data.status,null,2);
        renderRows();
      }catch(error){if(id===requestId){q('#knowledge-count').textContent='?';report(error.message);}}
    }
    async function showPreview(row){
      if(dirty){report('Save the current draft before opening another proposal.');return;}
      const project=app.project(),id=++previewId;
      try{
        const data=await request('preview',{id:row.id});if(id!==previewId||project!==app.project())return;
        preview={...row,...(data.proposal || {}),...data};dirty=false;
        q('#knowledge-preview').hidden=false;q('#knowledge-preview-title').textContent=preview.title;
        q('#knowledge-path').textContent=preview.target_path || preview.target || preview.path || '';
        q('#knowledge-editor').value=preview.markdown || preview.content || '';
        q('#knowledge-diff').textContent=typeof preview.diff==='string'?preview.diff:JSON.stringify(preview.diff || '',null,2);
        q('#knowledge-sources').textContent=JSON.stringify(preview.sources || [],null,2);
        q('#knowledge-rendered').replaceChildren();root.LAEWMarkdown.renderMarkdown(q('#knowledge-rendered'),q('#knowledge-editor').value);
        q('#knowledge-editor').disabled=!reviewable(preview);q('#knowledge-save').disabled=!reviewable(preview);
        for(const name of ['approve','reject','defer'])q('#knowledge-'+name).disabled=!reviewable(preview);
        q('#knowledge-stale').textContent=preview.stale?'This document changed. Prepare and review a fresh proposal before approval.':'';
        q('#knowledge-approve').disabled=!reviewable(preview)||!!preview.stale||!!preview.needs_target_decision;
        q('#knowledge-matches').hidden=!preview.needs_target_decision;
        q('#knowledge-match-list').textContent=(preview.matches || []).map(match=>match.target).join('\n');
        const targets=q('#knowledge-destination');targets.replaceChildren();
        const option=(value,label)=>{const item=document.createElement('option');item.value=value;item.textContent=label;targets.append(item);};
        option('','Choose a destination');option('create','Create a distinct note at the proposed path');
        for(const match of preview.matches || [])option(match.target,'Update '+match.target);
        targets.value='';
        if(!preview.stale && !preview.needs_target_decision)reviewed.set(preview.id,preview.version);
        renderRows();q('#knowledge-preview-title').focus();
      }catch(error){report(error.message);}
    }
    async function run(button,action){
      if(busy)return;busy=true;button.disabled=true;updateBatch();
      try{await action();}catch(error){report(error.message);}finally{busy=false;button.disabled=false;updateBatch();}
    }
    q('#knowledge-toggle').addEventListener('click',()=>drawer.hidden?open():close());
    q('#knowledge-open-settings').addEventListener('click',open);
    q('#knowledge-close').addEventListener('click',close);
    document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!drawer.hidden){event.preventDefault();close();}});
    q('#knowledge-editor').addEventListener('input',()=>{dirty=true;q('#knowledge-approve').disabled=true;});
    q('#knowledge-destination').addEventListener('change',()=>{dirty=true;q('#knowledge-approve').disabled=true;});
    q('#knowledge-save').addEventListener('click',event=>run(event.currentTarget,async()=>{
      if(!preview)return;
      const destination=q('#knowledge-destination').value,choice={};
      if(preview.needs_target_decision){if(!destination)throw new Error('Choose a distinct note or an existing document to update.');choice.kind=destination==='create'?'create':'update';if(choice.kind==='update')choice.target=destination;}
      await request('edit',{id:preview.id,version:preview.version,content:q('#knowledge-editor').value,...choice});dirty=false;const id=preview.id;await refresh();const row=rows.find(row=>row.id===id);if(row)await showPreview(row);report('Draft saved. Review the updated preview before approval.');
    }));
    for(const action of ['approve','reject','defer'])q('#knowledge-'+action).addEventListener('click',event=>run(event.currentTarget,async()=>{
      if(!preview)return;if(dirty)throw new Error('Save the edited draft before deciding.');
      const result=await request('decide',{id:preview.id,version:preview.version,action});clearPreview();await refresh();report(result.message || 'Proposal '+(result.status || action)+'.');
    }));
    q('#knowledge-approve-selected').addEventListener('click',event=>run(event.currentTarget,async()=>{
      if(dirty)throw new Error('Save the edited draft before batch approval.');
      const project=app.project(),approvals=selectionForApproval(rows,selected);let completed=0;const errors=[];
      for(const row of approvals){if(app.project()!==project){errors.push('Review scope changed; remaining approvals stopped.');break;}try{await request('decide',{...row,project_id:project,action:'approve'});selected.delete(row.id);completed++;}catch(error){errors.push(error.message);}}
      clearPreview();await refresh();report(completed+' proposals processed.'+(errors.length?' '+errors.join(' · '):''));
    }));
    q('#knowledge-settings-form').addEventListener('submit',event=>{event.preventDefault();run(event.submitter,async()=>{
      await request('settings',{settings:{extraction_enabled:q('#knowledge-enabled').checked,interval_completed_turns:Number(q('#knowledge-interval').value),model_source:q('#knowledge-model-source').value}});await refresh();report('Knowledge settings saved.');
    });});
    q('#knowledge-analyze').addEventListener('click',event=>run(event.currentTarget,async()=>{
      const id=app.conversation();if(!id)throw new Error('Open a saved conversation first.');const result=await request('analyze',{conversation_id:id});await refresh();report(result.message || 'Analysis queued.');
    }));
    q('#knowledge-sync').addEventListener('click',event=>run(event.currentTarget,async()=>{const result=await request('sync',{});await refresh();report(result.message || 'Index retry queued.');}));
    q('#settings-refresh').addEventListener('click',refresh);
    return {refresh,open,close};
  }
  const api={create,selectionForApproval,reviewable};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  if(root)root.LAEWKnowledge=api;
})(typeof window==='undefined'?null:window);
