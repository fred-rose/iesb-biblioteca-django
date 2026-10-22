// Chrome DevTools Protocol nativo; sem pacotes npm.
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';

let input = '';
for await (const chunk of process.stdin) input += chunk;
const config = JSON.parse(input);
const edge = [
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
].find(existsSync);
if (!edge) throw new Error('Microsoft Edge não encontrado.');
const browser = spawn(edge, [
  '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--in-process-gpu',
  // Ambiente de captura restrito: navega apenas no servidor local com dados fictícios.
  '--no-sandbox',
  '--remote-debugging-port=0', `--user-data-dir=${config.profile}`, 'about:blank',
], { windowsHide: true, stdio: ['ignore', 'ignore', 'pipe'] });
let browserErrors = '';
browser.stderr.on('data', chunk => { browserErrors += chunk.toString(); });
browser.on('exit', code => { if (code) console.error(`Edge terminou (${code}): ${browserErrors}`); });
let socket;
try {
  let port;
  for (let attempt = 0; attempt < 100; attempt++) {
    try {
      port = Number((await readFile(path.join(config.profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0]);
      break;
    } catch { await delay(100); }
  }
  if (!port) throw new Error('Edge não disponibilizou a porta de depuração.');
  const target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json();
  socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.addEventListener('open', resolve, { once: true });
    socket.addEventListener('error', reject, { once: true });
  });
  let sequence = 0;
  const pending = new Map();
  const waiters = new Map();
  socket.addEventListener('close', ({ code, reason }) => {
    for (const request of pending.values()) request.reject(new Error(`Edge encerrou a conexão: ${code} ${reason}`));
    pending.clear();
  });
  socket.addEventListener('message', ({ data }) => {
    const message = JSON.parse(data);
    if (message.id) {
      const request = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) request?.reject(new Error(message.error.message));
      else request?.resolve(message.result);
    } else {
      waiters.get(message.method)?.();
      waiters.delete(message.method);
    }
  });
  function send(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = ++sequence;
      const timeout = setTimeout(() => { pending.delete(id); reject(new Error(`Timeout CDP: ${method}`)); }, 15000);
      pending.set(id, {
        resolve: result => { clearTimeout(timeout); resolve(result); },
        reject: error => { clearTimeout(timeout); reject(error); },
      });
      socket.send(JSON.stringify({ id, method, params }));
    });
  }
  function event(method) {
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => { waiters.delete(method); reject(new Error(`Timeout: ${method}`)); }, 15000);
      waiters.set(method, () => { clearTimeout(timeout); resolve(); });
    });
  }
  await send('Page.enable');
  await send('Network.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1080, deviceScaleFactor: 1, mobile: false });
  await send('Network.setCookie', {
    name: config.sessionName, value: config.session, url: config.baseUrl,
    httpOnly: true, sameSite: 'Lax',
  });
  const output = path.join(config.root, 'docs', 'prints');
  await mkdir(output, { recursive: true });
  for (const [name, route, expected] of [
    ['01-admin.png', '/admin/', 'Administração da Biblioteca'],
    ['02-catalogo.png', '/', 'Uma nova leitura começa aqui.'],
    ['03-emprestimos-atraso.png', '/emprestimos/', 'Atrasado'],
    ['04-catalogo-mobile.png', '/', 'Uma nova leitura começa aqui.'],
  ]) {
    if (name.includes('mobile')) {
      await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
    }
    const loaded = event('Page.loadEventFired');
    await send('Page.navigate', { url: config.baseUrl + route });
    await loaded;
    const checked = await send('Runtime.evaluate', {
      expression: `document.body.innerText.includes(${JSON.stringify(expected)})`, returnByValue: true,
    });
    if (!checked.result.value) throw new Error(`Conteúdo esperado não encontrado: ${route}`);
    const dimensions = await send('Runtime.evaluate', {
      expression: 'document.documentElement.scrollWidth <= window.innerWidth', returnByValue: true,
    });
    if (!dimensions.result.value) throw new Error(`Overflow horizontal: ${route}`);
    const image = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
    await writeFile(path.join(output, name), Buffer.from(image.data, 'base64'));
    console.log(`Captura real salva: docs/prints/${name}`);
  }
  await send('Browser.close');
  await new Promise(resolve => browser.once('exit', resolve));
  // Permite que os processos filhos liberem os arquivos do perfil no Windows.
  await delay(1000);
} catch (error) {
  console.error(browserErrors);
  throw error;
} finally {
  socket?.close();
  if (browser.exitCode === null) browser.kill();
}
