(() => {
  const q = (selector) => document.querySelector(selector);
  const conversation = q('#conversation');
  const form = q('#composer');
  const input = q('#message');
  const send = q('#send');
  const provider = q('#provider');
  const projectList = q('#project-list');
  const projectError = q('#project-error');
  const state = q('#state');
  const panel = q('#panel');
  const dialog = q('#project-dialog');
  const projectForm = q('#project-form');
  const projectNameInput = q('#project-name');
  let latest = { steps: [] };
  const panelState = window.LAEWUI.createPanelState();
  let activeTab = panelState.active;
  let panelBody = panel;
  let submitting = false;
  let switchingProject = false;
  let creatingProject = false;
  let currentProjectId = null;
  let currentConversationId = null;
  let draftId = crypto.randomUUID();
  let openingConversation = false;
  let projectItems = [];
  let conversationItems = [];
  let conversationsRequest = 0;
  let statusRequest = 0;
  let activeController = null;
  let activeRunId = null;
  let stoppingRunId = null;
  let activeAssistant = null;
  let streamedResponse = '';
  const sessionId = crypto.randomUUID();
  const initialEmpty = q('.empty')?.cloneNode(true);
  const emptyForScope = () => {
    const empty = initialEmpty.cloneNode(true);
    if (currentProjectId === null) {
      empty.querySelector('h2').textContent = 'Start a general conversation';
      empty.querySelector('p').textContent = 'Ask the Chief Agent a question or explore Global Knowledge.';
      empty.querySelector('.suggestions')?.remove();
    }
    return empty;
  };
  const isCloud = () => ['openai-api', 'chatgpt', 'gemini'].includes(provider.value);
  const localViews = new Map();
  const drafts = new Map();
  let activeView = null;
  let authAttempt = null;
  const cloudFields = () => ({provider: provider.value, model: q('#cloud-model').value.trim(),
    account_id: q('#cloud-account').value || null, session_id: sessionId, project_id: currentProjectId});
  const viewKey = () => JSON.stringify([sessionId, currentProjectId, currentConversationId || draftId]);
  function saveLocalView() {
    if (activeView) localViews.set(activeView.key, {nodes: Array.from(conversation.childNodes), latest: {...latest}});
  }
  async function changeView() {
    const key = viewKey();
    if (activeView?.key === key) return;
    if (activeView) drafts.set(activeView.key, input.value);
    saveLocalView();
    activeView = {key, cloud: isCloud()};
    input.value = drafts.get(key) || '';
    activeAssistant = null; streamedResponse = '';
    latest = {steps: [], provider: latest.provider, model: latest.model, project: latest.project,
      project_path: latest.project_path, projects_root: latest.projects_root, knowledge_root: latest.knowledge_root,
      projectSettings: latest.projectSettings, rag: latest.rag};
    conversation.replaceChildren();
    const saved = localViews.get(key);
    if (saved) { conversation.append(...saved.nodes); latest = {...saved.latest, ...latest}; }
    else conversation.append(emptyForScope());
    render();
    knowledgeUI.refresh();
  }
  const services = q('#services-view');
  const manageProvider = q('#service-provider');
  const manageAccount = q('#manage-account');
  const catalogs = new Map();
  const connectionStates = new Map();
  const providerLabels = {manifest:'Local · Manifest', 'llama.cpp':'Local · llama.cpp', 'openai-api':'OpenAI API', chatgpt:'ChatGPT OAuth', gemini:'Google AI Studio'};
  let credentialStatus = {};
  let catalogRequest = 0;
  function showPage(name) {
    q('#chat-view').hidden = name !== 'chat'; services.hidden = name !== 'models'; q('#settings-view').hidden = name !== 'settings';
    q('.shell').classList.toggle('services-open', name !== 'chat');
    for (const page of ['chat','models','settings']) {
      const button = q('#nav-' + page), selected = name === page;
      button.classList.toggle('active', selected);
      if (selected) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current');
    }
    closeSidebar();
    applySidebarWidth();
    if (name === 'models') refreshServices();
    if (name === 'settings') { settingsUI.refresh(); knowledgeUI.refresh(); }
  }
  function updateMode() {
    q('#session-mode').textContent = isCloud() ? 'CLOUD MODEL · LAEW TOOLS' : 'LOCAL MODEL · LAEW TOOLS';
    updateModelPicker();
  }
  const catalogKey = (type, account = '') => JSON.stringify([type, account]);
  async function cloudPost(route, body = {}) {
    const response = await fetch(route, {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({...cloudFields(), provider:manageProvider.value, account_id:manageAccount.value || null, ...body})});
    const data = await readJson(response);
    if (!response.ok) throw new Error(data.error || 'Connection request failed.');
    return data;
  }
  function statusLabel(type) {
    if(type==='openai-api' && !credentialStatus.api_key_configured) return 'API key required';
    if(type==='gemini' && !credentialStatus.gemini_api_key_configured) return 'API key required';
    if(type==='chatgpt' && !(credentialStatus.accounts || []).some(a=>a.authenticated)) return 'Sign-in required';
    if (connectionStates.has(type)) return connectionStates.get(type);
    if (type === 'openai-api') return credentialStatus.api_key_configured ? 'API key configured · not tested' : 'API key required';
    if (type === 'gemini') return credentialStatus.gemini_api_key_configured ? 'API key configured · not tested' : 'API key required';
    if (type === 'chatgpt') return (credentialStatus.accounts || []).some(a => a.authenticated) ? 'Authorized account · not tested' : 'Sign-in required';
    return 'Connection not tested';
  }
  function drawProviderCards() {
    q('#provider-cards').replaceChildren();
    Object.entries(providerLabels).forEach(([type,label]) => {
      const card = document.createElement('article'); card.className = 'provider-card';
      const title = document.createElement('h2'); title.textContent = label;
      const status = document.createElement('p'); status.className = 'connection-status'; status.textContent = statusLabel(type);
      const auth = document.createElement('p'); auth.textContent = 'Authentication: ' + (type === 'chatgpt' ? 'ChatGPT OAuth' : ['gemini','openai-api'].includes(type) ? 'API key' : 'Local backend');
      const count = document.createElement('p');
      const entries = [...catalogs.entries()].filter(([key]) => JSON.parse(key)[0] === type);
      count.textContent = entries.length ? 'Catalog models: ' + new Set(entries.flatMap(([,models]) => models.map(m => m.id))).size : 'Models: load catalog to check';
      const button = document.createElement('button'); button.type = 'button'; button.textContent = 'Manage';
      button.addEventListener('click', () => { manageProvider.value = type; updateServiceEditor(); q('#manage-title').scrollIntoView({block:'nearest'}); });
      card.append(title,status,auth,count,button); q('#provider-cards').append(card);
    });
  }
  function updateServiceEditor() {
    const type = manageProvider.value, oauth = type === 'chatgpt';
    catalogRequest++;
    q('#api-key').value = ''; q('#service-model').value = '';
    q('#key-form').hidden = !['gemini','openai-api'].includes(type);
    q('#manage-account-label').hidden = !oauth; q('#cloud-login').hidden = !oauth; q('#cloud-logout').hidden = !oauth;
    q('#local-endpoint-note').hidden = !['manifest','llama.cpp'].includes(type);
    q('#cloud-auth-state').textContent = statusLabel(type);
    q('#services-message').textContent = type === 'gemini' ? 'Free Tier and limits depend on your Google AI Studio project. No paid model fallback is enabled.' : '';
    drawCatalog(catalogs.get(catalogKey(type, oauth ? manageAccount.value : '')) || []);
  }
  async function refreshServices() {
    try {
      const response = await fetch('/api/cloud/status?session_id=' + encodeURIComponent(sessionId), {cache:'no-store'});
      if (!response.ok) throw new Error('Could not load authentication status.');
      credentialStatus = await readJson(response);
      for(const key of catalogs.keys()){const [type,account]=JSON.parse(key);if(type==='chatgpt' && !(credentialStatus.accounts || []).some(a=>a.id===account && a.authenticated)) catalogs.delete(key);}
      const selected = manageAccount.value; manageAccount.replaceChildren(new Option('Choose or add an account',''));
      (credentialStatus.accounts || []).forEach(a => manageAccount.add(new Option(a.label + (a.authenticated ? '' : ' · signed out'),a.id)));
      if ((credentialStatus.accounts || []).some(a => a.id === selected)) manageAccount.value = selected;
      if (authAttempt) {
        const attempt = (credentialStatus.attempts || []).find(a => a.id === authAttempt);
        if (attempt && !['pending','validating'].includes(attempt.state)) {
          authAttempt = null; q('#cloud-auth-cancel').hidden = true;
          if (attempt.state === 'connected') manageAccount.value = attempt.account_id;
          else q('#services-message').textContent = attempt.error || 'Sign-in was not completed.';
        }
      }
      drawProviderCards(); q('#cloud-auth-state').textContent = credentialStatus.auth_error && manageProvider.value === 'chatgpt' ? credentialStatus.auth_error : statusLabel(manageProvider.value);
    } catch(error) { q('#services-message').textContent = error.message; }
  }
  function drawCatalog(models) {
    q('#cloud-models').replaceChildren(); q('#model-catalog').replaceChildren();
    models.forEach(model => {
      const option = new Option(model.label || model.id,model.id); q('#cloud-models').append(option);
      const item = document.createElement('li'); item.textContent = model.label || model.id; q('#model-catalog').append(item);
    });
  }
  function updateModelPicker() {
    const select = q('#active-model'); select.replaceChildren(new Option('Manifest default',''));
    for (const entry of window.LAEWUI.modelGroups([...catalogs],providerLabels,credentialStatus.accounts || [])) {
      const group=document.createElement('optgroup'); group.label=entry.label;
      entry.options.forEach(option=>group.append(new Option(option.label,option.value)));select.append(group);
    }
    const current = JSON.stringify([provider.value,q('#cloud-model').value,q('#cloud-account').value]);
    if (q('#cloud-model').value) {
      if (!Array.from(select.options).some(o=>o.value === current)) select.append(new Option(q('#cloud-model').value + ' · ' + (providerLabels[provider.value] || provider.value),current));
      select.value = current;
    } else select.value = '';
    select.disabled = submitting;
  }
  async function loadCloudModels() {
    const type=manageProvider.value, account=type==='chatgpt' ? manageAccount.value : '', request=++catalogRequest;
    q('#services-message').textContent = 'Testing connection and loading the model catalog…';
    const params = new URLSearchParams({provider:type,account_id:account,session_id:sessionId});
    try {
      const response = await fetch('/api/cloud/models?' + params,{cache:'no-store'}); const data=await readJson(response);
      if (!response.ok) throw new Error(data.error || 'Cannot load models.');
      catalogs.set(catalogKey(type,account),data.models); connectionStates.set(type,'Last catalog check succeeded · inference not tested');
      if (request===catalogRequest) { drawCatalog(data.models); q('#services-message').textContent = `Loaded ${data.models.length} models. Model capabilities are validated on use.`; }
      drawProviderCards(); updateModelPicker();
    } catch(error) { connectionStates.set(type,'Connection check failed'); drawProviderCards(); if(request===catalogRequest) q('#services-message').textContent=error.message; }
  }
  async function activateModel(type,model,account='') {
    if (submitting || switchingProject || creatingProject) return;
    provider.value=type; q('#cloud-model').value=model;
    q('#cloud-account').replaceChildren(new Option(account,account)); q('#cloud-account').value=account;
    await loadStatus();
  }
  q('#active-model').addEventListener('change', async () => {
    const value=q('#active-model').value;
    if(value) await activateModel(...JSON.parse(value)); else await activateModel('manifest','');
  });
  q('#nav-chat').addEventListener('click',()=>showPage('chat'));
  q('#nav-models').addEventListener('click',()=>showPage('models'));
  q('#chat-permission-mode').addEventListener('change',async()=>{
    const project=currentProjectId,select=q('#chat-permission-mode');select.disabled=true;
    try{const response=await fetch('/api/project/permissions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project_id:project,permission_mode:select.value})});const data=await readJson(response);if(!response.ok)throw new Error(data.error || 'Could not save permissions.');}
    catch(error){setState(error.message,'error');}finally{await refreshProjectSettings();select.disabled=false;}
  });
  q('#nav-settings').addEventListener('click',()=>showPage('settings'));
  q('#services-refresh').addEventListener('click',refreshServices);
  manageProvider.addEventListener('change',updateServiceEditor);
  manageAccount.addEventListener('change',updateServiceEditor);
  q('#use-model').addEventListener('click',async()=>{
    const model=q('#service-model').value.trim(); if(!model) { q('#services-message').textContent='Choose an exact model ID first.';return; }
    await activateModel(manageProvider.value,model,manageProvider.value==='chatgpt'?manageAccount.value:''); showPage('chat');
  });
  q('#key-form').addEventListener('submit',async event=>{
    event.preventDefault(); const field=q('#api-key'), value=field.value; field.value='';
    const button=q('#key-form button'); button.disabled=true;
    try { const data=await cloudPost('/api/cloud/key',{api_key:value}); connectionStates.delete(manageProvider.value); await refreshServices(); q('#services-message').textContent=data.message; }
    catch(error){q('#services-message').textContent=error.message;}
    finally{button.disabled=false;}
  });
  q('#theme').value=window.LAEWTheme.preference;
  q('#theme').addEventListener('change',()=>window.LAEWTheme.set(q('#theme').value));

  const setState = (text, kind = '') => { state.textContent = text; state.className = kind; };
  const setProjectBusy = (busy) => {
    q('#new-project').disabled = busy;
    q('#refresh-projects').disabled = busy;
    projectList.querySelectorAll('button').forEach((button) => { button.disabled = busy || button.dataset.unavailable === 'true'; });
    q('#sidebar-new-chat').disabled = busy;
    q('#chat-permission-mode').disabled = busy;
  };
  const clearConversation = () => {
    conversation.replaceChildren(emptyForScope());
    latest.steps = [];
    latest.error = null;
    panelState.reset(); render('context');
  };

  const addMessage = (role, text, kind = '') => {
    const followOutput = conversation.scrollHeight - conversation.scrollTop - conversation.clientHeight < 48;
    q('.empty')?.remove();
    const article = document.createElement('article');
    article.className = `message ${role} ${kind}`;
    const label = document.createElement('div');
    label.textContent = role === 'user' ? 'YOU' : 'CHIEF AGENT';
    const content = document.createElement(role === 'assistant' && !kind ? 'div' : 'pre');
    content.className = 'message-body';
    if (role === 'assistant' && !kind) window.LAEWMarkdown.renderMarkdown(content, text);
    else content.textContent = text;
    article.append(label, content);
    conversation.append(article);
    if (followOutput) conversation.scrollTop = conversation.scrollHeight;
    return { article, content };
  };
  const panelHeading = (title) => {
    const heading = document.createElement('h2'); heading.textContent = title; const card = document.createElement('section'); card.className = 'context-card'; card.append(heading); panel.append(card); panelBody = card;
  };
  const panelNote = (text) => {
    const note = document.createElement('p'); note.textContent = text; panelBody.append(note);
  };
  function render(tab = activeTab) {
    activeTab = panelState.select(tab);
    document.querySelectorAll('.tab').forEach(button => {
      const selected=button.dataset.tab === activeTab;
      button.classList.toggle('active',selected); button.setAttribute('aria-selected',String(selected)); button.tabIndex=selected?0:-1;
    });
    panel.setAttribute('aria-labelledby','tab-'+activeTab);
    panel.replaceChildren(); panelBody=panel;
    if (tab === 'context') {
      panelHeading(currentProjectId ? 'Active project' : 'General Chat');
      const details = document.createElement('dl');
      [['Project', currentProjectId ? (latest.project || projectItems.find(item=>item.id===currentProjectId)?.name) : 'None'], ['Provider', latest.provider], ['Model', latest.model]].forEach(([label, value]) => {
        const term = document.createElement('dt'); term.textContent = label;
        const description = document.createElement('dd'); description.textContent = value || 'Unavailable';
        details.append(term, description);
      });
      panelBody.append(details);
      const paths=document.createElement('details'), summary=document.createElement('summary'); summary.textContent='Workspace paths'; paths.append(summary);
      [['Project',latest.project_path],['Projects root',latest.projects_root],['Global Knowledge',latest.knowledge_root]].forEach(([label,value])=>{if(value){const p=document.createElement('p');p.textContent=label+': '+value;paths.append(p);}});panelBody.append(paths);
      panelNote(currentProjectId ? 'LAEW tools use this project’s permissions.' : 'Global Knowledge is available; project tools and Project Memory are unavailable.');

      panelHeading('Knowledge routing'); renderRouting();
      panelHeading('Retrieved knowledge'); renderSources();
      panelHeading('Last response usage');
      if (latest.usage) panelNote(`Input: ${latest.usage.prompt_tokens ?? 'unavailable'} · Output: ${latest.usage.completion_tokens ?? 'unavailable'} tokens`);
      else panelNote('Token usage is reported after a response. Context capacity is not reported.');
      if (currentProjectId) {
      panelHeading('Project settings');
      panelNote('Documentation language: '+(latest.projectSettings?.documentation_language || 'checking…'));
      const settingsButton=document.createElement('button');settingsButton.type='button';settingsButton.textContent='Open project settings';settingsButton.addEventListener('click',()=>settingsUI.openProject(currentProjectId));panelBody.append(settingsButton);
      }
      panelHeading('Long-Term Memory');
      if (latest.memories?.length) latest.memories.forEach(memory=>panelNote(`${memory.scope === 'user' ? 'User Memory' : 'Project Memory'} · ${memory.content}`));
      else panelNote(latest.memoryMode === 'unavailable' ? 'Memory is unavailable for this turn.' : 'No memories used for this turn.');
      panelHeading('Knowledge');
      if (!latest.rag) panelNote('Checking synchronization status…');
      else if (latest.rag.error) panelNote(latest.rag.error);
      else ['project', 'global'].forEach((scope) => {
        const status = latest.rag[scope];
        if (!status) return;
        panelNote(scope === 'project' ? 'Project Memory' : 'Global Knowledge');
        panelNote(`Synchronization: ${status.state} · Last success: ${status.last_success || 'Not recorded'}`);
        if (status.error) panelNote(status.error);
        const button = document.createElement('button');
        button.type = 'button'; button.textContent = `Sync ${scope}`;
        button.addEventListener('click', async () => {
          try {
            const response = await fetch('/api/rag/sync', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({scope})});
            const payload = await readJson(response);
            if (!response.ok) throw new Error(payload.error || 'Synchronization could not start.');
            await refreshRag();
          } catch (error) { panelNote(error.message); }
        });
        panelBody.append(button);
      });
    } else if (tab === 'run') {
      panelHeading('Current run');
      renderRouting();
      const steps = Array.isArray(latest.steps) ? latest.steps : [];
      if (!steps.length) panelNote(latest.error || 'No tool activity for this response.');
      else {
        const list = document.createElement('ol');
        steps.forEach((step) => {
          const item = document.createElement('li'); item.className='tool-card';
          const badge=document.createElement('span'); badge.className='status-badge'; badge.textContent=step.status || (step.success === true ? 'Completed' : step.success === false ? (/denied|blocked/i.test(step.error || '') ? 'Denied' : 'Failed') : 'Status unavailable'); item.append(badge);
          const title = document.createElement('b'); title.textContent = step.tool || 'Response'; item.append(title);
          if (step.operation) item.append(document.createTextNode(` · ${step.operation}`));
          if (step.error) { const error = document.createElement('em'); error.textContent = step.error; item.append(error); }
          list.append(item);
        });
        panelBody.append(list);
      }
    } else {
      panelHeading('Sources');
      renderSources();
    }
  }
  function renderRouting() {
    const routing = latest.routing;
    if (!routing) { panelNote('No routing information for this turn.'); return; }
    const labels = {global: 'Global Knowledge', project: 'Project Knowledge', hybrid: 'Both scopes'};
    const selected = routing.scopes.map(scope => labels[scope]);
    panelNote(`${routing.reason} · ${selected.join(', ') || 'No RAG scope'} · ${routing.routing_ms} ms`);
    panelNote(`Memory Recall: ${routing.memory}`);
    for (const [label, searches] of [['Automatic prefetch', routing.prefetch], ['RagTool follow-up', routing.follow_up]]) {
      if (!searches.length) panelNote(`${label}: none`);
      for (const search of searches) {
        const timing = search.elapsed_ms == null ? '' : ` · ${search.elapsed_ms} ms`;
        const duplicates = search.duplicates_omitted ? ` · ${search.duplicates_omitted} duplicate(s) omitted` : '';
        panelNote(`${label} · ${labels[search.scope] || search.scope}: ${search.status} · ${search.chunks} fragments${timing}${duplicates}`);
        if (search.error) panelNote(search.error);
      }
    }
  }
  function renderSources() {
    const searches = latest.routing?.prefetch || [];
    const sources = [...new Set([...searches, ...(latest.steps || [])].flatMap(item => item.sources || []))];
    if(!sources.length) panelNote('No sources used for this response.');
    sources.forEach(source=>{
      const note=document.createElement('p'); note.className='source-item';
      const label=source.startsWith('@project')?'Project Memory':source.startsWith('@knowledge')?'Global Knowledge':/^https?:/.test(source)?'Web source':'Retrieved source';
      note.textContent=label+' · '+source;panelBody.append(note);
    });
    (latest.steps || []).filter(step=>step.tool==='FilesystemTool' && step.operation==='view_file' && step.success===true).forEach(()=>panelNote('Source includes a direct file read.'));
  }
  async function readJson(response) {
    const text = await response.text();
    try { return text ? JSON.parse(text) : {}; }
    catch { throw new Error(`The local API returned invalid JSON (${response.status}).`); }
  }
  async function conversationPost(path, body) {
    const response = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    const data = await readJson(response);
    if (!response.ok) throw new Error(data.error || 'Conversation operation failed.');
    return data;
  }
  const storage = {
    get(key) { try { return localStorage.getItem(key); } catch { return null; } },
    set(key, value) { try { localStorage.setItem(key, value); } catch {} }
  };
  const expansion = window.LAEWUI.createExpansionState(storage);
  const activeConversationKey = 'laew-active-conversation';
  const saveActiveConversation = () => storage.set(activeConversationKey, currentConversationId || '');
  const projectsToggle = q('#projects-toggle'), projectsContent = q('#projects-content');
  function setProjectsExpanded(expanded) {
    projectsContent.hidden = !expanded;
    projectsToggle.setAttribute('aria-expanded', String(expanded));
    projectsToggle.querySelector('.projects-chevron').textContent = expanded ? '▾' : '▸';
    expansion.setProjects(expanded);
  }
  setProjectsExpanded(expansion.projectsExpanded);
  projectsToggle.addEventListener('click', () => setProjectsExpanded(projectsContent.hidden));
  const menu = q('#conversation-menu');
  let menuItem = null, menuTrigger = null;
  function closeConversationMenu(restoreFocus = false) {
    menu.hidden = true; menuItem = null;
    if (restoreFocus && menuTrigger?.isConnected) menuTrigger.focus();
    menuTrigger = null;
  }
  function showConversationMenu(item, x, y, trigger) {
    menuItem = item; menuTrigger = trigger; menu.hidden = false;
    menu.style.left = '0px'; menu.style.top = '0px';
    const rect=menu.getBoundingClientRect();
    menu.style.left = Math.max(4, Math.min(x, window.innerWidth-rect.width-4))+'px';
    menu.style.top = Math.max(4, Math.min(y, window.innerHeight-rect.height-4))+'px';
    menu.querySelector('button').focus();
  }
  menu.addEventListener('keydown', event => {
    if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); closeConversationMenu(true); }
    if (['ArrowDown','ArrowUp','Home','End'].includes(event.key)) {
      event.preventDefault(); const buttons=Array.from(menu.querySelectorAll('button')); const index=buttons.indexOf(document.activeElement);
      buttons[event.key==='Home'?0:event.key==='End'?buttons.length-1:(index+(event.key==='ArrowDown'?1:-1)+buttons.length)%buttons.length].focus();
    }
  });
  document.addEventListener('pointerdown', event => { if (!menu.hidden && !menu.contains(event.target)) closeConversationMenu(); });
  menu.addEventListener('click', async event => {
    const action=event.target.closest('[data-action]')?.dataset.action, item=menuItem;
    if (!action || !item) return;
    closeConversationMenu(true);
    if (action === 'rename') {
      const title=window.prompt('Conversation title (1–200 characters)', item.title);
      if (title === null) return;
      if (!title.trim() || title.length > 200) { setState('Title must contain 1–200 characters.', 'error'); return; }
      try { await conversationPost('/api/conversation/rename', {id:item.id, title:title.trim()}); await refreshConversations(); }
      catch (error) { setState(error.message, 'error'); }
    } else if (action === 'delete' && window.confirm(`Delete conversation “${item.title}”?`)) {
      try {
        await conversationPost('/api/conversation/delete', {id:item.id});
        if (currentConversationId === item.id) { currentConversationId=null; saveActiveConversation(); draftId=crypto.randomUUID(); await changeView(); }
        await refreshConversations();
      } catch (error) { setState(error.message, 'error'); }
    }
  });
  async function refreshConversations() {
    const request=++conversationsRequest;
    try {
      const response = await fetch('/api/conversations', {cache:'no-store'});
      const data = await readJson(response);
      if (!response.ok) throw new Error(data.error || 'Unable to load conversations.');
      if (request !== conversationsRequest) return;
      conversationItems = Array.isArray(data.conversations) ? data.conversations : [];
      drawProjectList();
    } catch (error) { if (request === conversationsRequest) setState(error.message, 'error'); }
  }
  async function openConversation(id, restore = false) {
    if (submitting || switchingProject || creatingProject || openingConversation) return;
    openingConversation = true; setProjectBusy(true); send.disabled = true; input.disabled = true;
    try {
      const response = await fetch('/api/conversation?id='+encodeURIComponent(id), {cache:'no-store'});
      const data = await readJson(response);
      if (!response.ok) throw new Error(data.error || 'Conversation unavailable.');
      if (data.project_id !== currentProjectId) {
        await switchProject(data.project_id, true);
        if (currentProjectId !== data.project_id) throw new Error('Conversation project is unavailable.');
      }
      currentConversationId = id; saveActiveConversation();
      const groupKey=data.scope_type === 'general' ? 'general' : 'project:'+data.project_id;
      expansion.revealConversation(groupKey, restore);
      if (!restore && projectsContent.hidden) setProjectsExpanded(true);
      showPage('chat'); closeSidebar();
      await changeView();
      conversation.replaceChildren();
      const finished = new Set(data.events.filter(e=>e.kind==='run' && e.status==='completed').map(e=>e.run_id));
      for (const event of data.events) {
        if (event.kind === 'user' && !event.generated) addMessage('user', event.content);
        if (event.kind === 'assistant' && finished.has(event.run_id) && !event.message?.tool_calls?.length && !event.content.includes('```tool_call')) addMessage('assistant', event.content);
      }
      const lastRunId = [...data.events].reverse().find(event=>event.kind==='run')?.run_id;
      latest.steps = data.events.filter(event=>event.kind==='tool_result' && event.run_id===lastRunId).map(event=>({
        tool:event.tool, operation:event.operation, call_id:event.call_id,
        success:event.status==='completed', status:event.status,
        error:event.status==='completed' ? null : event.content.slice(0, 300),
      }));
      render();
      if (!conversation.childNodes.length) conversation.append(emptyForScope());
      const runs = new Map();
      data.events.filter(e=>e.kind==='run').forEach(e=>runs.set(e.run_id, e.status));
      if ([...runs.values()].some(status=>status !== 'completed')) setState('This conversation contains an incomplete run.');
      await refreshConversations();
    } catch (error) { setState(error.message, 'error'); }
    finally { openingConversation = false; setProjectBusy(false); send.disabled = false; input.disabled = false; }
  }
  async function refreshProjectSettings() {
    const projectId = currentProjectId;
    if (!projectId) return;
    try {
      const response = await fetch('/api/project/settings', {cache: 'no-store'});
      const payload = await readJson(response);
      if (!response.ok) throw new Error(payload.error || 'Project settings unavailable.');
      if (currentProjectId === projectId && payload.project_id === projectId) { latest.projectSettings = payload; q('#chat-permission-mode').value=payload.permission_mode || 'auto'; }
    } catch (error) {
      if (currentProjectId === projectId) latest.projectSettings = {error: error.message};
    }
    if (activeTab === 'context' && !panel.contains(document.activeElement)) render('context');
  }
  async function refreshRag() {
    const projectId=currentProjectId;
    try { const data=await readJson(await fetch('/api/rag'));if(projectId===currentProjectId) latest.rag=data; }
    catch { if(projectId===currentProjectId) latest.rag = {error: 'Synchronization status is unavailable.'}; }
    if (activeTab === 'context' && !panel.contains(document.activeElement)) render('context');
  }
  refreshRag();
  window.setInterval(refreshRag, 5000);
  function showProjectError(message) {
    projectError.textContent = message || '';
    projectError.hidden = !message;
  }
  function updateProjectHeader(item) {
    const name = item?.name || 'General Chat';
    const path = item?.path || 'Global Knowledge · No active project';
    q('#chat-permissions').hidden=!item;
    q('#active-project-name').textContent = name;
    q('#active-project-name').title = name;
    q('#task-title').textContent = name;
    q('#conversation-description').textContent = item ? 'Investigate, reason, and work with this project through LAEW’s controlled runtime.' : 'Chat with the Chief Agent using Global Knowledge.';
    q('#workspace').textContent = path;
    q('#workspace').title = path;
    q('#active-project-path').textContent = path;
    q('#active-project-path').title = path;
  }
  function drawProjectList() {
    closeConversationMenu(); projectList.replaceChildren();
    q('#project-count').textContent = String(projectItems.length);
    const groups=window.LAEWUI.conversationGroups(projectItems, conversationItems);
    groups.forEach((group, index) => {
      const section=document.createElement('section'); section.className='conversation-group'; section.dataset.groupId=group.key;
      const heading=document.createElement('div'); heading.className='group-heading';
      const expanded=expansion.isExpanded(group.key);
      const toggle=document.createElement('button'); toggle.type='button'; toggle.className='group-toggle';
      const contentsId='project-group-'+index;
      toggle.setAttribute('aria-expanded', String(expanded)); toggle.setAttribute('aria-controls',contentsId);
      toggle.setAttribute('aria-label', `Toggle ${group.name} conversations`);
      toggle.textContent=expanded?'▾':'▸';
      const select=document.createElement('button'); select.type='button'; select.className='group-select';
      const projectId=group.key === 'general' ? null : group.key.slice('project:'.length);
      select.textContent=group.name; select.title=group.name;
      select.disabled=group.unavailable || submitting || switchingProject || creatingProject || openingConversation;
      if (group.unavailable) select.dataset.unavailable='true';
      if (!group.unavailable && projectId === currentProjectId) { select.classList.add('active'); select.setAttribute('aria-current','true'); }
      select.addEventListener('click', () => switchProject(projectId));
      const count=document.createElement('span'); count.className='group-count'; count.textContent=String(group.items.length); count.setAttribute('aria-hidden','true');
      const create=document.createElement('button'); create.type='button'; create.className='group-new-chat'; create.textContent='＋';
      create.setAttribute('aria-label', `New conversation in ${group.name}`); create.title=`New conversation in ${group.name}`;
      create.disabled=select.disabled;
      if (group.unavailable) create.dataset.unavailable='true';
      create.addEventListener('click', async () => {
        if (submitting || switchingProject || creatingProject || openingConversation) return;
        if (projectId !== currentProjectId) await switchProject(projectId);
        if (projectId === currentProjectId) await newConversation();
      });
      heading.append(toggle,select,count,create);
      if (!group.unavailable && projectId !== null) {
        select.addEventListener('contextmenu',event=>{event.preventDefault();settingsUI.projectMenu(projectId,event.clientX,event.clientY,select);});
        select.addEventListener('keydown',event=>{if(event.key==='ContextMenu' || (event.shiftKey && event.key==='F10')){event.preventDefault();const rect=select.getBoundingClientRect();settingsUI.projectMenu(projectId,rect.left,rect.bottom,select);}});
        const config=document.createElement('button');config.type='button';config.className='group-new-chat';config.textContent='⚙';config.title='Project settings';config.setAttribute('aria-label',`Settings for ${group.name}`);config.addEventListener('click',()=>settingsUI.openProject(projectId));heading.append(config);
      }
      section.append(heading);
      const contents=document.createElement('div'); contents.id=contentsId; contents.className='group-contents'; contents.hidden=!expanded;
      toggle.addEventListener('click', () => { const value=contents.hidden; contents.hidden=!value; expansion.setGroup(group.key,value); toggle.setAttribute('aria-expanded',String(value)); toggle.textContent=value?'▾':'▸'; });
      for (const item of group.items) {
        const row=document.createElement('div'); row.className='conversation-row'; row.dataset.conversationId=item.id;
        const open=document.createElement('button'); open.type='button'; open.className='conversation-open'; open.title=item.title;
        open.textContent=item.title; open.classList.toggle('active',item.id===currentConversationId);
        if (item.id===currentConversationId) open.setAttribute('aria-current','true');
        open.disabled=submitting || switchingProject || creatingProject || openingConversation; open.addEventListener('click', () => openConversation(item.id));
        const more=document.createElement('button'); more.type='button'; more.className='conversation-more'; more.textContent='⋯'; more.disabled=open.disabled;
        more.setAttribute('aria-label',`Actions for ${item.title}`); more.setAttribute('aria-haspopup','menu');
        more.addEventListener('click', () => { const rect=more.getBoundingClientRect(); showConversationMenu(item,rect.left,rect.bottom,more); });
        row.addEventListener('contextmenu', event => { if (open.disabled) return; event.preventDefault(); showConversationMenu(item,event.clientX,event.clientY,open); });
        open.addEventListener('keydown', event => { if (event.key==='ContextMenu' || (event.shiftKey && event.key==='F10')) { event.preventDefault(); const rect=open.getBoundingClientRect(); showConversationMenu(item,rect.left,rect.bottom,open); } });
        row.append(open,more); contents.append(row);
      }
      if (!group.items.length) { const empty=document.createElement('p'); empty.className='group-empty'; empty.textContent='No conversations yet'; contents.append(empty); }
      section.append(contents); projectList.append(section);
    });
  }
  async function loadStatus() {
    updateMode(); await changeView();
    if (isCloud()) {
      latest={...latest,provider:provider.value,model:q('#cloud-model').value};
      refreshProjectSettings(); refreshRag(); render();
      q('#runtime').textContent = providerLabels[provider.value] + ' · ' + (q('#cloud-model').value || 'choose a model');
      setState('Connection validated when the model is used.'); updateModelPicker();
      return;
    }
    refreshProjectSettings();
    const requestId = ++statusRequest;
    const selection = provider.value;
    setState('Checking provider…', 'pending');
    try {
      const response = await fetch(`/api/status?provider=${encodeURIComponent(selection)}&model=${encodeURIComponent(q('#cloud-model').value.trim())}&session_id=${encodeURIComponent(sessionId)}`, { cache: 'no-store' });
      const status = await readJson(response);
      if (requestId !== statusRequest || selection !== provider.value) return;
      latest = { ...latest, ...status, steps: latest.steps || [] };
      if (!q('#cloud-model').value && status.model) { q('#cloud-model').value=status.model; updateModelPicker(); }
      q('#runtime').textContent = status.available ? `${status.provider} · ${status.model}` : `Unavailable · ${status.error || 'provider error'}`;
      q('#runtime').className = status.available ? 'ready' : 'problem';
      if (status.project_path) q('#workspace').textContent = status.project_path;
      setState(status.available ? 'Ready' : (status.error || 'Provider unavailable'), status.available ? 'success' : 'error');
    } catch (error) {
      if (requestId !== statusRequest || selection !== provider.value) return;
      latest = { ...latest, error: error.message };
      q('#runtime').textContent = 'Unavailable · local API error'; q('#runtime').className = 'problem';
      setState('Could not contact the local API', 'error');
    }
    render();
  }
  async function refreshProjects() {
    q('#refresh-projects').disabled = true;
    try {
      const response = await fetch('/api/projects', { cache: 'no-store' });
      const payload = await readJson(response);
      if (!response.ok) throw new Error(payload.error || `Project list failed (${response.status}).`);
      projectItems = Array.isArray(payload.projects) ? payload.projects : [];
      const nextProjectId = payload.active_project || null;
      if (currentConversationId && nextProjectId !== currentProjectId) { currentConversationId=null; saveActiveConversation(); draftId=crypto.randomUUID(); }
      currentProjectId = nextProjectId;
      q('#project-root').textContent = payload.projects_root || 'Projects root unavailable';
      q('#project-root').title = payload.projects_root || '';
      showProjectError(payload.error && projectItems.length ? payload.error : '');
      drawProjectList();
      await refreshConversations();
      const active = projectItems.find((item) => item.id === currentProjectId);
      updateProjectHeader(active);
      await loadStatus();
    } catch (error) {
      showProjectError(error.message);
      q('#project-root').textContent = 'Could not load Projects directory';
      setState(error.message, 'error');
    } finally {
      q('#refresh-projects').disabled = false;
    }
  }
  async function switchProject(projectId, fromConversation = false) {
    if (submitting || switchingProject || creatingProject || (openingConversation && !fromConversation) || projectId === currentProjectId) return;
    saveLocalView(); switchingProject = true; setProjectBusy(true); send.disabled = true; input.disabled = true;
    setState('Switching project…', 'pending');
    try {
      const response = await fetch('/api/project', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_id: projectId }),
      });
      const payload = await readJson(response);
      if (!response.ok) throw new Error(payload.error || `Project switch failed (${response.status}).`);
      currentProjectId = payload.active_project;
      currentConversationId = null; saveActiveConversation(); draftId = crypto.randomUUID();
      latest = { ...latest, project: payload.project?.name || null, project_path: payload.project?.path || null, projectSettings: null, rag: null, steps: [], error: null };
      updateProjectHeader(payload.project); drawProjectList();
      setState('Project switched · new conversation', 'success');
      closeSidebar(); await loadStatus();
    } catch (error) {
      showProjectError(error.message); setState(error.message, 'error');
      await refreshProjects();
    } finally {
      switchingProject = false; setProjectBusy(openingConversation); send.disabled = openingConversation; input.disabled = openingConversation;
      drawProjectList(); if (!fromConversation) await refreshConversations(); input.focus();
    }
  }
  function openProjectDialog() {
    q('#dialog-error').hidden = true; q('#dialog-error').textContent = '';
    projectForm.reset(); dialog.showModal(); projectNameInput.focus();
  }
  async function createProject(event) {
    event.preventDefault();
    if (creatingProject || submitting || switchingProject) return;
    saveLocalView(); creatingProject = true; setProjectBusy(true);
    const createButton = q('#dialog-create'); createButton.disabled = true; q('#dialog-cancel').disabled = true;
    q('#dialog-error').hidden = true; q('#dialog-error').textContent = '';
    try {
      const response = await fetch('/api/projects', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: projectNameInput.value }),
      });
      const payload = await readJson(response);
      if (!response.ok) throw new Error(payload.error || `Project creation failed (${response.status}).`);
      currentProjectId = payload.active_project;
      currentConversationId = null; saveActiveConversation(); draftId = crypto.randomUUID();
      latest = { ...latest, project: payload.project.name, project_path: payload.project.path, steps: [], error: null };
      dialog.close(); updateProjectHeader(payload.project);
      await refreshProjects();
      setState('Project created · new conversation', 'success');
    } catch (error) {
      const message = error.message || 'Could not create project.';
      q('#dialog-error').textContent = message; q('#dialog-error').hidden = false;
      projectNameInput.focus();
    } finally {
      creatingProject = false; createButton.disabled = false; q('#dialog-cancel').disabled = false;
      setProjectBusy(false); drawProjectList();
    }
  }
  async function submit(event) {
    event.preventDefault();
    const message = input.value.trim();
    if (!message || submitting || switchingProject || creatingProject || openingConversation) return;
    if (isCloud() && !q('#cloud-model').value.trim()) { setState('Choose an exact model ID first.', 'error'); return; }
    panelState.beginRun();
    submitting = true; q('#active-model').disabled=true; send.disabled = true; provider.disabled = true; input.disabled = true;
    q('#cancel').disabled = false; q('#cancel').hidden = false; send.hidden = true; setProjectBusy(true);
    q('#cloud-settings').querySelectorAll('input, select, button').forEach(item => { item.disabled = true; });
    activeController = new AbortController(); activeRunId = crypto.randomUUID(); activeAssistant = null; streamedResponse = '';
    latest = { ...latest, steps: [], error: null, routing: null, memories: [], memoryMode: null };
    setState('Starting Chief Agent…', 'pending');
    try {
      if (!currentConversationId) {
        const created = await conversationPost('/api/conversations', {scope_type: currentProjectId ? 'project' : 'general', project_id: currentProjectId});
        currentConversationId = created.id; saveActiveConversation();
        expansion.revealConversation(currentProjectId ? 'project:'+currentProjectId : 'general', false);
        if (activeView) activeView.key = viewKey();
        await conversationPost('/api/conversation/rename', {id: created.id, title: message.slice(0, 100)});
        await refreshConversations();
      }
      addMessage('user', message);
      const response = await fetch('/api/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, provider: provider.value, project_id: currentProjectId, conversation_id: currentConversationId, session_id: sessionId, run_id: activeRunId,
          model:q('#cloud-model').value.trim() || null, account_id:provider.value === 'chatgpt' ? q('#cloud-account').value || null : null }),
        signal: activeController.signal,
      });
      await window.LAEWStream.readEventStream(response, (event) => {
        if (event.type === 'routing') { latest.routing = event.routing; render(); }
        if (event.type === 'memory') { latest.memories=event.memories; latest.memoryMode=event.mode; render(); }
        if (event.type === 'start') { latest.memories=[];
          latest = { ...latest, provider: event.provider, model: event.model };
          q('#runtime').textContent = `${event.provider || 'Provider'} · ${event.model || 'model unavailable'}`;
          q('#runtime').className = 'ready'; setState('Generating response…', 'pending');
        } else if (event.type === 'delta') {
          streamedResponse += event.text;
          if (!activeAssistant) activeAssistant = addMessage('assistant', '');
          window.LAEWMarkdown.renderMarkdown(activeAssistant.content, streamedResponse);
          setState('Generating response…', 'pending'); conversation.scrollTop = conversation.scrollHeight;
        } else if (event.type === 'reset') {
          streamedResponse = '';
          if (activeAssistant) window.LAEWMarkdown.renderMarkdown(activeAssistant.content, '');
          setState('Provider retrying…', 'pending');
        } else if (event.type === 'step') {
          latest = { ...latest, steps: [...(latest.steps || []).filter(step => !(step.pending && step.tool === event.step.tool && step.operation === event.step.operation)), event.step] };
          if (event.step.tool) panelState.toolEvent();
          render(panelState.active);
        } else if (event.type === 'approval') {
          latest.steps.push({tool:event.tool,operation:event.operation,pending:true,approvalId:event.id,status:'Pending approval',success:null});
          render(panelState.toolEvent());
          const card = document.createElement('section'); card.className = 'message approval-request'; card.setAttribute('role','group'); card.setAttribute('aria-label','Tool approval');
          const heading = document.createElement('strong'); heading.textContent = 'Chief Agent requests permission';
          const details = document.createElement('pre');
          details.textContent = `${event.tool}.${event.operation}\nProject: ${event.project}\nRisk: ${event.risk}\nArguments: ${JSON.stringify(event.arguments, null, 2)}`;
          card.append(heading, details);
          const choices = [['Allow once', 'allow']];
          if (event.allow_session) choices.push(['Allow for session', 'allow_session']);
          choices.push(['Deny', 'deny']);
          choices.forEach(([label, decision]) => {
            const button = document.createElement('button'); button.type = 'button'; button.textContent = label;
            button.addEventListener('click', async () => {
              card.querySelectorAll('button').forEach((item) => { item.disabled = true; });
              try {
                const response = await fetch('/api/approval', {method: 'POST', headers: {'Content-Type': 'application/json'},
                  body: JSON.stringify({id: event.id, decision, session_id: sessionId})});
                if (!response.ok) throw new Error('Approval expired or was already decided.');
                heading.textContent = decision === 'deny' ? 'Denied' : (decision === 'allow_session' ? 'Approved for session' : 'Approved once');
                const pending=latest.steps.find(s=>s.approvalId===event.id); if(pending) pending.status=decision==='deny'?'Denied':'Approved · awaiting result'; render();
              } catch (error) { heading.textContent = error.message; }
            });
            card.append(button);
          });
          conversation.append(card); conversation.scrollTop=conversation.scrollHeight; setState('Waiting for approval…', 'pending');
        } else if (event.type === 'done') {
          knowledgeUI.refresh();
          latest = { ...latest, ...event };
          if (!activeAssistant) activeAssistant = addMessage('assistant', event.response || 'The Chief Agent returned no response.', event.response ? '' : 'error');
          else window.LAEWMarkdown.renderMarkdown(activeAssistant.content, event.response || streamedResponse);
          input.value = '';
          q('#runtime').textContent = `${event.provider || latest.provider || 'Provider'} · ${event.model || latest.model || 'model unavailable'}`;
          q('#runtime').className = 'ready'; setState('Completed', 'success');
        } else if (event.type === 'error') {
          latest = { ...latest, error: event.error, steps: event.steps || latest.steps || [] };
          if (activeAssistant) activeAssistant.article.classList.add('incomplete');
          addMessage('assistant', `${event.error || 'The response failed.'} Check provider availability and retry.`, 'error');
          setState('Run failed — revise and retry', 'error');
        }
      }, activeController.signal);
    } catch (error) {
      const cancelled = error.name === 'AbortError' || (activeRunId && activeRunId === stoppingRunId);
      latest = { ...latest, error: cancelled ? 'Response cancelled.' : error.message, steps: latest.steps || [] };
      if (activeAssistant) activeAssistant.article.classList.add('incomplete');
      if (cancelled) latest.steps.forEach(step=>{if(step.pending) step.status='Cancelled';});
      if (cancelled) conversation.querySelectorAll('.approval-request button').forEach((button) => { button.disabled = true; });
      addMessage('assistant', `${latest.error} ${cancelled ? 'The partial response is incomplete.' : 'Check provider availability and retry.'}`, 'error');
      setState(cancelled ? 'Cancelled · partial response retained' : 'Run failed — revise and retry', 'error');
    } finally {
      submitting = false; activeController = null; activeRunId = null; stoppingRunId = null; activeAssistant = null;
      send.disabled = false; send.hidden = false; q('#cancel').hidden = true; q('#cancel').disabled = true; provider.disabled = false; input.disabled = false; setProjectBusy(false);
      q('#cloud-settings').querySelectorAll('input, select, button').forEach(item => { item.disabled = false; });
      drawProjectList(); refreshConversations(); updateModelPicker(); render(); input.focus();
    }
  }
  q('#cancel').addEventListener('click', async () => {
    const controller = activeController, runId = activeRunId;
    if (!controller || !runId) return;
    stoppingRunId = runId;
    q('#cancel').disabled = true; setState('Stopping…', 'pending');
    try {
      const response = await fetch('/api/chat/cancel', {method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({session_id: sessionId, run_id: runId})});
      if (!response.ok) throw new Error('Could not stop the run.');
      controller.abort();
    } catch (error) {
      if (activeRunId === runId) { stoppingRunId = null; q('#cancel').disabled = false; setState(error.message, 'error'); }
    }
  });
  function closeSidebar() {
    q('#sidebar').classList.remove('open');
    q('#sidebar-toggle').setAttribute('aria-expanded', 'false');
  }

  form.addEventListener('submit', submit);
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); form.requestSubmit(); }
  });
  q('#cloud-refresh-models').addEventListener('click', loadCloudModels);
  async function newConversation() {
    if (submitting || switchingProject || creatingProject || openingConversation) return;
    try { currentConversationId = null; saveActiveConversation(); draftId = crypto.randomUUID(); showPage('chat'); await changeView(); await refreshConversations(); setState('New Chief Agent conversation', 'success'); }
    catch (error) { setState(error.message, 'error'); }
  }
  q('#sidebar-new-chat').addEventListener('click', newConversation);
  q('#cloud-login').addEventListener('click', async () => {
    if (authAttempt) return;
    const popup = window.open('about:blank', '_blank'); if (popup) popup.opener = null;
    try {
      const data = await cloudPost('/api/cloud/auth/start'); authAttempt = data.attempt_id;
      if (popup) popup.location = data.authorization_url;
      else { const link = document.createElement('a'); link.href = data.authorization_url; link.textContent = 'Open ChatGPT sign-in'; link.target = '_blank'; link.rel = 'noopener noreferrer'; q('#services-message').replaceChildren(link); }
      q('#cloud-auth-cancel').hidden = false;
      const poll = window.setInterval(async () => {
        if (!authAttempt) { window.clearInterval(poll); return; }
        try { await refreshServices(); } catch (error) { q('#cloud-auth-state').textContent = error.message; }
      }, 1500);
    } catch (error) { if (popup) popup.close(); q('#cloud-auth-state').textContent = error.message; }
  });
  q('#cloud-auth-cancel').addEventListener('click', async () => {
    try { await cloudPost('/api/cloud/auth/cancel', {attempt_id:authAttempt}); authAttempt = null; q('#cloud-auth-cancel').hidden = true; q('#cloud-auth-state').textContent = 'Sign-in cancelled.'; }
    catch (error) { q('#cloud-auth-state').textContent = error.message; }
  });
  q('#cloud-logout').addEventListener('click', async () => {
    try {
      const data = await cloudPost('/api/cloud/auth/logout');
      for (const key of drafts.keys()) { const scope = JSON.parse(key); if (scope.provider === 'chatgpt' && scope.account_id === q('#cloud-account').value) drafts.delete(key); }
      input.value = ''; activeView = null; q('#cloud-model').value = '';
      await refreshServices(); q('#services-message').textContent=data.message;
    }
    catch (error) { q('#cloud-auth-state').textContent = error.message; }
  });
  q('#refresh-projects').addEventListener('click', refreshProjects);
  q('#new-project').addEventListener('click', openProjectDialog);
  projectForm.addEventListener('submit', createProject);
  q('#dialog-close').addEventListener('click', () => dialog.close());
  q('#dialog-cancel').addEventListener('click', () => dialog.close());
  q('#dialog-project-root').textContent = 'Projects';
  document.querySelectorAll('.tab').forEach(button=>{
    button.addEventListener('click',()=>render(button.dataset.tab));
    button.addEventListener('keydown',event=>{
      if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
      event.preventDefault(); const tabs=Array.from(document.querySelectorAll('.tab')); let index=tabs.indexOf(button);
      index=event.key==='Home'?0:event.key==='End'?tabs.length-1:(index+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;
      render(tabs[index].dataset.tab);tabs[index].focus();
    });
  });
  document.addEventListener('keydown',event=>{ if(event.key==='Escape'){closeSidebar();if(window.matchMedia('(max-width: 880px)').matches){q('#context').classList.add('hidden');q('#context-toggle').setAttribute('aria-expanded','false');}} });
  q('#context-toggle').addEventListener('click', () => {
    const context = q('#context'); context.classList.toggle('hidden');
    q('#context-toggle').setAttribute('aria-expanded', String(!context.classList.contains('hidden')));
    q('.shell').classList.toggle('context-collapsed',context.classList.contains('hidden')); applySidebarWidth();
  });
  q('#sidebar-toggle').addEventListener('click', () => {
    const sidebar = q('#sidebar'); const open = sidebar.classList.toggle('open');
    q('#sidebar-toggle').setAttribute('aria-expanded', String(open));
  });
  const resizeHandle=q('#sidebar-resize');
  const widthKey='laew-sidebar-width';
  let preferredWidth=Number(storage.get(widthKey)) || 260, drag=null;
  function applySidebarWidth() {
    const contextWidth=q('#context').classList.contains('hidden') || q('.shell').classList.contains('services-open') ? 0 : parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--context-width')) || 330;
    const width=window.LAEWUI.sidebarWidth(preferredWidth, window.innerWidth, contextWidth);
    document.documentElement.style.setProperty('--sidebar-width', width+'px');
    resizeHandle.setAttribute('aria-valuemin','210'); resizeHandle.setAttribute('aria-valuemax',String(window.LAEWUI.sidebarWidth(480,window.innerWidth,contextWidth)));
    resizeHandle.setAttribute('aria-valuenow',String(Math.round(width)));
  }
  function setSidebarWidth(value) { preferredWidth=window.LAEWUI.sidebarWidth(value,window.innerWidth,q('#context').classList.contains('hidden') || q('.shell').classList.contains('services-open') ? 0 : parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--context-width')) || 330); applySidebarWidth(); storage.set(widthKey,String(preferredWidth)); }
  resizeHandle.addEventListener('pointerdown', event => { if (event.button!==0) return; event.preventDefault(); drag={id:event.pointerId, start:event.clientX, width:parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--sidebar-width'))}; resizeHandle.setPointerCapture(event.pointerId); document.body.classList.add('resizing-sidebar'); });
  resizeHandle.addEventListener('pointermove', event => { if (drag && drag.id===event.pointerId) setSidebarWidth(drag.width+event.clientX-drag.start); });
  function finishResize(event) { if (!drag || drag.id!==event.pointerId) return; if (event.type==='pointercancel') setSidebarWidth(drag.width); drag=null; document.body.classList.remove('resizing-sidebar'); }
  resizeHandle.addEventListener('pointerup',finishResize); resizeHandle.addEventListener('pointercancel',finishResize); resizeHandle.addEventListener('lostpointercapture',finishResize);
  resizeHandle.addEventListener('dblclick',()=>setSidebarWidth(260));
  resizeHandle.addEventListener('keydown',event=>{ const current=parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--sidebar-width')); const values={ArrowLeft:current-10,ArrowRight:current+10,Home:210,End:480}; if (Object.hasOwn(values,event.key)) { event.preventDefault(); setSidebarWidth(values[event.key]); } });
  window.addEventListener('resize',applySidebarWidth); applySidebarWidth();
  const syncResponsivePanels = () => {
    if (window.matchMedia('(max-width: 880px)').matches) {
      q('#context').classList.add('hidden'); q('#context-toggle').setAttribute('aria-expanded', 'false');
    } else {
      q('.shell').classList.remove('context-collapsed'); closeSidebar(); q('#context').classList.remove('hidden'); q('#context-toggle').setAttribute('aria-expanded', 'true');
    }
    applySidebarWidth();
  };
  window.matchMedia('(max-width: 880px)').addEventListener('change', syncResponsivePanels);
  conversation.addEventListener('click', (event) => {
    const button = event.target.closest('[data-prompt]');
    if (!button) return; input.value = button.dataset.prompt; input.focus();
  });
  async function discoverModels() {
    await refreshServices();
    const targets=[['manifest',''],['llama.cpp','']];
    if(credentialStatus.api_key_configured) targets.push(['openai-api','']);
    if(credentialStatus.gemini_api_key_configured) targets.push(['gemini','']);
    (credentialStatus.accounts || []).filter(a=>a.authenticated).forEach(a=>targets.push(['chatgpt',a.id]));
    await Promise.allSettled(targets.map(async([type,account])=>{
      const response=await fetch('/api/cloud/models?'+new URLSearchParams({provider:type,account_id:account,session_id:sessionId}),{cache:'no-store'});
      const data=await readJson(response);
      if(response.ok){catalogs.set(catalogKey(type,account),data.models);connectionStates.set(type,'Last catalog check succeeded · inference not tested');}
      else connectionStates.set(type,'Catalog unavailable');
    }));
    drawProviderCards();updateModelPicker();
  }
  const knowledgeUI=window.LAEWKnowledge.create({project:()=>currentProjectId,conversation:()=>currentConversationId});
  knowledgeUI.refresh();
  window.setInterval(()=>{if(!document.hidden)knowledgeUI.refresh();},10000);
  const settingsUI=window.LAEWSettings.create({
    projects:()=>projectItems, conversation:()=>currentConversationId, project:()=>currentProjectId,
    selection:()=>({provider:provider.value,model:q('#cloud-model').value,account_id:q('#cloud-account').value || null}),
    catalogs:()=>window.LAEWUI.modelGroups(Array.from(catalogs.entries()),providerLabels,credentialStatus.accounts || []),
    openConversation, onProjectSaved:refreshProjectSettings
  });
  updateServiceEditor(); syncResponsivePanels(); render(); refreshProjects().then(() => { const saved=storage.get(activeConversationKey); if (saved && !currentConversationId) openConversation(saved, true); }); discoverModels();
})();
