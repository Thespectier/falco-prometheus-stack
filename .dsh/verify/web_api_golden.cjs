/**
 * 前端 API 层（web/src/api/client.ts）请求级黄金输出验证。
 *
 * 做法：用项目自带的 tsc 把 client.ts 编译成 ESM，在 Node 里把 `import.meta.env`
 * 换成可控的全局对象后求值，桩掉 `fetch`，逐个方法调用并记录
 * `(url, method, headers, body)` 与返回值。改造前后输出必须逐字节一致。
 *
 * 运行：node .dsh/verify/web_api_golden.cjs <输出文件>
 */

const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const HERE = __dirname;
const ROOT = path.dirname(path.dirname(HERE));
const WEB = path.join(ROOT, 'web');
const OUT = path.join(HERE, 'tmp', 'web');

fs.rmSync(OUT, { recursive: true, force: true });
fs.mkdirSync(OUT, { recursive: true });

// Node 26 下 execFileSync 不能直接执行 .cmd，改为用 node 跑 tsc 的 JS 入口。
// --noCheck：这里只要产物，类型闸门由项目级 `tsc --noEmit` 负责。
const tsc = path.join(WEB, 'node_modules', 'typescript', 'bin', 'tsc');
execFileSync(
  process.execPath,
  [tsc, 'src/api/client.ts', '--outDir', OUT, '--module', 'es2020', '--target', 'es2020', '--noCheck'],
  { cwd: WEB, stdio: 'inherit' }
);

function loadClient(baseUrl) {
  let source = fs.readFileSync(path.join(OUT, 'client.js'), 'utf8');
  source = source.replace(/import\.meta\.env/g, 'globalThis.__VITE_ENV__');
  source = source.replace(/^export /gm, '');
  globalThis.__VITE_ENV__ = { BASE_URL: baseUrl };
  return new Function(source + '\nreturn { api, ApiClient };')();
}

const REQUESTS = [];
const PLAN = { ok: true, statusText: 'OK', payload: {} };

globalThis.fetch = async (url, init = {}) => {
  REQUESTS.push({
    url,
    method: init.method || 'GET',
    headers: init.headers || null,
    body: init.body === undefined ? null : init.body,
  });
  if (!PLAN.ok) {
    return { ok: false, statusText: PLAN.statusText, json: async () => ({}) };
  }
  return { ok: true, statusText: 'OK', json: async () => PLAN.payload };
};

const RESULTS = [];

function scenario(name, fn) {
  REQUESTS.length = 0;
  let value = null;
  let error = null;
  try {
    value = fn();
  } catch (exc) {
    error = `${exc.constructor.name}: ${exc.message}`;
  }
  RESULTS.push({ case: name, value, error, requests: REQUESTS.slice() });
}

async function scenarioAsync(name, fn) {
  REQUESTS.length = 0;
  let value = null;
  let error = null;
  try {
    value = await fn();
  } catch (exc) {
    error = `${exc.constructor.name}: ${exc.message}`;
  }
  RESULTS.push({ case: name, value, error, requests: REQUESTS.slice() });
}

async function main() {
  const { api } = loadClient('/');

  scenario('client.base_url_root', () => api.baseURL);

  PLAN.payload = { total_events_rate: 1.5 };
  await scenarioAsync('client.get_overview', () => api.getOverview());

  PLAN.payload = [{ id: 'nginx', name: 'nginx', last_seen: 1, event_rate: 2 }];
  await scenarioAsync('client.list_containers', () => api.listContainers());

  PLAN.payload = { container_id: 'nginx', alerts: [] };
  await scenarioAsync('client.alerts_defaults', () => api.getContainerAlerts('nginx'));
  await scenarioAsync('client.alerts_args', () => api.getContainerAlerts('web api', 60, 10, 5));

  PLAN.payload = { container_id: 'nginx', hbt_structure: { name: 'root' } };
  await scenarioAsync('client.hbt_snapshot', () => api.getHbtSnapshot('nginx'));

  PLAN.payload = { container_id: 'nginx', logs: [] };
  await scenarioAsync('client.container_logs', () => api.getContainerLogs('nginx'));

  PLAN.payload = [];
  await scenarioAsync('client.incidents_no_filter', () => api.getIncidents());
  await scenarioAsync('client.incidents_container', () => api.getIncidents('nginx', 30, 2, 1));
  await scenarioAsync('client.incidents_empty_container', () => api.getIncidents('', 30, 2, 1));

  PLAN.payload = { api_key: '********', endpoint: 'https://api.deepseek.com', model: 'deepseek-chat' };
  await scenarioAsync('client.get_llm_config', () => api.getLLMConfig());
  await scenarioAsync('client.set_llm_config', () => api.setLLMConfig({ api_key: 'sk-new', endpoint: 'e', model: 'm' }));

  PLAN.ok = false;
  PLAN.statusText = 'Not Found';
  await scenarioAsync('client.get_error', () => api.getOverview());
  await scenarioAsync('client.post_error', () => api.setLLMConfig({ api_key: 'k' }));
  PLAN.ok = true;
  PLAN.statusText = 'OK';

  // 非根 basename：Vite 注入的 BASE_URL 带业务前缀时的地址拼装
  const prefixed = loadClient('/infrasecurity/');
  scenario('client.base_url_prefixed', () => prefixed.api.baseURL);
  PLAN.payload = [];
  await scenarioAsync('client.prefixed_overview', () => prefixed.api.getOverview());

  const payload = JSON.stringify(RESULTS, null, 2);
  if (process.argv[2]) {
    fs.writeFileSync(process.argv[2], payload + '\n', 'utf8');
  } else {
    process.stdout.write(payload);
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
