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
  let activeTab = 'context';
  let submitting = false;
  let switchingProject = false;
  let creatingProject = false;
  let currentProjectId = null;
  let projectItems = [];
  let statusRequest = 0;
  let activeController = null;
  let activeAssistant = null;
  let streamedResponse = '';
  const initialEmpty = q('.empty')?.cloneNode(true);

  const setState = (text, kind = '') => { state.textContent = text; state.className = kind; };
  const setProjectBusy = (busy) => {
    q('#new-project').disabled = busy;
    q('#refresh-projects').disabled = busy;
    projectList.querySelectorAll('button[data-project-id]').forEach((button) => { button.disabled = busy; });
  };
  const clearConversation = () => {
    conversation.replaceChildren(initialEmpty.cloneNode(true));
    latest.steps = [];
    latest.error = null;
    render('context');
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
    const heading = document.createElement('h2'); heading.textContent = title; panel.append(heading);
  };
  const panelNote = (text) => {
    const note = document.createElement('p'); note.textContent = text; panel.append(note);
  };
  function render(tab = activeTab) {
    activeTab = tab;
    panel.replaceChildren();
    if (tab === 'context') {
      panelHeading('Workspace context');
      const details = document.createElement('dl');
      [['Project', latest.project_path || latest.project], ['Projects root', latest.projects_root], ['Provider', latest.provider], ['Model', latest.model]].forEach(([label, value]) => {
        const term = document.createElement('dt'); term.textContent = label;
        const description = document.createElement('dd'); description.textContent = value || 'Unavailable';
        details.append(term, description);
      });
      panel.append(details);
      panelNote('Runtime state reported by LAEW. Project files stay inside the selected workspace boundaries.');
    } else if (tab === 'run') {
      panelHeading('Current run');
      const steps = Array.isArray(latest.steps) ? latest.steps : [];
      if (!steps.length) panelNote(latest.error || 'No tool activity for this response.');
      else {
        const list = document.createElement('ol');
        steps.forEach((step) => {
          const item = document.createElement('li');
          const title = document.createElement('b'); title.textContent = step.tool || 'Response'; item.append(title);
          if (step.operation) item.append(document.createTextNode(` · ${step.operation}`));
          if (step.error) { const error = document.createElement('em'); error.textContent = step.error; item.append(error); }
          list.append(item);
        });
        panel.append(list);
      }
    } else {
      panelHeading('Sources');
      const sources = [...new Set((latest.steps || []).flatMap((step) => step.sources || []))];
      if (!sources.length) panelNote('No RAG sources were retrieved for this response.');
      else {
        const list = document.createElement('ul');
        sources.forEach((source) => { const item = document.createElement('li'); item.textContent = source; list.append(item); });
        panel.append(list);
      }
    }
  }
  async function readJson(response) {
    const text = await response.text();
    try { return text ? JSON.parse(text) : {}; }
    catch { throw new Error(`The local API returned invalid JSON (${response.status}).`); }
  }
  function showProjectError(message) {
    projectError.textContent = message || '';
    projectError.hidden = !message;
  }
  function updateProjectHeader(item) {
    const name = item?.name || 'No active project';
    const path = item?.path || 'Choose a project folder to begin.';
    q('#active-project-name').textContent = name;
    q('#active-project-name').title = name;
    q('#task-title').textContent = name;
    q('#workspace').textContent = path;
    q('#workspace').title = path;
    q('#active-project-path').textContent = path;
    q('#active-project-path').title = path;
  }
  function drawProjectList() {
    projectList.replaceChildren();
    q('#project-count').textContent = String(projectItems.length);
    if (!projectItems.length) {
      const note = document.createElement('p'); note.className = 'muted-note';
      note.textContent = 'No project folders yet. Create one to get started.'; projectList.append(note); return;
    }
    projectItems.forEach((item) => {
      const button = document.createElement('button');
      button.type = 'button'; button.className = 'project-item';
      button.dataset.projectId = item.id;
      button.classList.toggle('active', item.id === currentProjectId);
      button.setAttribute('aria-current', item.id === currentProjectId ? 'true' : 'false');
      button.title = item.path;
      const mark = document.createElement('span'); mark.className = 'project-mark'; mark.textContent = 'P';
      const name = document.createElement('span'); name.className = 'project-name'; name.textContent = item.name;
      button.append(mark, name);
      if (item.id === currentProjectId) {
        const active = document.createElement('span'); active.className = 'project-active-mark'; active.textContent = '✓'; active.setAttribute('aria-label', 'Active project'); button.append(active);
      }
      button.disabled = submitting || switchingProject || creatingProject;
      projectList.append(button);
    });
  }
  async function loadStatus() {
    const requestId = ++statusRequest;
    const selection = provider.value;
    setState('Checking provider…', 'pending');
    try {
      const response = await fetch(`/api/status?provider=${encodeURIComponent(selection)}`, { cache: 'no-store' });
      const status = await readJson(response);
      if (requestId !== statusRequest || selection !== provider.value) return;
      latest = { ...latest, ...status, steps: latest.steps || [] };
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
      currentProjectId = payload.active_project || null;
      q('#project-root').textContent = payload.projects_root || 'Projects root unavailable';
      q('#project-root').title = payload.projects_root || '';
      showProjectError(payload.error && projectItems.length ? payload.error : '');
      drawProjectList();
      const active = projectItems.find((item) => item.id === currentProjectId);
      updateProjectHeader(active);
      if (!active) {
        q('#runtime').textContent = 'No active project'; q('#runtime').className = 'problem';
        setState(payload.error || 'Select or create a project folder', 'error');
        latest = { ...latest, project: null, project_path: null, provider: null, model: null };
        render('context');
      } else await loadStatus();
    } catch (error) {
      showProjectError(error.message);
      q('#project-root').textContent = 'Could not load Projects directory';
      setState(error.message, 'error');
    } finally {
      q('#refresh-projects').disabled = false;
    }
  }
  async function switchProject(projectId) {
    if (submitting || switchingProject || creatingProject || !projectId || projectId === currentProjectId) return;
    switchingProject = true; setProjectBusy(true); send.disabled = true; input.disabled = true;
    setState('Switching project…', 'pending');
    try {
      const response = await fetch('/api/project', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_id: projectId }),
      });
      const payload = await readJson(response);
      if (!response.ok) throw new Error(payload.error || `Project switch failed (${response.status}).`);
      currentProjectId = payload.active_project;
      latest = { ...latest, project: payload.project.name, project_path: payload.project.path, steps: [], error: null };
      clearConversation(); updateProjectHeader(payload.project); drawProjectList();
      setState('Project switched · new conversation', 'success');
      closeSidebar(); await loadStatus();
    } catch (error) {
      showProjectError(error.message); setState(error.message, 'error');
      await refreshProjects();
    } finally {
      switchingProject = false; setProjectBusy(false); send.disabled = false; input.disabled = false;
      drawProjectList(); input.focus();
    }
  }
  function openProjectDialog() {
    q('#dialog-error').hidden = true; q('#dialog-error').textContent = '';
    projectForm.reset(); dialog.showModal(); projectNameInput.focus();
  }
  async function createProject(event) {
    event.preventDefault();
    if (creatingProject || submitting || switchingProject) return;
    creatingProject = true; setProjectBusy(true);
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
      latest = { ...latest, project: payload.project.name, project_path: payload.project.path, steps: [], error: null };
      clearConversation(); dialog.close(); updateProjectHeader(payload.project);
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
    if (!message || submitting || switchingProject || creatingProject || !currentProjectId) return;
    submitting = true; send.disabled = true; provider.disabled = true; input.disabled = true;
    q('#cancel').disabled = false; setProjectBusy(true);
    activeController = new AbortController(); activeAssistant = null; streamedResponse = '';
    latest = { ...latest, steps: [], error: null };
    setState('Starting Chief Agent…', 'pending'); addMessage('user', message);
    try {
      const response = await fetch('/api/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, provider: provider.value, project_id: currentProjectId }),
        signal: activeController.signal,
      });
      await window.LAEWStream.readEventStream(response, (event) => {
        if (event.type === 'start') {
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
          latest = { ...latest, steps: [...(latest.steps || []), event.step] };
          render();
        } else if (event.type === 'done') {
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
      const cancelled = error.name === 'AbortError';
      latest = { ...latest, error: cancelled ? 'Response cancelled.' : error.message, steps: latest.steps || [] };
      if (activeAssistant) activeAssistant.article.classList.add('incomplete');
      addMessage('assistant', `${latest.error} ${cancelled ? 'The partial response is incomplete.' : 'Check provider availability and retry.'}`, 'error');
      setState(cancelled ? 'Cancelled · partial response retained' : 'Run failed — revise and retry', 'error');
    } finally {
      submitting = false; activeController = null; activeAssistant = null;
      send.disabled = false; q('#cancel').disabled = true; provider.disabled = false; input.disabled = false; setProjectBusy(false);
      drawProjectList(); render('run'); input.focus();
    }
  }
  q('#cancel').addEventListener('click', () => activeController?.abort());
  function closeSidebar() {
    q('#sidebar').classList.remove('open');
    q('#sidebar-toggle').setAttribute('aria-expanded', 'false');
  }

  form.addEventListener('submit', submit);
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); form.requestSubmit(); }
  });
  provider.addEventListener('change', loadStatus);
  projectList.addEventListener('click', (event) => {
    const button = event.target.closest('[data-project-id]');
    if (button) switchProject(button.dataset.projectId);
  });
  q('#refresh-projects').addEventListener('click', refreshProjects);
  q('#new-project').addEventListener('click', openProjectDialog);
  projectForm.addEventListener('submit', createProject);
  q('#dialog-close').addEventListener('click', () => dialog.close());
  q('#dialog-cancel').addEventListener('click', () => dialog.close());
  q('#dialog-project-root').textContent = 'Projects';
  document.querySelectorAll('.tab').forEach((button) => button.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach((item) => {
      const selected = item === button; item.classList.toggle('active', selected); item.setAttribute('aria-selected', String(selected));
    });
    render(button.dataset.tab);
  }));
  q('#context-toggle').addEventListener('click', () => {
    const context = q('#context'); context.classList.toggle('hidden');
    q('#context-toggle').setAttribute('aria-expanded', String(!context.classList.contains('hidden')));
  });
  q('#sidebar-toggle').addEventListener('click', () => {
    const sidebar = q('#sidebar'); const open = sidebar.classList.toggle('open');
    q('#sidebar-toggle').setAttribute('aria-expanded', String(open));
  });
  const syncResponsivePanels = () => {
    if (window.matchMedia('(max-width: 880px)').matches) {
      q('#context').classList.add('hidden'); q('#context-toggle').setAttribute('aria-expanded', 'false');
    } else {
      closeSidebar(); q('#context').classList.remove('hidden'); q('#context-toggle').setAttribute('aria-expanded', 'true');
    }
  };
  window.addEventListener('resize', syncResponsivePanels);
  conversation.addEventListener('click', (event) => {
    const button = event.target.closest('[data-prompt]');
    if (!button) return; input.value = button.dataset.prompt; input.focus();
  });
  syncResponsivePanels(); render(); refreshProjects();
})();
