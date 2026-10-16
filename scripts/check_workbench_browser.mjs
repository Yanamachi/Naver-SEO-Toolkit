// Local Chrome QA only: no app server, downloads, or customer website requests.
import {spawn} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';

const input = path.resolve(process.argv[2] || 'customer-data/projects/JOB-DEMO-SEO-FINAL/dashboard.html');
const output = path.resolve(process.argv[3] || 'results/step3_1/browser');
const chrome = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
assert(fs.statSync(input).isFile(), 'Generate dashboard.html first');
fs.mkdirSync(output, {recursive: true});
const profile = fs.mkdtempSync(path.join(output, 'chrome-'));
const child = spawn(chrome, ['--headless', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--disable-background-networking', '--disable-component-update', '--disable-sync', '--disable-extensions',
  '--host-resolver-rules=MAP * ~NOTFOUND', '--remote-debugging-port=0', '--remote-debugging-address=127.0.0.1',
  '--user-data-dir=' + profile, 'about:blank'], {stdio: 'ignore', windowsHide: true});
let socket;
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const errors = [], network = [], checks = [];
let startupError;
child.on('error', error => { startupError = error; });
async function waitUntil(test, label) {
  const deadline = Date.now() + 15000;
  while (Date.now() < deadline) {
    if (startupError) throw startupError;
    if (await test()) return;
    await delay(50);
  }
  throw Error('Timed out: ' + label);
}

try {
  const portFile = path.join(profile, 'DevToolsActivePort');
  await waitUntil(() => fs.existsSync(portFile), 'Chrome startup');
  const [port, endpoint] = fs.readFileSync(portFile, 'utf8').trim().split(/\r?\n/);
  socket = new WebSocket('ws://127.0.0.1:' + port + endpoint);
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
  let sequence = 0;
  const pending = new Map();
  socket.onmessage = event => {
    const data = JSON.parse(event.data);
    if (data.id) {
      const call = pending.get(data.id);
      if (!call) return;
      pending.delete(data.id);
      data.error ? call.reject(Error(data.error.message)) : call.resolve(data.result);
    }
    if (data.method === 'Runtime.exceptionThrown') errors.push(data.params.exceptionDetails.text);
    if (data.method === 'Network.requestWillBeSent' && /^https?:/.test(data.params.request.url)) network.push(data.params.request.url);
  };
  const send = (method, params = {}, sessionId) => new Promise((resolve, reject) => {
    const id = ++sequence;
    pending.set(id, {resolve, reject});
    socket.send(JSON.stringify({id, method, params, ...(sessionId ? {sessionId} : {})}));
    setTimeout(() => { if (pending.delete(id)) reject(Error('CDP timeout: ' + method)); }, 15000).unref();
  });
  const {targetId} = await send('Target.createTarget', {url: 'about:blank'});
  const {sessionId} = await send('Target.attachToTarget', {targetId, flatten: true});
  const tab = (method, params) => send(method, params, sessionId);
  await tab('Page.enable');
  await tab('Runtime.enable');
  await tab('Network.enable');
  await tab('Network.setBlockedURLs', {urls: ['http://*', 'https://*']});
  const evaluate = async expression => {
    const response = await tab('Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true, userGesture: true});
    assert(!response.exceptionDetails, JSON.stringify(response.exceptionDetails));
    return response.result.value;
  };
  await tab('Emulation.setDeviceMetricsOverride', {width: 1440, height: 1100, deviceScaleFactor: 1, mobile: false});
  await tab('Page.navigate', {url: pathToFileURL(input).href});
  await waitUntil(() => evaluate('!!document.querySelector("[data-stage-link].is-active")'), 'hashed UI script');
  assert.equal(await evaluate('document.querySelectorAll("[data-stage-panel]:not([hidden])").length'), 1);
  checks.push('CSP-authorized script and initial stage');
  const stages = await evaluate('[...document.querySelectorAll("[data-stage-panel]")].map(e => e.id)');
  for (const id of stages) {
    await evaluate(`document.querySelector('[href="#${id}"]').click()`);
    assert.equal(await evaluate('document.querySelector("[data-stage-panel]:not([hidden])").id'), id);
  }
  checks.push('all eight stage selections');
  await evaluate(`document.querySelector('[href="#stage-environment"]').click(); document.querySelector('#stage-environment details summary').click()`);
  assert.equal(await evaluate('document.querySelector("#stage-environment details").open'), true);
  checks.push('native details expand');
  await evaluate(`Object.defineProperty(navigator, 'clipboard', {configurable:true, value:{writeText:async text => {window.__copied=text;}}})`);
  await evaluate(`document.querySelector('[href="#stage-intake"]').click()`);
  const cliText = await evaluate('document.querySelector("#stage-intake pre[id]").textContent');
  await evaluate('document.querySelector("#stage-intake [data-copy]").click()');
  await waitUntil(async () => (await evaluate('window.__copied')) === cliText, 'CLI copy');
  await evaluate(`document.querySelector('[href="#stage-review"]').click()`);
  // The first copyable review card may be CLI; specifically locate Codex copy.
  const expectedBrief = await evaluate(`document.getElementById([...document.querySelectorAll('#stage-review [data-copy]')].find(b => b.textContent.includes('Codex')).dataset.copy).textContent`);
  await evaluate('[...document.querySelectorAll("#stage-review [data-copy]")].find(b => b.textContent.includes("Codex")).click()');
  await waitUntil(async () => (await evaluate('window.__copied')) === expectedBrief, 'Codex copy');
  assert(String(await evaluate('window.__copied')).includes('\n'));
  checks.push('CLI and bounded Codex text copied (clipboard stub; OS clipboard unchanged)');
  await evaluate(`navigator.clipboard.writeText = async () => {throw Error('denied')}; document.execCommand = () => {window.__fallback=document.querySelector('textarea').value; return true;}; [...document.querySelectorAll('#stage-review [data-copy]')].find(b => b.textContent.includes('복사')).click();`);
  await waitUntil(() => evaluate('typeof window.__fallback === "string"'), 'clipboard fallback');
  await evaluate('document.execCommand = () => false; document.querySelector("#stage-review [data-copy]").click()');
  await waitUntil(() => evaluate('document.getElementById("copy-status").textContent.includes("직접 선택")'), 'clipboard failure message');
  checks.push('clipboard denial fallback and manual selection message');
  await evaluate(`document.querySelector('[href="#stage-intake"]').click()`);
  await evaluate(`document.getElementById('copy-status').textContent='';document.querySelectorAll('[data-copy]').forEach(b=>{b.textContent=b.getAttribute('aria-label').includes('Codex')?'Codex 검토 지침 복사':'명령어 복사'});window.scrollTo(0,0)`);
  fs.writeFileSync(path.join(output, 'desktop.png'), Buffer.from((await tab('Page.captureScreenshot', {format: 'png'})).data, 'base64'));
  await evaluate(`document.querySelector('[href="#stage-seo"]').click()`);
  fs.writeFileSync(path.join(output, 'seo.png'), Buffer.from((await tab('Page.captureScreenshot', {format: 'png'})).data, 'base64'));
  await tab('Emulation.setDeviceMetricsOverride', {width: 390, height: 900, deviceScaleFactor: 1, mobile: true});
  const originalPill = await evaluate(`document.querySelector('.sidebar .pill').textContent`);
  await evaluate(`document.querySelector('.sidebar .pill').textContent='NEED_REVIEW · 담당자 검토 필요'`);
  for (const id of stages) {
    await evaluate(`document.querySelector('[href="#${id}"]').click()`);
    assert(await evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Mobile horizontal overflow: ' + id);
  }
  await evaluate(`document.querySelector('[href="#stage-intake"]').click()`);
  await evaluate(`document.querySelector('.sidebar .pill').textContent=${JSON.stringify(originalPill)}`);
  await evaluate('window.scrollTo(0,0)');
  fs.writeFileSync(path.join(output, 'mobile.png'), Buffer.from((await tab('Page.captureScreenshot', {format: 'png'})).data, 'base64'));
  checks.push('desktop/mobile rendering and no mobile horizontal overflow in all stages');
  const reportHrefs = await evaluate('[...document.querySelectorAll(".report-links a")].map(a => a.getAttribute("href"))');
  for (const href of reportHrefs) {
    assert(/^\.\/[a-z-]+\.html$/.test(href));
    assert(fs.statSync(path.resolve(path.dirname(input), href)).isFile());
  }
  checks.push('existing report links resolve to local files');
  if (reportHrefs.length) {
    const firstReportURL = pathToFileURL(path.resolve(path.dirname(input), reportHrefs[0])).href;
    const previous = new Set((await send('Target.getTargets')).targetInfos.map(t => t.targetId));
    await evaluate(`document.querySelector('.report-links a').click()`);
    let opened;
    await waitUntil(async () => {
      opened = (await send('Target.getTargets')).targetInfos.find(t => !previous.has(t.targetId) && t.url === firstReportURL);
      return !!opened;
    }, 'local report open');
    await send('Target.closeTarget', {targetId: opened.targetId});
    checks.push('report open button opens the existing local HTML');
  }
  assert.equal(network.length, 0, 'No external HTTP requests');
  assert.equal(errors.length, 0, 'No runtime exceptions');
  fs.writeFileSync(path.join(output, 'checks.json'), JSON.stringify({checks, runtime_errors: errors, external_requests: network, stages: stages.length, report_links: reportHrefs}, null, 2));
  console.log(JSON.stringify({passed: checks.length, checks, output}, null, 2));
  await send('Browser.close');
} finally {
  socket?.close();
  child.kill();
}
