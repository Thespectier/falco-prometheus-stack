/**
 * 前端路由契约检查。
 *
 * `App.tsx` 的路由表与 `layout/AppLayout.tsx` 的导航项必须一一对应：少了路由会在点击时
 * 落到兜底路由，多了路由则说明导航漏了一项。两处都必须与后端的页面无关，只关乎前端。
 *
 * 运行：node .dsh/verify/web_route_contract.cjs
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const APP = path.join(ROOT, 'web', 'src', 'App.tsx');
const LAYOUT = path.join(ROOT, 'web', 'src', 'layout', 'AppLayout.tsx');

/** 归一化：统一成以 / 开头、不带结尾斜杠的形式 */
function normalize(route) {
  const trimmed = route.replace(/^\/+/, '').replace(/\/+$/, '');
  return `/${trimmed}`;
}

function collect(source, pattern) {
  return [...source.matchAll(pattern)].map((match) => match[1]);
}

const appSource = fs.readFileSync(APP, 'utf8');
const layoutSource = fs.readFileSync(LAYOUT, 'utf8');

// 路由表里的 path: '...'（排除兜底路由 '*'）
const appRoutes = collect(appSource, /path:\s*'([^']*)'/g).filter((route) => route !== '*');
// 导航项的 key: '...'
const navRoutes = collect(layoutSource, /key:\s*'([^']*)'/g);

const normalizedApp = appRoutes.map(normalize).sort();
const normalizedNav = navRoutes.map(normalize).sort();

const onlyInApp = normalizedApp.filter((route) => !normalizedNav.includes(route));
const onlyInNav = normalizedNav.filter((route) => !normalizedApp.includes(route));

console.log('App 路由      :', JSON.stringify(normalizedApp));
console.log('导航项        :', JSON.stringify(normalizedNav));
console.log('仅路由表有    :', JSON.stringify(onlyInApp));
console.log('仅导航有      :', JSON.stringify(onlyInNav));
console.log('契约一致      :', onlyInApp.length === 0 && onlyInNav.length === 0 ? 'YES' : 'NO');

process.exit(onlyInApp.length === 0 && onlyInNav.length === 0 ? 0 : 1);
