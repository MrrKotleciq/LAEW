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
  let panelFrame = null;
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
  let activeRunId = null;
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
  let diagnosticRuns = new Map();
  let selectedDiagnosticRun = null;
  let streamingDiagnosticRun = null;
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
    diagnosticRuns = new Map(); selectedDiagnosticRun = null; streamingDiagnosticRun = null;
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
    diagnosticRuns.clear(); selectedDiagnosticRun = null; streamingDiagnosticRun = null;
    latest.steps = [];
    latest.error = null;
    panelState.reset(); render('setup');
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
  function attachContextAction(article, runId) {
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'turn-context-action'; button.textContent = 'View sources';
    const run = diagnosticRuns.get(runId);
    if (run) button.setAttribute('aria-label', `View sources for turn ${run.number}`);
    button.addEventListener('click', () => {
      selectedDiagnosticRun = runId;
      if (q('#context').classList.contains('hidden')) q('#context-toggle').click();
      render('sources');
      q('#diagnostic-turn')?.focus();
    });
    article.append(button);
  }
  function renderTurnSelection() {
    panelHeading('Conversation turn');
    const choices = [...diagnosticRuns];
    const available = choices.some(([id]) => id === selectedDiagnosticRun);
    const select = document.createElement('select');
    select.id = 'diagnostic-turn'; select.setAttribute('aria-label', 'Conversation turn');
    select.add(new Option(submitting ? 'Follow live run' : 'Follow latest turn', ''));
    for (const [id, run] of choices) {
      select.add(new Option(`Turn ${run.number} · ${run.status}`, id));
    }
    select.value = available ? selectedDiagnosticRun : '';
    select.addEventListener('change', () => {
      selectedDiagnosticRun = select.value || null;
      render();
    });
    panelBody.append(select);
    if (available && submitting && selectedDiagnosticRun !== streamingDiagnosticRun) {
      panelNote('A new run is active. Select Follow live run to inspect it.');
    }
    const run = available ? diagnosticRuns.get(selectedDiagnosticRun)
      : (submitting ? diagnosticRuns.get(streamingDiagnosticRun) : choices.at(-1)?.[1]);
    if (submitting && !run) panelNote('Starting run…');
    if (run) panelNote(`Turn ${run.number} · ${run.status}${available ? ' · selected' : ''}`);
    return run;
  }
  function scheduleDiagnosticsRender() {
    if (activeTab === 'setup' || panelFrame !== null) return;
    panelFrame = requestAnimationFrame(() => {
      panelFrame = null;
      render();
    });
  }
  function render(tab = activeTab) {
    if (panelFrame !== null) cancelAnimationFrame(panelFrame);
    panelFrame = null;
    const focused = document.activeElement;
    const restoreTurnFocus = focused?.id === 'diagnostic-turn';
    const focusedDetail = focused?.parentElement?.dataset.detail;
    const focusedSync = focused?.dataset.syncScope;
    const openDetails = new Set([...panel.querySelectorAll('details[open][data-detail]')]
      .map(detail => detail.dataset.detail));
    activeTab = panelState.select(tab);
    document.querySelectorAll('.tab').forEach(button => {
      const selected=button.dataset.tab === activeTab;
      button.classList.toggle('active',selected); button.setAttribute('aria-selected',String(selected)); button.tabIndex=selected?0:-1;
    });
    panel.setAttribute('aria-labelledby','tab-'+activeTab);
    panel.replaceChildren(); panelBody=panel;
    const run = tab === 'setup' ? null : renderTurnSelection();
    if (tab === 'setup') {
      panelHeading(currentProjectId ? 'Active project' : 'General Chat');
      const details = document.createElement('dl');
      [['Project', currentProjectId ? (latest.project || projectItems.find(item=>item.id===currentProjectId)?.name) : 'None'], ['Provider', latest.provider], ['Model', latest.model]].forEach(([label, value]) => {
        const term = document.createElement('dt'); term.textContent = label;
        const description = document.createElement('dd'); description.textContent = value || 'Unavailable';
        details.append(term, description);
      });
      panelBody.append(details);
      const paths=diagnosticDetails('Workspace paths', 'workspace-paths');
      [['Project',latest.project_path],['Projects root',latest.projects_root],['Global Knowledge',latest.knowledge_root]].forEach(([label,value])=>{if(value){const p=document.createElement('p');p.textContent=label+': '+value;paths.append(p);}});
      panelNote(currentProjectId ? 'LAEW tools use this project’s permissions.' : 'Global Knowledge is available; project tools and Project Memory are unavailable.');

      if (currentProjectId) {
      panelHeading('Project settings');
      panelNote('Documentation language: '+(latest.projectSettings?.documentation_language || 'checking…'));
      const settingsButton=document.createElement('button');settingsButton.type='button';settingsButton.textContent='Open project settings';settingsButton.addEventListener('click',()=>settingsUI.openProject(currentProjectId));panelBody.append(settingsButton);
      }
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
        button.dataset.syncScope = scope;
        const card = panelBody;
        button.addEventListener('click', async () => {
          try {
            const response = await fetch('/api/rag/sync', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({scope})});
            const payload = await readJson(response);
            if (!response.ok) throw new Error(payload.error || 'Synchronization could not start.');
            await refreshRag(true);
          } catch (error) {
            const note = document.createElement('p');
            note.textContent = error.message;
            card.append(note);
          }
        });
        panelBody.append(button);
      });
    } else if (tab === 'run') {
      renderExecution(run);
    } else {
      renderSources(run);
    }
    for (const detail of panel.querySelectorAll('details[data-detail]')) {
      detail.open = openDetails.has(detail.dataset.detail);
      if (detail.dataset.detail === focusedDetail) detail.firstElementChild.focus({preventScroll: true});
    }
    if (restoreTurnFocus) q('#diagnostic-turn')?.focus({preventScroll: true});
    if (focusedSync) panel.querySelector(`[data-sync-scope="${focusedSync}"]`)?.focus({preventScroll: true});
  }

  function diagnosticDetails(label, key) {
    const details = document.createElement('details');
    details.dataset.detail = key;
    const summary = document.createElement('summary');
    summary.textContent = label;
    details.append(summary);
    panelBody.append(details);
    return details;
  }

  const sourceLabels = {global: 'Global Knowledge', project: 'Project Knowledge', hybrid: 'Global + Project Knowledge'};
  const formatStatus = value => String(value || 'unavailable').replaceAll('_', ' ');
  function coverageSteps(evaluation) {
    if (!evaluation) return [];
    return [evaluation.horizon, evaluation].filter(Boolean).map(attempt => {
      const elapsed = attempt.backend === 'active' ? attempt.active_elapsed_ms : attempt.elapsed_ms;
      return {
        label: attempt.backend === 'horizon' ? 'Horizon NLI' :
          attempt.backend === 'active' ? 'Active model fallback' : 'Memory coverage model',
        status: attempt.status,
        detail: [attempt.model, attempt.phase, attempt.signal && formatStatus(attempt.signal),
          attempt.entailment_score != null && `Entailment ${attempt.entailment_score.toFixed(3)}`,
          elapsed != null && `${elapsed} ms`, attempt.error_category].filter(Boolean).join(' · '),
      };
    });
  }

  function renderCoverageSource(assessment) {
    if (!assessment) return;
    panelNote(`Assessment · ${formatStatus(assessment.status)} · ${assessment.reason}`);
    for (const attempt of coverageSteps(assessment.model_assessment)) {
      panelNote([attempt.label, formatStatus(attempt.status), attempt.detail].filter(Boolean).join(' · '));
    }
  }

  function renderExecution(run) {
    const isLive = submitting && run?.status === 'running' && run === diagnosticRuns.get(streamingDiagnosticRun);
    panelHeading(isLive ? 'Run · Live' : 'Execution');
    const routing = run?.diagnostics?.routing;
    const requests = run?.diagnostics?.requests || [];
    const tools = [...(run?.diagnostics?.tools || []), ...(run?.legacyTools || [])];
    const list = document.createElement('ol');
    const step = (title, status, detail = '') => {
      const item = document.createElement('li');
      item.className = 'tool-card';
      const badge = document.createElement('span');
      badge.className = 'status-badge';
      badge.textContent = formatStatus(status);
      const name = document.createElement('b');
      name.textContent = title;
      item.append(badge, name, document.createTextNode(detail));
      list.append(item);
    };
    if (routing) {
      const skipped = Object.entries(routing.knowledge_skip_reasons || {})
        .filter(([scope]) => !routing.scopes.includes(scope))
        .map(([scope, reason]) => `${sourceLabels[scope]} skipped. ${reason}`);
      step('Knowledge Routing', 'completed', [`${routing.routing_ms} ms`, ...skipped].join(' · '));
      step('Automatic Memory Recall', routing.memory_recall?.status, routing.memory_recall?.reason || '');
      for (const attempt of coverageSteps(routing.assessment?.model_assessment)) {
        step(attempt.label, attempt.status, attempt.detail);
      }
      if (routing.escalation) {
        step('Knowledge escalation', 'selected', routing.escalation.reason);
      } else if (routing.escalation_skipped) {
        step('Knowledge escalation', 'skipped', routing.escalation_skipped);
      }
      for (const search of routing.prefetch.filter(search => !search.after_order)) {
        step(`${sourceLabels[search.scope]} automatic prefetch`, search.status, search.error || '');
      }
      for (const hint of (routing.hints || []).filter(hint => !hint.after_order)) {
        step('Retrieval hint', hint.supplied ? 'supplied' : 'generated', hintLabel(hint));
      }
    } else if (run?.status === 'running') {
      panelNote('Preparing context…');
    } else if (!run?.diagnostics) {
      panelNote('Diagnostic data unavailable for this turn.');
    }
    const renderTool = tool => {
      step([tool.tool, tool.operation].filter(Boolean).join(' · '), tool.status,
        [tool.call_id && `Call ${tool.call_id}`, tool.elapsed_ms != null && `${tool.elapsed_ms} ms`,
          tool.error_category, tool.reused && 'Reused result', tool.supplied && 'Result supplied to adapter',
          tool.historical && 'From conversation history'].filter(Boolean).join(' · '));
      for (const attempt of coverageSteps(tool.memory_recall?.assessment?.model_assessment)) {
        step(attempt.label, attempt.status, attempt.detail);
      }
      if (tool.memory_recall?.escalation_skipped) {
        step('Knowledge escalation after MemoryTool', 'skipped', tool.memory_recall.escalation_skipped);
      }
      for (const search of (routing?.prefetch || []).filter(search => search.after_order === tool.order)) {
        step(`${sourceLabels[search.scope]} automatic fallback`, search.status,
          [search.reason, search.error].filter(Boolean).join(' · '));
      }
      for (const hint of (routing?.hints || []).filter(hint => hint.after_order === tool.order)) {
        step('Retrieval hint', hint.supplied ? 'supplied' : 'generated', hintLabel(hint));
      }
    };
    for (const [index, request] of requests.entries()) {
      step(request.iteration > 1 ? 'Model request · resumed' : 'Model request', request.status,
        [`Iteration ${request.iteration}`, `Attempt ${request.attempt}`, request.error_category,
          request.elapsed_ms != null && `${request.elapsed_ms} ms`].filter(Boolean).join(' · '));
      const next = requests[index + 1];
      if (next?.iteration !== request.iteration) {
        tools.filter(tool => tool.iteration === request.iteration).forEach(renderTool);
      }
    }
    tools.filter(tool => !requests.some(request => request.iteration === tool.iteration)).forEach(renderTool);
    if (!tools.length) panelNote('No recorded tool activity.');
    if (run?.status === 'completed') step('Assistant response', 'completed');
    if (['failed', 'cancelled', 'outcome unknown'].includes(run?.status)) step('Run', run.status, run.error || '');
    if (list.childNodes.length) panelBody.append(list);
    if (submitting && !selectedDiagnosticRun) {
      latest.steps.filter(item => item.pending).forEach(item => panelNote(`${item.tool} · ${item.status}`));
    }
  }

  function renderMemoryRecall(recall, label, id) {
    const recallStatus = recall.skip_reason === 'recall_disabled' ? 'Memory Recall disabled' : ({
      no_results: recall.budget_omitted ? 'Matching memories exceeded the context budget' : 'No matching active memories returned',
      failed: 'Memory Recall failed', unavailable: 'Memory Recall unavailable',
      not_selected: 'Memory Recall not selected',
    }[recall.status] || formatStatus(recall.status));
    const scopes = recall.scopes?.length ? ` · Allowed scope: ${recall.scopes.join(', ')}` : '';
    panelNote(`${label} · ${recallStatus}${scopes}`);
    if (recall.reason) panelNote(recall.reason);
    if (recall.invoked === false) panelNote('Recall service was not invoked.');
    else if (recall.search_executed === false) panelNote('Recall did not reach a search backend.');
    else if (recall.search_executed === true) panelNote('Recall queried a search backend.');
    if (recall.candidates != null) panelNote(`${recall.candidates} candidates`);
    if (recall.selected != null) panelNote(`${recall.selected} selected · ${recall.supplied} supplied to provider adapter`);
    if (recall.elapsed_ms != null) panelNote(`${recall.elapsed_ms} ms`);
    if (recall.estimated_context_size != null) panelNote(`${recall.estimated_context_size} estimated tokens`);
    if (recall.budget_omitted) panelNote(`${recall.budget_omitted} omitted for budget`);
    if (recall.duplicates_omitted) panelNote(`${recall.duplicates_omitted} duplicate(s) omitted`);
    if (recall.error_category) panelNote(recall.error_category);
    if (recall.fallback_error_category) panelNote(`Semantic recall fallback · ${recall.fallback_error_category}`);
    if (recall.fallback_reason) panelNote(`Semantic recall fallback · ${formatStatus(recall.fallback_reason)}`);
    if (recall.skip_reason && recall.skip_reason !== 'recall_disabled') panelNote(formatStatus(recall.skip_reason));
    if (recall.ids?.length) diagnosticDetails('Selected memory IDs', id).append(document.createTextNode(recall.ids.join(', ')));
  }

  function hintLabel(hint) {
    const scopes = hint.scopes.map(scope => sourceLabels[scope]).join(', ');
    return `${formatStatus(hint.kind)} evidence${scopes ? ` · Optional search in ${scopes}` : ''}`;
  }

  function renderSources(run) {
    const diagnostics = run?.diagnostics;
    const routing = diagnostics?.routing;
    panelHeading('Knowledge Routing');
    if (!run) panelNote(submitting ? 'Preparing context…' : 'Choose a conversation turn to inspect its sources.');
    else if (!diagnostics) panelNote('Diagnostic data unavailable for this turn.');
    else if (!routing) panelNote(run.status === 'running' ? 'Preparing context…' : 'Routing was not recorded.');
    else {
      const selected = [...(routing.memory_requested ? ['Long-Term Memory'] : []),
        ...(routing.initial_scopes || routing.scopes).map(scope => sourceLabels[scope])];
      panelNote(`${routing.initial_scopes ? 'Initially selected' : 'Selected'}: ${selected.join(', ') || 'None'}`);
      panelNote(routing.reason);
      if (routing.topic_from_history) panelNote('Search used the recent conversation topic.');
      if (routing.memory_excluded) panelNote('Long-Term Memory excluded for this turn by the user.');
      if (routing.rag_disabled) panelNote('RAG excluded for this turn by the user.');
      else if (routing.excluded_scopes?.length) {
        panelNote(`Excluded by the user: ${routing.excluded_scopes.map(scope => sourceLabels[scope]).join(', ')}`);
      }
      panelNote(`Routing: ${routing.routing_ms} ms`);
    }

    panelHeading('Long-Term Memory');
    const recall = routing?.memory_recall;
    if (!recall) panelNote('No recorded Memory Recall data.');
    else renderMemoryRecall(recall, 'Automatic Memory Recall', 'memory-ids');
    renderCoverageSource(routing?.assessment);
    if (routing?.escalation) {
      panelNote(`Escalated to ${routing.escalation.scopes.map(scope => sourceLabels[scope]).join(', ')} · ${routing.escalation.reason}`);
    } else if (routing?.escalation_skipped) {
      panelNote(`Automatic fallback skipped · ${routing.escalation_skipped}`);
    }
    for (const tool of diagnostics?.tools || []) {
      if (tool.tool === 'MemoryTool' && tool.operation === 'recall') {
        renderMemoryRecall(
          {status: tool.status, elapsed_ms: tool.elapsed_ms, ...tool.memory_recall},
          'Model-initiated MemoryTool recall', `memory-tool-${tool.order}`,
        );
        renderCoverageSource(tool.memory_recall?.assessment);
        if (tool.memory_recall?.escalation_skipped) {
          panelNote(`Automatic fallback skipped · ${tool.memory_recall.escalation_skipped}`);
        }
      }
    }

    for (const scope of ['global', 'project']) {
      panelHeading(sourceLabels[scope]);
      if (scope === 'project' && !currentProjectId) {
        panelNote('Project Knowledge unavailable in General Chat');
        continue;
      }
      if (!routing) {
        panelNote('No recorded retrieval data.');
        continue;
      }
      const prefetch = routing.prefetch.filter(search => search.scope === scope);
      panelNote(routing.scopes.includes(scope) ? 'Selected for automatic prefetch' : 'Not selected for automatic prefetch');
      if (!routing.scopes.includes(scope) && routing.knowledge_skip_reasons?.[scope]) {
        panelNote(routing.knowledge_skip_reasons[scope]);
      }
      if (routing.scopes.includes(scope) && !prefetch.length) {
        panelNote(run.status === 'running' ? 'Automatic prefetch pending' : 'No automatic prefetch outcome recorded');
      }
      prefetch.forEach((search, index) => {
        renderSearch(search, search.after_order ? 'Automatic fallback after MemoryTool' : 'Automatic prefetch', `prefetch-${scope}-${index}`);
        if (search.reason) panelNote(search.reason);
      });
      routing.follow_up.filter(search => search.scope === scope)
        .forEach((search, index) => renderSearch(search, 'Model-initiated RagTool', `rag-${scope}-${index}`));
    }
    const otherSearches = routing?.follow_up.filter(search => !['global', 'project'].includes(search.scope)) || [];
    if (otherSearches.length) {
      panelHeading('Other RagTool searches');
      otherSearches.forEach((search, index) => renderSearch(search,
        `Model-initiated RagTool · ${sourceLabels[search.scope] || formatStatus(search.scope)}`, `rag-other-${index}`));
    }

    panelHeading('Context Assembly');
    if (!routing) {
      panelNote('No recorded context assembly data.');
      return;
    }
    if (recall?.selected != null) {
      panelNote(`Memory · ${recall.selected} selected${recall.prepared == null ? '' : ` · ${recall.prepared} prepared`} · ${recall.supplied} supplied to provider adapter`);
    }
    for (const hint of routing.hints || []) {
      panelNote(`Retrieval hint · ${hintLabel(hint)} · ${hint.supplied ? 'supplied to provider adapter' : 'generated'}`);
    }
    for (const scope of (currentProjectId ? ['global', 'project'] : ['global'])) {
      for (const [label, searches] of [['automatic prefetch', routing.prefetch], ['RagTool', routing.follow_up]]) {
        for (const search of searches.filter(item => item.scope === scope)) {
          if (search.chunks == null || search.status === 'started') continue;
          const metrics = [
            search.retrieved_sources && `${search.retrieved_sources.length} retrieved paths recorded`,
            `${search.chunks} excerpts prepared`, `${search.supplied ?? 0} supplied to provider adapter`,
            search.budget_omitted && `${search.budget_omitted} omitted for budget`,
            search.duplicates_omitted && `${search.duplicates_omitted} duplicates omitted`,
            search.fragments && `${search.fragments.filter(fragment => fragment.truncated).length} truncated`,
            search.estimated_context_size != null && `${search.estimated_context_size} estimated tokens`,
          ];
          panelNote(`${sourceLabels[scope]} ${label} · ${metrics.filter(Boolean).join(' · ')}`);
        }
      }
    }
    for (const request of diagnostics.requests) {
      panelNote(`Iteration ${request.iteration} · attempt ${request.attempt} · ${request.dispatched ? 'Dispatched to provider adapter' : 'Dispatch unconfirmed'} · ${request.history_messages} history messages · ${request.tool_results} current tool results`
        + (request.history_omitted ? ` · ${request.history_omitted} history messages omitted for budget` : '')
        + (request.usage?.input == null ? '' : ` · ${request.usage.input} input tokens reported`)
        + (request.usage?.output == null ? '' : ` · ${request.usage.output} output tokens reported`));
    }
  }

  function renderSearch(search, label, key) {
    panelNote(`${label} · ${formatStatus(search.status)}${search.elapsed_ms == null ? '' : ` · ${search.elapsed_ms} ms`}`);
    if (search.candidates != null) panelNote(`${search.candidates} candidates`);
    if (search.chunks != null) panelNote(`${search.chunks} excerpts prepared · ${search.supplied ?? 0} supplied to provider adapter`);
    if (search.index_status) panelNote(`Index · ${formatStatus(search.index_status)}`);
    if (search.search_executed === false && !search.reused) panelNote('Search did not reach the retrieval pipeline.');
    if (search.error) panelNote(search.error);
    if (search.call_id) panelNote(`Call ${search.call_id}`);
    if (search.reused) panelNote('Reused result.');
    if (search.budget_omitted) panelNote(`${search.budget_omitted} omitted for budget`);
    if (search.duplicates_omitted) panelNote(`${search.duplicates_omitted} duplicate(s) omitted`);
    if (search.estimated_context_size != null) panelNote(`${search.estimated_context_size} estimated tokens`);
    const authorized = path => typeof path === 'string' &&
      (path.startsWith('@knowledge/') || (currentProjectId && path.startsWith('@project/')));
    const paths = (search.retrieved_sources || search.sources || []).filter(authorized);
    const fragments = (search.fragments || []).filter(fragment => authorized(fragment.path));
    if (paths.length || fragments.length) {
      const details = diagnosticDetails('Source paths and prepared excerpts', key);
      for (const text of [...paths, ...fragments.map(fragment =>
        `${fragment.path} · ${fragment.id} · ${search.supplied ? 'supplied to provider adapter' : 'prepared'}${fragment.truncated ? ' · truncated' : ''}`)]) {
        const note = document.createElement('p');
        note.textContent = text;
        details.append(note);
      }
    }
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
      const item = conversationItems.find(entry => entry.id === id);
      if (!item) throw new Error('Conversation unavailable.');
      if (item.project_id !== currentProjectId) {
        await switchProject(item.project_id, true);
        if (currentProjectId !== item.project_id) throw new Error('Conversation project is unavailable.');
      }
      const params = new URLSearchParams({id});
      if (currentProjectId) params.set('project_id', currentProjectId);
      const response = await fetch('/api/conversation?' + params, {cache:'no-store'});
      const data = await readJson(response);
      if (!response.ok) throw new Error(data.error || 'Conversation unavailable.');
      currentConversationId = id; saveActiveConversation();
      const groupKey=data.scope_type === 'general' ? 'general' : 'project:'+data.project_id;
      expansion.revealConversation(groupKey, restore);
      if (!restore && projectsContent.hidden) setProjectsExpanded(true);
      showPage('chat'); closeSidebar();
      await changeView();
      conversation.replaceChildren();
      diagnosticRuns = new Map(); streamingDiagnosticRun = null;
      for (const event of data.events) {
        if (event.kind !== 'run' || !event.run_id) continue;
        const previous = diagnosticRuns.get(event.run_id);
        diagnosticRuns.set(event.run_id, {
          number: previous?.number || diagnosticRuns.size + 1,
          status: event.status, error: event.content, assistantId: event.assistant_event_id,
          diagnostics: event.diagnostics?.version === 1 ? event.diagnostics : previous?.diagnostics || null,
          legacyTools: [],
        });
      }
      const toolOutcomes = new Set(data.events.filter(event => event.kind === 'tool_result')
        .map(event => JSON.stringify([event.run_id, event.call_id])));
      for (const event of data.events) {
        const run = diagnosticRuns.get(event.run_id);
        if (event.kind === 'user' && !event.generated) addMessage('user', event.content);
        if (event.kind === 'assistant' && run?.status === 'completed'
            && (run.assistantId ? run.assistantId === event.id
              : !event.message?.tool_calls?.length && !event.content.includes('```tool_call'))) {
          attachContextAction(addMessage('assistant', event.content).article, event.run_id);
        }
        const hasOutcome = toolOutcomes.has(JSON.stringify([event.run_id, event.call_id]));
        if (run && (event.kind === 'tool_result' || (event.kind === 'tool_call' && !hasOutcome))
            && !run.diagnostics?.tools.some(tool => tool.call_id === event.call_id)) {
          run.legacyTools.push({tool: event.tool, operation: event.operation,
            call_id: event.call_id, status: event.kind === 'tool_result' ? event.status : 'Outcome unknown', historical: true});
        }
      }
      render();
      if (!conversation.childNodes.length) conversation.append(emptyForScope());
      if ([...diagnosticRuns.values()].some(run => run.status !== 'completed')) setState('This conversation contains an incomplete run.');
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
    if (activeTab === 'setup' && !panel.contains(document.activeElement)) render('setup');
  }
  async function refreshRag(manual = false) {
    const projectId=currentProjectId;
    try { const data=await readJson(await fetch('/api/rag'));if(projectId===currentProjectId) latest.rag=data; }
    catch { if(projectId===currentProjectId) latest.rag = {error: 'Synchronization status is unavailable.'}; }
    if (activeTab === 'setup' && (manual || !panel.contains(document.activeElement))) render('setup');
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
    submitting = true; q('#active-model').disabled=true; send.disabled = true; provider.disabled = true; input.disabled = true;
    q('#cancel').disabled = false; q('#cancel').hidden = false; send.hidden = true; setProjectBusy(true);
    q('#cloud-settings').querySelectorAll('input, select, button').forEach(item => { item.disabled = true; });
    activeRunId = crypto.randomUUID(); activeAssistant = null; streamedResponse = '';
    streamingDiagnosticRun = null;
    latest = { ...latest, steps: [], error: null };
    setState('Starting Chief Agent…', 'pending');
    scheduleDiagnosticsRender();
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
      const conversationId = currentConversationId;
      const projectId = currentProjectId;
      const response = await fetch('/api/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, provider: provider.value, project_id: currentProjectId, conversation_id: currentConversationId, session_id: sessionId, run_id: activeRunId,
          model:q('#cloud-model').value.trim() || null, account_id:provider.value === 'chatgpt' ? q('#cloud-account').value || null : null }),
      });
      await window.LAEWStream.readEventStream(response, (event) => {
        if (currentConversationId !== conversationId || currentProjectId !== projectId) return;
        if (event.conversation_id && event.conversation_id !== conversationId) return;
        if (event.run_id && streamingDiagnosticRun && event.run_id !== streamingDiagnosticRun) return;
        if (event.conversation_id === conversationId && event.diagnostics?.version === 1 && event.run_id) {
          streamingDiagnosticRun = event.run_id;
          const previous = diagnosticRuns.get(event.run_id);
          diagnosticRuns.set(event.run_id, {
            number: previous?.number || diagnosticRuns.size + 1,
            status: event.run_status || 'running', error: event.error,
            diagnostics: event.diagnostics,
          });
          if (!selectedDiagnosticRun || selectedDiagnosticRun === event.run_id || !previous || event.run_status) scheduleDiagnosticsRender();
        }
        if (event.phase === 'provider_request' && !streamedResponse) setState('Generating response…', 'pending');
        if (event.type === 'start') { latest.memories=[];
          latest = { ...latest, provider: event.provider, model: event.model };
          q('#runtime').textContent = `${event.provider || 'Provider'} · ${event.model || 'model unavailable'}`;
          q('#runtime').className = 'ready'; setState('Preparing context…', 'pending');
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
          if (!selectedDiagnosticRun) scheduleDiagnosticsRender();
        } else if (event.type === 'approval') {
          latest.steps.push({tool:event.tool,operation:event.operation,pending:true,approvalId:event.id,status:'Pending approval',success:null});
          if (!selectedDiagnosticRun) scheduleDiagnosticsRender();
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
          latest = { ...latest, provider: event.provider, model: event.model, usage: event.usage };
          if (!activeAssistant) activeAssistant = addMessage('assistant', event.response || 'The Chief Agent returned no response.', event.response ? '' : 'error');
          else window.LAEWMarkdown.renderMarkdown(activeAssistant.content, event.response || streamedResponse);
          if (streamingDiagnosticRun) attachContextAction(activeAssistant.article, streamingDiagnosticRun);
          input.value = '';
          q('#runtime').textContent = `${event.provider || latest.provider || 'Provider'} · ${event.model || latest.model || 'model unavailable'}`;
          q('#runtime').className = 'ready'; setState('Completed', 'success');
        } else if (event.type === 'cancelled') {
          if (activeAssistant) activeAssistant.article.classList.add('incomplete');
          conversation.querySelectorAll('.approval-request button').forEach(button => { button.disabled = true; });
          setState('Cancelled', 'error');
        } else if (event.type === 'error') {
          latest = { ...latest, error: event.error, steps: event.steps || latest.steps || [] };
          if (activeAssistant) activeAssistant.article.classList.add('incomplete');
          addMessage('assistant', `${event.error || 'The response failed.'} Check provider availability and retry.`, 'error');
          setState('Run failed — revise and retry', 'error');
        }
      });
    } catch (error) {
      const run = diagnosticRuns.get(streamingDiagnosticRun);
      if (run?.status === 'running') {
        run.status = 'outcome unknown';
        run.error = 'Response stream ended early. Reopen the conversation for the persisted outcome.';
      }
      latest = { ...latest, error: error.message, steps: latest.steps || [] };
      if (activeAssistant) activeAssistant.article.classList.add('incomplete');
      conversation.querySelectorAll('.approval-request button').forEach(button => { button.disabled = true; });
      addMessage('assistant', latest.error, 'error');
      setState('Stream interrupted', 'error');
    } finally {
      submitting = false; activeRunId = null; activeAssistant = null;
      streamingDiagnosticRun = null;
      send.disabled = false; send.hidden = false; q('#cancel').hidden = true; q('#cancel').disabled = true; provider.disabled = false; input.disabled = false; setProjectBusy(false);
      q('#cloud-settings').querySelectorAll('input, select, button').forEach(item => { item.disabled = false; });
      drawProjectList(); refreshConversations(); updateModelPicker(); render();
      if (!panel.contains(document.activeElement)) input.focus();
    }
  }
  q('#cancel').addEventListener('click', async () => {
    const runId = activeRunId;
    if (!runId) return;
    q('#cancel').disabled = true; setState('Stopping…', 'pending');
    try {
      const response = await fetch('/api/chat/cancel', {method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({session_id: sessionId, run_id: runId})});
      if (!response.ok) throw new Error('Could not stop the run.');
      // Persistent runs report cancellation through the stream after saving the terminal snapshot.
    } catch (error) {
      if (activeRunId === runId) { q('#cancel').disabled = false; setState(error.message, 'error'); }
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
