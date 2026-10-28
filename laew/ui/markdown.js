/* Safe, dependency-free Markdown subset with GitHub-style tables. */
(() => {
  const splitCells = (line) => {
    let value = line.trim();
    if (value.startsWith('|')) value = value.slice(1);
    if (value.endsWith('|')) value = value.slice(0, -1);
    return value.split('|').map((cell) => cell.trim());
  };
  const isTableRow = (line) => line.includes('|');
  const isTableRule = (line) => {
    if (!isTableRow(line)) return false;
    const cells = splitCells(line);
    return cells.length > 0 && cells.every((cell) => /^:?-{1,}:?$/.test(cell));
  };
  const inline = (source) => {
    const tokens = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*|\[[^\]]+\]\([^)]+\))/g;
    const output = [];
    let offset = 0;
    for (const match of source.matchAll(tokens)) {
      if (match.index > offset) output.push({ type: 'text', text: source.slice(offset, match.index) });
      const value = match[0];
      if (value.startsWith('`')) output.push({ type: 'code', text: value.slice(1, -1) });
      else if (value.startsWith('**')) output.push({ type: 'strong', text: value.slice(2, -2) });
      else if (value.startsWith('*')) output.push({ type: 'em', text: value.slice(1, -1) });
      else {
        const link = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(value);
        output.push({ type: 'link', text: link[1], href: link[2].trim() });
      }
      offset = match.index + value.length;
    }
    if (offset < source.length) output.push({ type: 'text', text: source.slice(offset) });
    return output;
  };
  function parseMarkdown(source) {
    const lines = String(source).replace(/\r\n?/g, '\n').split('\n');
    const blocks = [];
    for (let index = 0; index < lines.length;) {
      const line = lines[index];
      if (!line.trim()) { index++; continue; }
      const fence = /^\s*```([^`]*)$/.exec(line);
      if (fence) {
        const code = []; index++;
        while (index < lines.length && !/^\s*```\s*$/.test(lines[index])) code.push(lines[index++]);
        if (index < lines.length) index++;
        blocks.push({ type: 'codeblock', language: fence[1].trim(), text: code.join('\n') });
        continue;
      }
      const heading = /^(#{1,6})\s+(.+)$/.exec(line);
      if (heading) { blocks.push({ type: 'heading', level: heading[1].length, children: inline(heading[2]) }); index++; continue; }
      if (index + 1 < lines.length && isTableRow(line) && isTableRule(lines[index + 1])) {
        const headers = splitCells(line);
        const alignment = splitCells(lines[index + 1]).map((cell) => cell.startsWith(':') && cell.endsWith(':') ? 'center' : cell.endsWith(':') ? 'right' : 'left');
        const rows = []; index += 2;
        while (index < lines.length && isTableRow(lines[index]) && lines[index].trim()) {
          const cells = splitCells(lines[index]);
          if (cells.length) rows.push(cells);
          index++;
        }
        blocks.push({ type: 'table', headers, alignment, rows });
        continue;
      }
      const list = /^\s*(?:([-*+])|(\d+)[.)])\s+(.+)$/.exec(line);
      if (list) {
        const ordered = Boolean(list[2]); const items = [];
        while (index < lines.length) {
          const item = /^\s*(?:([-*+])|(\d+)[.)])\s+(.+)$/.exec(lines[index]);
          if (!item || Boolean(item[2]) !== ordered) break;
          items.push(inline(item[3])); index++;
        }
        blocks.push({ type: ordered ? 'ol' : 'ul', items });
        continue;
      }
      const paragraph = [line.trim()]; index++;
      while (index < lines.length && lines[index].trim() &&
        !/^\s*(?:```|#{1,6}\s|[-*+]\s|\d+[.)]\s)/.test(lines[index]) &&
        !(index + 1 < lines.length && isTableRow(lines[index]) && isTableRule(lines[index + 1]))) {
        paragraph.push(lines[index++].trim());
      }
      blocks.push({ type: 'paragraph', children: inline(paragraph.join(' ')) });
    }
    return blocks;
  }
  function safeHref(value) {
    const href = String(value || '').trim();
    if (/^(https?:|mailto:|\/|#)/i.test(href) && !/^\/\//.test(href)) return href;
    return null;
  }
  function appendInline(document, parent, children) {
    for (const node of children) {
      if (node.type === 'text') { parent.append(document.createTextNode(node.text)); continue; }
      if (node.type === 'link') {
        const href = safeHref(node.href);
        if (!href) { parent.append(document.createTextNode(node.text)); continue; }
        const link = document.createElement('a'); link.textContent = node.text; link.href = href;
        if (/^https?:/i.test(href)) { link.target = '_blank'; link.rel = 'noopener noreferrer'; }
        parent.append(link); continue;
      }
      const tag = { code: 'code', strong: 'strong', em: 'em' }[node.type];
      const element = document.createElement(tag); element.textContent = node.text; parent.append(element);
    }
  }
  function renderMarkdown(target, source) {
    const document = target.ownerDocument || globalThis.document;
    target.replaceChildren();
    for (const block of parseMarkdown(source)) {
      if (block.type === 'heading') {
        const heading = document.createElement(`h${block.level}`); appendInline(document, heading, block.children); target.append(heading);
      } else if (block.type === 'paragraph') {
        const paragraph = document.createElement('p'); appendInline(document, paragraph, block.children); target.append(paragraph);
      } else if (block.type === 'codeblock') {
        const pre = document.createElement('pre'); const code = document.createElement('code');
        if (block.language) code.dataset.language = block.language;
        code.textContent = block.text; pre.append(code); target.append(pre);
      } else if (block.type === 'ul' || block.type === 'ol') {
        const list = document.createElement(block.type);
        for (const children of block.items) { const item = document.createElement('li'); appendInline(document, item, children); list.append(item); }
        target.append(list);
      } else if (block.type === 'table') {
        const wrapper = document.createElement('div'); wrapper.className = 'table-scroll';
        const table = document.createElement('table'); const thead = document.createElement('thead'); const headRow = document.createElement('tr');
        block.headers.forEach((text, index) => { const cell = document.createElement('th'); cell.scope = 'col'; cell.style.textAlign = block.alignment[index] || 'left'; appendInline(document, cell, inline(text)); headRow.append(cell); });
        thead.append(headRow); table.append(thead); const tbody = document.createElement('tbody');
        for (const row of block.rows) { const tr = document.createElement('tr');
          block.headers.forEach((_, index) => { const cell = document.createElement('td'); cell.style.textAlign = block.alignment[index] || 'left'; appendInline(document, cell, inline(row[index] || '')); tr.append(cell); }); tbody.append(tr); }
        table.append(tbody); wrapper.append(table); target.append(wrapper);
      }
    }
  }
  const api = { parseMarkdown, renderMarkdown };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof window !== 'undefined') window.LAEWMarkdown = api;
})();
