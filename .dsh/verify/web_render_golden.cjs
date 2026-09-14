/**
 * 前端渲染级黄金输出验证。
 *
 * 做法：
 *   1. 用项目自带的 tsc 把 src 下的 TSX 编译成 CommonJS（`--noCheck`，类型闸门交给
 *      项目级 `tsc --noEmit`），产物落在 web/.verify-build（每次运行重建）
 *   2. 把产物里的 `import.meta.env` 换成可控全局对象
 *   3. 在 Node 里桩掉浏览器 API（fetch / WebSocket / ResizeObserver / matchMedia /
 *      localStorage），用 react-dom/server 的 renderToStaticMarkup 渲染
 *   4. 逐个场景记录 HTML 与异常；改造前后必须逐字节一致
 *
 * 不覆盖 `App.tsx`：它用 BrowserRouter，服务端渲染需要完整的 window.history，
 * 改由 `tsc --noEmit` + 路由表人工核对保证。
 *
 * 运行：node .dsh/verify/web_render_golden.cjs <输出文件>
 */

const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const HERE = __dirname;
const ROOT = path.dirname(path.dirname(HERE));
const WEB = path.join(ROOT, 'web');
const BUILD = path.join(WEB, '.verify-build');

module.paths.push(path.join(WEB, 'node_modules'));

const ENTRIES = [
  'src/components/Chart.tsx',
  'src/layout/AppLayout.tsx',
  'src/pages/Overview.tsx',
  'src/pages/Alerts.tsx',
  'src/pages/Logs.tsx',
  'src/pages/Incidents.tsx',
  'src/pages/HbtVisualizer.tsx',
  'src/pages/Settings.tsx',
];

fs.rmSync(BUILD, { recursive: true, force: true });

const tsc = path.join(WEB, 'node_modules', 'typescript', 'bin', 'tsc');
execFileSync(
  process.execPath,
  [
    tsc,
    ...ENTRIES,
    '--outDir', BUILD,
    '--module', 'commonjs',
    '--moduleResolution', 'node',
    '--target', 'es2020',
    '--jsx', 'react-jsx',
    '--esModuleInterop',
    '--noCheck',
  ],
  { cwd: WEB, stdio: 'inherit' }
);

// 产物里的 import.meta.env 在 CommonJS 下非法，替换成可控全局对象
(function patchEmitted(dir) {
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name);
    if (fs.statSync(full).isDirectory()) {
      patchEmitted(full);
    } else if (name.endsWith('.js')) {
      const source = fs.readFileSync(full, 'utf8');
      if (source.includes('import.meta.env')) {
        fs.writeFileSync(full, source.replace(/import\.meta\.env/g, 'globalThis.__VITE_ENV__'), 'utf8');
      }
    }
  }
})(BUILD);

// web/package.json 里是 "type": "module"，会让产物被当成 ESM；
// 构建目录单独标记为 CommonJS，tsc 的 commonjs 产物才能被 require
fs.writeFileSync(path.join(BUILD, 'package.json'), JSON.stringify({ type: 'commonjs' }), 'utf8');

// ---------------------------------------------------------------- 浏览器 API 桩
globalThis.__VITE_ENV__ = { BASE_URL: '/' };

const CALLS = [];
globalThis.fetch = async (url, init = {}) => {
  CALLS.push(`fetch ${init.method || 'GET'} ${url}`);
  return {
    ok: true,
    statusText: 'OK',
    json: async () => ({ status: 'ok' }),
  };
};

globalThis.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};
globalThis.matchMedia = () => ({
  matches: false,
  addListener() {},
  removeListener() {},
  addEventListener() {},
  removeEventListener() {},
});
globalThis.WebSocket = class {
  constructor(url) {
    CALLS.push(`ws ${url}`);
  }
  close() {}
  send() {}
  addEventListener() {}
  removeEventListener() {}
};

const store = new Map();
globalThis.localStorage = {
  getItem: (key) => (store.has(key) ? store.get(key) : null),
  setItem: (key, value) => store.set(key, String(value)),
  removeItem: (key) => store.delete(key),
  clear: () => store.clear(),
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const { QueryClient, QueryClientProvider } = require('@tanstack/react-query');
const { MemoryRouter, Route, Routes } = require('react-router-dom');

function load(relative) {
  return require(path.join(BUILD, relative.replace(/^src\//, '').replace(/\.tsx$/, '.js')));
}

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, gcTime: Infinity, staleTime: Infinity } },
});

/** 预置查询缓存后渲染：让页面进入"有数据"分支，否则 SSR 只会渲染 loading 空态 */
function renderWithData(element, entry, seed) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity, staleTime: Infinity } },
  });
  for (const [key, value] of seed) {
    client.setQueryData(key, value);
  }
  return renderToStaticMarkup(
    React.createElement(
      QueryClientProvider,
      { client },
      React.createElement(
        MemoryRouter,
        { initialEntries: [entry] },
        React.createElement(Routes, null, React.createElement(Route, { path: '*', element }))
      )
    )
  );
}

/**
 * 把 components/Chart 换成记录 props 的桩组件。
 *
 * Chart 在服务端只输出一个空 div，options 内容（含 formatter 函数）进不了 HTML；
 * 这里通过 require.cache 注入桩件，让 options 也能纳入黄金输出。
 */
const CHART_PATH = path.join(BUILD, 'components', 'Chart.js');

function collectChartOptions(relativeToReload) {
  const original = require.cache[CHART_PATH];
  const recorded = [];
  require.cache[CHART_PATH] = {
    id: CHART_PATH,
    filename: CHART_PATH,
    loaded: true,
    // __esModule 必须给：tsc 的 esModuleInterop 会把没有该标记的模块再包一层 default
    exports: {
      __esModule: true,
      default: (props) => { recorded.push(props); return null; },
    },
  };
  const target = path.join(BUILD, relativeToReload.replace(/^src\//, '').replace(/\.tsx$/, '.js'));
  delete require.cache[target];
  return {
    recorded,
    restore() {
      if (original) {
        require.cache[CHART_PATH] = original;
      } else {
        delete require.cache[CHART_PATH];
      }
    },
  };
}

const SAMPLE_PARAM = { name: 'node-name', data: { name: 'node-name', type: 'process_operation', events_count: 3 } };

/** 序列化 props：函数用样本参数调用一次后记录结果，其余原样 */
function serialize(value) {
  if (typeof value === 'function') {
    let sample;
    try {
      sample = String(value(SAMPLE_PARAM));
    } catch (error) {
      sample = `THREW: ${error.message}`;
    }
    return { __fn: true, sample };
  }
  if (Array.isArray(value)) {
    return value.map((item) => serialize(item));
  }
  if (value && typeof value === 'object') {
    const out = {};
    for (const key of Object.keys(value)) {
      out[key] = serialize(value[key]);
    }
    return out;
  }
  return value;
}

const SEED_CONTAINERS = [
  { id: 'nginx', name: 'nginx', last_seen: 1700000000, event_rate: 1.5 },
  { id: 'api', name: 'api', last_seen: 1700000010, event_rate: 0.5 },
];

const SEED_HBT = {
  container_id: 'nginx',
  hbt_structure: {
    name: 'root',
    type: 'root',
    events_count: 0,
    metadata: {},
    children: {
      process_branch: {
        name: 'process_branch',
        type: 'branch',
        events_count: 0,
        metadata: {},
        children: {
          execve: {
            name: 'execve',
            type: 'process_operation',
            events_count: 3,
            metadata: {},
            children: {},
          },
        },
      },
    },
  },
};

const SEED_ALERTS = {
  container_id: 'nginx',
  alerts: [
    {
      container_id: 'nginx',
      timestamp: '2024-04-30T10:00:00+08:00',
      category: 'process',
      reason: 'evt.type not matched',
      evt_type: 'openat',
      proc_name: 'bash',
      fd_name: '',
      output: '{"evt.type": "openat"}',
    },
  ],
};

const SEED_LOGS = {
  container_id: 'nginx',
  logs: [
    {
      timestamp: '2024-04-30T10:00:00+08:00',
      rule: 'process',
      priority: 'DEBUG',
      output: '{"evt.type": "execve"}',
      source: 'syscall',
      tags: ['a'],
    },
  ],
};

const SEED_INCIDENTS = [
  {
    container_id: 'nginx',
    timestamp: '2024-04-30T10:00:00+08:00',
    threat_score: 85.5,
    cluster_id: 3,
    attribute_name: 'fd.name',
    attribute_value: '1.1.1.1:53',
    event_type: 'connect',
    process_name: 'curl',
    alert_content: 'network attribute not matched 1.1.1.1:53 curl connect',
    details: '{"evt.type": "connect"}',
    analysis: '',
  },
];

const SEED_OVERVIEW = {
  total_events_rate: 12.5,
  priority_distribution: [{ priority: 'Warning', value: 4 }],
  category_distribution: [{ category: 'process', value: 6.5 }],
  active_containers_count: 2,
  funnel_stats: { logs: 3, alerts: 2, incidents: 1 },
};

function withProviders(element, entry = '/') {
  return React.createElement(
    QueryClientProvider,
    { client: queryClient },
    React.createElement(
      MemoryRouter,
      { initialEntries: [entry] },
      React.createElement(Routes, null, React.createElement(Route, { path: '*', element: element }))
    )
  );
}

const RESULTS = [];

function scenario(name, fn) {
  CALLS.length = 0;
  let html = null;
  let value = null;
  let error = null;
  try {
    const result = fn();
    // 字符串结果是 HTML；其余（如收集到的 props）单独放在 value 里
    if (typeof result === 'string') {
      html = result;
    } else {
      value = result === undefined ? null : result;
    }
  } catch (exc) {
    error = `${exc.constructor.name}: ${exc.message}`;
  }
  RESULTS.push({ case: name, html, value, error, calls: CALLS.slice() });
}

function build() {
  // Chart：纯展示组件，直接给 options
  const Chart = load('src/components/Chart.tsx').default;
  scenario('Chart.default_height', () =>
    renderToStaticMarkup(React.createElement(Chart, { options: { series: [] } })));
  scenario('Chart.custom_height', () =>
    renderToStaticMarkup(React.createElement(Chart, { options: { series: [{ type: 'line' }] }, height: 120 })));

  // AppLayout：含导航菜单与子路由出口
  const AppLayout = load('src/layout/AppLayout.tsx').default;
  scenario('AppLayout.menu', () => renderToStaticMarkup(withProviders(React.createElement(AppLayout), '/logs')));

  // 页面：各自给一个能命中 useParams 的路由
  const pages = [
    ['Overview', 'src/pages/Overview.tsx', '/'],
    ['Alerts', 'src/pages/Alerts.tsx', '/alerts'],
    ['Logs', 'src/pages/Logs.tsx', '/logs'],
    ['Incidents', 'src/pages/Incidents.tsx', '/incidents'],
    ['HbtVisualizer', 'src/pages/HbtVisualizer.tsx', '/hbt'],
    ['Settings', 'src/pages/Settings.tsx', '/settings'],
  ];

  for (const [name, file, entry] of pages) {
    const Component = load(file).default;
    scenario(`page.${name}`, () => renderToStaticMarkup(withProviders(React.createElement(Component), entry)));
  }

  // 有数据状态：进入数据分支（HbtVisualizer 的自动选中在 SSR 不执行，
  // 因此按它实际使用的 key ['hbt', null] 预置缓存）
  scenario('page.Incidents.with_data', () => {
    const Incidents = load('src/pages/Incidents.tsx').default;
    return renderWithData(React.createElement(Incidents), '/incidents', [
      [['containers'], SEED_CONTAINERS],
      [['incidents', undefined, 0], SEED_INCIDENTS],
    ]);
  });

  scenario('page.HbtVisualizer.with_data', () => {
    const HbtVisualizer = load('src/pages/HbtVisualizer.tsx').default;
    return renderWithData(React.createElement(HbtVisualizer), '/hbt', [
      [['containers'], SEED_CONTAINERS],
      [['hbt', null], SEED_HBT],
    ]);
  });

  // Chart 的 props：options 内容进不了 HTML，用桩组件收集后单独比对
  scenario('page.Alerts.with_data', () => {
    const Alerts = load('src/pages/Alerts.tsx').default;
    return renderWithData(React.createElement(Alerts), '/alerts', [
      [['containers'], SEED_CONTAINERS],
      [['alerts', 'all', 0], SEED_ALERTS],
    ]);
  });

  scenario('page.Overview.with_data', () => {
    const Overview = load('src/pages/Overview.tsx').default;
    return renderWithData(React.createElement(Overview), '/', [
      [['overview'], SEED_OVERVIEW],
      [['containers'], SEED_CONTAINERS],
    ]);
  });

  scenario('page.Overview.chart_options', () => {
    const spy = collectChartOptions('src/pages/Overview.tsx');
    try {
      const Overview = load('src/pages/Overview.tsx').default;
      renderWithData(React.createElement(Overview), '/', [
        [['overview'], SEED_OVERVIEW],
        [['containers'], SEED_CONTAINERS],
      ]);
      return { rendered: spy.recorded.length, options: spy.recorded.map((props) => serialize(props.options)) };
    } finally {
      spy.restore();
    }
  });

  scenario('page.HbtVisualizer.chart_options', () => {
    const spy = collectChartOptions('src/pages/HbtVisualizer.tsx');
    try {
      const HbtVisualizer = load('src/pages/HbtVisualizer.tsx').default;
      renderWithData(React.createElement(HbtVisualizer), '/hbt', [
        [['containers'], SEED_CONTAINERS],
        [['hbt', null], SEED_HBT],
      ]);
      return { rendered: spy.recorded.length, options: serialize(spy.recorded[0] ? spy.recorded[0].options : null) };
    } finally {
      spy.restore();
    }
  });
}

build();

const payload = JSON.stringify(RESULTS, null, 2);
if (process.argv[2]) {
  fs.writeFileSync(process.argv[2], payload + '\n', 'utf8');
} else {
  process.stdout.write(payload);
}
