/* Browser regression driven through Chromium's DevTools protocol (Node 22+). */
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const {readFile} = require('node:fs/promises');
const {join} = require('node:path');
const {setTimeout: sleep} = require('node:timers/promises');

async function waitFor(check, label) {
  const deadline = Date.now() + 8000;
  while (Date.now() < deadline) {
    const result = await check();
    if (result) return result;
    await sleep(30);
  }
  throw new Error(`Timed out waiting for ${label}`);
}

async function main() {
  const [executable, profile, base] = process.argv.slice(2);
  const browser = spawn(executable, [
    '--headless=new', '--no-first-run', '--disable-background-networking',
    '--disable-component-update', '--disable-sync', '--remote-debugging-port=0',
    '--window-size=1280,900', `--user-data-dir=${profile}`, 'about:blank',
  ], {stdio: 'ignore', windowsHide: true});
  let launchError;
  browser.on('error', error => { launchError = error; });
  let socket;
  let command;
  try {
    const port = await waitFor(async () => {
      if (launchError) throw launchError;
      if (browser.exitCode) throw new Error(`Browser exited with ${browser.exitCode}`);
      return (await readFile(join(profile, 'DevToolsActivePort'), 'utf8').catch(() => '')).split(/\r?\n/)[0];
    }, 'browser debugging port');
    const pages = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
    socket = new WebSocket(pages.find(page => page.type === 'page').webSocketDebuggerUrl);
    await new Promise((resolve, reject) => {
      socket.addEventListener('open', resolve, {once: true});
      socket.addEventListener('error', reject, {once: true});
    });
    let sequence = 0;
    const pending = new Map();
    socket.addEventListener('message', ({data}) => {
      const reply = JSON.parse(data);
      pending.get(reply.id)?.(reply);
      pending.delete(reply.id);
    });
    command = (method, params = {}) => new Promise((resolve, reject) => {
      const id = ++sequence;
      pending.set(id, reply => reply.error ? reject(new Error(reply.error.message)) : resolve(reply.result));
      socket.send(JSON.stringify({id, method, params}));
    });
    const evaluate = async expression => {
      const result = await command('Runtime.evaluate', {expression, returnByValue: true});
      if (result.exceptionDetails) throw new Error(result.result.description);
      return result.result.value;
    };
    const click = selector => evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
    const text = () => evaluate('document.querySelector("#panel")?.innerText');
    const expectPanel = async pattern => {
      try {
        await waitFor(async () => pattern.test(await text()), pattern);
      } catch (error) {
        throw new Error(`${error.message}\nPanel: ${await text()}\nState: ${await evaluate('document.querySelector("#state")?.textContent')}`);
      }
    };
    const choose = value => evaluate(`{
      const select = document.querySelector('#diagnostic-turn');
      select.selectedIndex = ${value};
      select.dispatchEvent(new Event('change'));
    }`);
    const submit = prompt => evaluate(`{
      document.querySelector('#message').value = ${JSON.stringify(prompt)};
      document.querySelector('#composer').requestSubmit();
    }`);
    const release = async gate => assert.equal((await fetch(`${base}/release/${gate}`)).status, 204);

    await command('Page.navigate', {url: base});
    await expectPanel(/General Chat/);
    await expectPanel(/test model/);
    await expectPanel(/Synchronization: ready/);
    await evaluate('document.querySelector("#panel button").focus()');
    await click('#panel button');
    await expectPanel(/Synchronization: requested/);
    await click('#tab-run');
    await submit('What are my hobbies and what is documented in Global Knowledge?');
    await expectPanel(/Run · Live/);
    await expectPanel(/started\s+FilesystemTool/);
    await expectPanel(/failed\s+Model request\s+Iteration 1 · Attempt 1/);
    assert.equal(await evaluate('document.querySelector(".tab.active").textContent'), 'Run');
    assert.equal(await evaluate('document.querySelector("#cancel").hidden'), false);
    await release('tool');
    await expectPanel(/failed\s+FilesystemTool/);
    await expectPanel(/completed\s+FilesystemTool/);
    await expectPanel(/started\s+Model request · resumed/);
    assert.equal(await evaluate('document.querySelectorAll(".tool-card b").length'), 9);

    await click('#tab-sources');
    await expectPanel(/Long-Term Memory[\s\S]*1 selected · 1 supplied to provider adapter/);
    await expectPanel(/Global Knowledge[\s\S]*Automatic prefetch · found/);
    await expectPanel(/Project Knowledge unavailable in General Chat/);
    await expectPanel(/Context Assembly[\s\S]*Dispatched to provider adapter/);
    await click('#tab-run');
    await release('reply');
    await expectPanel(/completed\s+Assistant response/);

    await choose(1);
    await submit('What are my hobbies?');
    await expectPanel(/A new run is active/);
    assert.match(await text(), /Turn 1 · completed · selected/);
    assert.match(await text(), /FilesystemTool/);
    await choose(0);
    await expectPanel(/Turn 2 · running/);
    assert.doesNotMatch(await text(), /FilesystemTool/);
    await click('#tab-sources');
    await expectPanel(/Automatic Memory Recall · started/);
    await release('recall');
    await expectPanel(/1 selected · 1 supplied to provider adapter/);
    await expectPanel(/Model-initiated RagTool · found/);
    await expectPanel(/Global Knowledge RagTool · .*1 supplied to provider adapter/);
    await expectPanel(/Turn 2 · running/);
    assert.equal(await evaluate('document.querySelector(".tab.active").textContent'), 'Sources');
    await click('#cancel');
    await expectPanel(/Turn 2 · cancelled/);
    await command('Page.reload');
    await waitFor(() => evaluate('document.querySelector("#conversation")?.innerText.includes("Fixture final response")'),
      'restored conversation');
    await click('#tab-run');
    await expectPanel(/Turn 2 · cancelled/);
    await click('#tab-sources');
    await expectPanel(/Model-initiated RagTool · found/);
    await choose(1);
    assert.doesNotMatch(await text(), /Model-initiated RagTool · found/);
    await click('#tab-run');
    await expectPanel(/completed\s+FilesystemTool/);
    await click('#tab-sources');
    await expectPanel(/1 selected · 1 supplied to provider adapter/);
    assert.equal(await evaluate('document.querySelector("#diagnostic-turn").selectedIndex'), 1);

    await command('Emulation.setDeviceMetricsOverride', {width: 390, height: 760, deviceScaleFactor: 1, mobile: false});
    await waitFor(() => evaluate('document.querySelector("#context").classList.contains("hidden")'), 'responsive details drawer');
    await click('#context-toggle');
    await expectPanel(/Context Assembly/);
    assert.equal(await evaluate('document.documentElement.scrollWidth <= window.innerWidth'), true);

    await command('Emulation.clearDeviceMetricsOverride');
    const legacy = '.conversation-open[title="Legacy fixture"]';
    await waitFor(() => evaluate(`document.querySelector('${legacy}')?.disabled === false`), 'conversation picker');
    await click(legacy);
    await expectPanel(/Diagnostic data unavailable for this turn/);
    assert.doesNotMatch(await text(), /1 selected/);
    const {conversations} = await (await fetch(`${base}/api/conversations`)).json();
    const project = conversations.find(chat => chat.title === 'Project fixture');
    const forbidden = await fetch(`${base}/api/conversation?` + new URLSearchParams({id: project.id, project_id: project.project_id}));
    assert.equal(forbidden.status, 403);
    await waitFor(() => evaluate('document.querySelector(\'.group-select[title="active"]\')?.disabled === false'), 'project picker');
    await click('.group-select[title="active"]');
    await click('#tab-setup');
    await expectPanel(/Active project/);
    assert.doesNotMatch(await text(), /Context Assembly|Turn 1/);
    await click('#tab-sources');
    await expectPanel(/Choose a conversation turn/);
    assert.doesNotMatch(await text(), /Turn 1|1 selected/);
  } finally {
    if (socket?.readyState === WebSocket.OPEN && command) {
      await Promise.race([command('Browser.close').catch(() => {}), sleep(500)]);
    }
    socket?.close();
    browser.kill();
  }
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
