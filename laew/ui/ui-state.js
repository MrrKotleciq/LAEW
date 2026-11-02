(function (root) {
  'use strict';
  function createPanelState() {
    let tab = 'context', switched = false;
    return {
      get active() { return tab; },
      select(value) { if (['context', 'run', 'sources'].includes(value)) tab = value; return tab; },
      beginRun() { switched = false; },
      toolEvent() { if (!switched) { switched = true; tab = 'run'; } return tab; },
      reset() { tab = 'context'; switched = false; }
    };
  }
  function modelGroups(entries, labels, accounts = []) {
    return entries.map(([key, models]) => {
      const [provider, account] = JSON.parse(key);
      return {label: labels[provider] + (account ? ' · ' + (accounts.find(a => a.id === account)?.label || 'Account') : ''),
        options: models.map(model => ({label:model.label || model.id, value:JSON.stringify([provider,model.id,account])}))};
    });
  }
  function conversationGroups(projects, conversations) {
    const groups = [{key:'general', name:'General Chat', items:[]}];
    const byId = new Map();
    projects.forEach(project => { const group={key:'project:'+project.id, name:project.name, items:[]}; byId.set(project.id,group); groups.push(group); });
    conversations.forEach(item => {
      if (item.scope_type === 'general') groups[0].items.push(item);
      else {
        let group=byId.get(item.project_id);
        if (!group) { group={key:'project:'+item.project_id, name:'Unavailable project · '+item.project_id, unavailable:true, items:[]}; byId.set(item.project_id,group); groups.push(group); }
        group.items.push(item);
      }
    });
    groups.forEach(group => group.items.sort((a,b) => String(b.updated_at || '').localeCompare(String(a.updated_at || ''))));
    return groups;
  }
  function createExpansionState(storage) {
    let groups;
    try { const value=JSON.parse(storage.get('laew-conversation-groups')); groups=value && typeof value==='object' && !Array.isArray(value) ? value : {}; }
    catch { groups={}; }
    if (!Object.hasOwn(groups,'general')) groups.general=true;
    return {
      get projectsExpanded() { return storage.get('laew-projects-expanded') !== 'false'; },
      setProjects(value) { storage.set('laew-projects-expanded',String(value)); },
      isExpanded(key) { return !!groups[key]; },
      setGroup(key,value) { groups[key]=value; storage.set('laew-conversation-groups',JSON.stringify(groups)); },
      revealConversation(key, restoring) { if (!restoring || !Object.hasOwn(groups,key)) this.setGroup(key,true); }
    };
  }
  function sidebarWidth(width, viewport, contextWidth=330) {
    const max=Math.max(210, Math.min(480, viewport-contextWidth-360));
    return Math.max(210, Math.min(max, Number.isFinite(Number(width)) ? Number(width) : 260));
  }
  const api = {createPanelState, modelGroups, conversationGroups, createExpansionState, sidebarWidth};
  if (typeof module !== 'undefined') module.exports = api;
  else root.LAEWUI = api;
})(typeof window === 'undefined' ? globalThis : window);
