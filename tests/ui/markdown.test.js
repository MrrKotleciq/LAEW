const test = require('node:test');
const assert = require('node:assert/strict');
const { parseMarkdown, renderMarkdown } = require('../../laew/ui/markdown.js');

class Element {
  constructor(tagName, ownerDocument) {
    this.tagName = tagName.toUpperCase(); this.ownerDocument = ownerDocument;
    this.children = []; this.dataset = {}; this.style = {}; this.attributes = {};
    this._text = '';
  }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = [...nodes]; this._text = ''; }
  set textContent(value) { this.children = []; this._text = String(value); }
  get textContent() { return this._text + this.children.map((child) => child.textContent).join(''); }
  setAttribute(key, value) { this.attributes[key] = value; }
}
class Document {
  createElement(tag) { return new Element(tag, this); }
  createTextNode(text) { return { textContent: String(text) }; }
}

test('Unicode survives Markdown tables and code blocks', () => {
  const target = new Element('div', new Document());
  renderMarkdown(target, '| Nazwa | Wartość |\n|---|---|\n| Zażółć | 25°C 🐕 |\n\n```\n🧬 — 🤝 🐶\n```');
  assert.equal(target.children[0].textContent, 'NazwaWartośćZażółć25°C 🐕');
  assert.equal(target.children[1].textContent, '🧬 — 🤝 🐶');
});

test('renders headings, paragraphs, lists, links, and fenced code safely', () => {
  const target = new Element('div', new Document());
  const source = '# Heading\n\nA [safe link](https://example.test) and `inline`.\n\n- one\n- two\n\n```py\nprint(1)\n```\n\n<script>alert(1)</script>';
  renderMarkdown(target, source);
  const tags = target.children.map((node) => node.tagName);
  assert.deepEqual(tags, ['H1', 'P', 'UL', 'PRE', 'P']);
  assert.equal(target.children[1].children.find((node) => node.tagName === 'A').rel, 'noopener noreferrer');
  assert.equal(target.children[3].children[0].textContent, 'print(1)');
  assert.equal(target.children[4].children[0].textContent, '<script>alert(1)</script>');
});

test('parses complete GFM tables into headers, aligned cells, and rows', () => {
  const blocks = parseMarkdown('| Name | Count |\n|:---|---:|\n| sensors | 12 |\n| relays | 3 |');
  assert.equal(blocks[0].type, 'table');
  assert.deepEqual(blocks[0].headers, ['Name', 'Count']);
  assert.deepEqual(blocks[0].alignment, ['left', 'right']);
  assert.deepEqual(blocks[0].rows, [['sensors', '12'], ['relays', '3']]);
  const target = new Element('div', new Document());
  renderMarkdown(target, '| Name | Count |\n|:---|---:|\n| sensors | 12 |');
  assert.equal(target.children[0].children[0].tagName, 'TABLE');
  assert.equal(target.children[0].children[0].children[0].children[0].children[0].tagName, 'TH');
});

test('partially streamed table separator still renders as a readable table', () => {
  const blocks = parseMarkdown('| Name | Count |\n|:---|---');
  assert.equal(blocks[0].type, 'table');
  assert.deepEqual(blocks[0].headers, ['Name', 'Count']);
  assert.deepEqual(blocks[0].rows, []);
  const nextChunk = parseMarkdown('| Name | Count |\n|:---|---:|\n| sensors |');
  assert.deepEqual(nextChunk[0].rows, [['sensors']]);
  const target = new Element('div', new Document());
  renderMarkdown(target, '| Name | Count |\n|:---|---:|\n| sensors |');
  const bodyRow = target.children[0].children[0].children[1].children[0];
  assert.equal(bodyRow.children.length, 2);
  assert.equal(bodyRow.children[1].textContent, '');
});

test('javascript links and raw HTML never become executable DOM nodes', () => {
  const target = new Element('div', new Document());
  renderMarkdown(target, '[unsafe](javascript:alert(1))\n\n<img src=x onerror=alert(1)>');
  assert.equal(target.children[0].tagName, 'P');
  assert.equal(target.children[0].children.some((node) => node.tagName === 'A'), false);
  assert.equal(target.children[1].tagName, 'P');
  assert.equal(target.children[1].children[0].textContent, '<img src=x onerror=alert(1)>');
});
