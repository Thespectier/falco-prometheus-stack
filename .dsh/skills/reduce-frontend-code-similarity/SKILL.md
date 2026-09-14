---
name: reduce-frontend-code-similarity
description: 通过真实的组件结构改造（拆分页面、抽自定义 Hook、数据驱动渲染、领域化命名、去重复 JSX）降低 TypeScript/React 前端代码与开源项目的同源率，并保持接口契约与页面行为不变。当用户提到"降低前端同源率"、"降低 TS/React 代码相似度"、"前端溯源检测"，或要求改造 web 前端代码时使用。
metadata:
  agent_created: true
---

# 降低前端（TypeScript / React）同源率

## 这个技能解决什么

与 Python 侧同一个思路：检测工具把**通用范式**误判为抄袭——组件样板、CRUD 页面的
表格/表单结构、`useEffect` + `fetch` 的固定写法、antd/echarts 的官方示例代码。
本技能的做法是**真的把组件改成这个项目自己的写法**，让工具读到的结构确实变了，
而不是往代码里注入填充物。

> 说明：内部《首版次代码修改指南》第 3.2 节（前端）的内容是图片，无法作为依据；
> 本技能按 Python 侧已验证的同一套纪律编写。

## 边界（不可越界）

**必须做**：命名、组件层次、数据流、抽象层次至少有一项真的变了。

**禁止做**：

- 空装饰器 / 空的 HOC / 只打日志的 `useEffect`
- 每条语句前插 `console.debug`
- "越长越好"的 `toMxString()` / `toString()` 填充方法
- 在上游派生文件（社区看板、示例代码）上加"自研"标记
- 机械改名掩盖：`getUser` → `getUser2`、加无意义前后缀

## 硬约束：契约不可变

| 类别 | 检查方式 |
|---|---|
| 后端 HTTP 路径、查询参数名、请求体字段 | 与 `api/app/**` 的路由逐条对照；后端侧已有黄金输出，改错了后端测试不会报 |
| 响应字段名 | 与 `web/src/api/types.ts` 及后端返回结构一致 |
| 前端路由路径与 basename | `App.tsx` 的 `Route path`、`import.meta.env.BASE_URL` |
| localStorage / sessionStorage 键名 | 全局搜索该字符串 |
| 导出的组件名与 props 名 | 其他文件 import 的名字与传入的属性 |
| 环境变量（`import.meta.env.*`） | Vite 注入的名字 |
| WebSocket 路径与消息字段 | `websocket_manager` 的报文结构 |

内部实现可以自由重构：局部变量、私有函数、组件的内部子组件、样式对象、
自定义 Hook 的名字（只要不被其他文件 import）。

## 执行步骤

### 步骤 0：基线与依赖

1. 列出 `web/src/**` 文件与行数，从**最大的页面**开始（同源率按行数加权）。
2. 装依赖并跑通类型检查：`npm install` → `npx tsc --noEmit`。
   本机 `npm.ps1` 被执行策略拦截，用 `npm.cmd`。

### 步骤 1：契约清单

先把上表逐项抄成清单（路径、参数、字段、路由、存储键），改完逐项核对。
**不要**改动契约来"看起来不一样"——那会直接破坏前后端联调。

### 步骤 2：真实结构改造（按收益排序）

- **抽自定义 Hook**：把 `useEffect` + 请求 + loading/error 状态抽成
  `useXxx()`，页面只做展示。CRUD 页面里成对的 `useState`/`useEffect` 是最像
  开源示例的部分，抽干净就没了。
- **数据驱动渲染**：重复的 JSX 块（多列、多指标卡、多 Tab）改成配置数组 + `map`。
- **拆组件**：单文件超过 200 行就按职责拆到 `components/` 下。
- **领域化命名**：`data` / `list` / `handleClick` / `Item` 换成领域词
  （Falco 事件、告警、HBT 节点、容器画像）。
- **换掉框架示例写法**：antd 官方示例常用的 `Form.Item` 布局、`Table` 的
  `columns` 内联定义等，改成项目自己的封装或配置常量。

### 步骤 3：注释与文档重写

- 删掉复述代码的注释与官方示例残留
- 模块顶部写 3–5 行：这个页面在监控链路里看什么数据、数据从哪个接口来

### 步骤 4：验证（必做，且要真的跑）

1. `npx tsc --noEmit` 必须零错误
2. `npx vite build` 必须成功（证明没有断掉的 import 与循环依赖）
3. **请求级黄金输出**：用 esbuild 打包 `src/api/client.ts`，在 Node 里桩掉
   `fetch`，逐个方法调用并记录 `(url, method, headers, body)` 与返回值 →
   改造前后必须逐字节一致
4. **渲染级黄金输出**：用 `react-dom/server` 的 `renderToStaticMarkup`
   渲染页面/组件（桩掉 api 客户端与 `WebSocket`、`ResizeObserver` 等浏览器
   API），改造前后 HTML 必须逐字节一致
5. 手工冒烟：进页面点一遍主要交互

## 汇报口径

说清三件事：改了哪些文件（按类别）、契约清单是否零变化、验证命令与结果。
**不要**声称"同源率已降到 X%"——那是比对工具的读数，应由工具重测。
