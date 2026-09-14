# 降低同源率 · 改造进度

方法：`.dsh/skills/reduce-code-similarity-by-refactor/SKILL.md`
来源核查：`.dsh/skills/code-provenance-audit/SKILL.md`

## 验证脚本

| 脚本 | 覆盖范围 | 现状 |
|---|---|---|
| `.dsh/verify/hbt_golden.py` | hanabi 模型层（19 场景，真实导入） | 通过 |
| `.dsh/verify/api_golden.py` | api/app 路由与入口（40 场景，fastapi/pydantic/服务层桩件） | 通过 |
| `.dsh/verify/log_storage_golden.py` | log_storage（68 场景，psycopg2/httpx 桩件 + 固定时钟） | 通过（2 个已记录差异） |
| `.dsh/verify/line_overlap.py` | 改动量测量（HEAD 版本 vs 工作区） | 工具 |

## 硬约束

- 公开契约逐字不变：HTTP 路径、请求/响应 JSON 字段、环境变量名、Prometheus 指标名与
  PromQL、数据库表/列名与 SQL 语义、compose 与镜像引用、跨模块导入的类与函数名、
  路由处理函数名（进入 OpenAPI operationId）
- 行为等价由黄金输出比对，不靠人工目测；**有意变更必须逐条记录**
- 禁止：空注解/空装饰器、逐语句日志、"越长越好"的填充方法、给上游派生文件打自研标记

## 第 1 轮：hanabi 模型层

| 原文件 | 处理方式 | 原样保留 |
|---|---|---|
| `hanabi/utils/parser.py` | 7 条顺序替换语句 → 规则表 + 单一循环 | 10.5% |
| `hanabi/utils/timeCount.py` | 窗口判定改写为整型比较、常量抽取 | 37.5% |
| `hanabi/models/tree_node.py` | `__slots__`、守卫式 add_child、to_dict 重排 | 40.4% |
| `hanabi/models/event_parser.py` | if/elif 分类链 → 别名表分派 | 33.3% |
| `hanabi/models/hbt_builder.py` | 分支布局声明表 + 处理器分派表 | 27.0% |
| `hanabi/models/hbt.py` | 三个 `add_*` 归并到 `_feed` | 50.0% |
| `hanabi/models/branch_handlers.py`（310 行） | 拆成包：`base` + process / network / file | 17.6% |

合计 374 有效行中 99 行（26.5%）原样保留。保留项均为契约（序列化键名、告警文案、
跨模块签名）与不可再分的单行语句。

## 第 2 轮：API 层

| 文件 | 处理方式 | 原样保留 |
|---|---|---|
| `api/app/main.py` | 18 行重复 `include_router` → 一张挂载表循环挂两遍前缀 | 67.1% |
| `api/app/routers/overview.py` | 查询表；四段结果处理的异常语义逐条保留 | 28.8% |
| `api/app/routers/containers.py` | 守卫式遍历 + 抽出"已知容器"判定 | 45.2% |
| `api/app/routers/config.py` | 掩码/默认值/存储键常量化 | 60.9% |
| `api/app/routers/hbt.py` | 卫语句 + 错误翻译分离 | 47.4% |
| 其余 5 个路由 + `core/config.py` | 调用与响应结构保留，注释文档重写 | 75–100% |

合计 294 有效行中 180 行（61.2%）原样保留。**原因已核实**：12–22 行的小路由全文就是
"装饰器 + 签名 + 一次服务调用 + 响应字面量"，签名里的查询参数与响应键都是对外契约。
框架样板的同源率来自 FastAPI 通用写法，改函数体消不掉；要再降只能合并模块（待用户确认）。

## 第 3 轮：log_storage（全仓最大文件）

原 623 行单文件 → 10 个模块的包（687 行）：

| 模块 | 行数 | 职责 |
|---|---|---|
| `base.py` | 126 | 日志器、连接池、建表、读写游标上下文管理器 |
| `values.py` | 102 | 取值归一化 + 行 → 接口结构 |
| `events.py` | 66 | events 写入与查询 |
| `alerts.py` | 123 | alerts 写入、查询、统计 |
| `incidents.py` | 103 | incidents 写入与查询 |
| `funnel.py` | 68 | 漏斗统计 |
| `maintenance.py` | 32 | 过期清理与维护 |
| `config_kv.py` | 28 | 键值配置 |
| `store.py` | 22 | 组合类 + 单例 |
| `__init__.py` | 17 | 对外导出（导入路径不变） |

合计 340 有效行中 153 行（45.0%）原样保留，其中 **58 行是 SQL/DDL 片段**（表名列名与
建表语句属数据库契约），其余是方法签名与参数注解。核心的结构收益是：原来 15 处重复的
"getconn → cursor → execute → commit → close → putconn → 异常里按 `'conn' in locals()`
判断" 样板收敛成两个上下文管理器。

### 有意的行为变更（**唯一一处**，已在验证中逐条记录）

`get_config` / `set_config` 在 `pool.getconn()` 失败时，原实现在 except 块里直接引用
未绑定的局部变量 `conn`，抛 `UnboundLocalError`（其余方法因写了 `'conn' in locals()`
守卫而没有这个问题）。重构后按类内既有语义处理：记日志、返回 `None` / 静默返回。

影响：数据库不可用时，`GET /api/config/llm` 由 500 变为正常返回默认配置。这是行为改进，
但确实改变了错误路径，故单独列出。黄金输出 68 个场景中仅这 2 个不同，其余 66 个
（含建表 DDL、每条 SQL 与参数、连接池生命周期、日志记录、返回值）**逐字节一致**。

### 顺带发现的既有缺陷（**未修**）

1. **毫秒时间戳被折算成 1e9 分之一**：`values.epoch_seconds` 沿用原口径
   `小于 1e11 视为秒，否则除以 1e9`。黄金测试实测：`evt.time=1700000000000`（毫秒）
   入库为 `1700.0` 秒（1970-01-01），而纳秒 `1700000000000000000` 才是正确的
   `1700000000.0`。后果：这类事件的时间戳落在保留期之外，会被清理任务立刻删掉，
   在接口上也永远查不到。修它会改变已入库数据的口径，故未动。
2. `overview.py` 的 `by_priority` / `by_category` 循环 `except` 不含 `IndexError`，
   Prometheus 采样值缺列时异常会冒到调用方（第 2 轮记录）。

两条都建议作为独立修复提交，需先确认。

## 第 4 轮：服务层与摄取端（5 个模块）

| 文件 | 处理方式 | 原样保留 |
|---|---|---|
| `api/app/services/websocket_manager.py` | 报文拼装抽出 `_frontend_message` + `_message_timestamp`；分组广播改为循环 | 33.8% |
| `analyzer/service.py` | 配置读取表驱动；提示词移出函数为模板；轮询体抽出 `_analyze_pending_incidents` | 55.2% |
| `api/app/services/prometheus.py` | 路径常量化、文档重写（薄封装，契约消息多） | 71.8% |
| `ingestors/logs/main.py` | 搬运抽成 `_drain_queue`、刷写条件显式化 | 76.6% |
| `ingestors/alerts/main.py` | 缓冲类结构保留、注释补全（属性名被测试与调用方依赖） | 86.3% |

合计 278 有效行中 170 行（61.2%）原样保留。**原因与第 2 轮相同**：这批文件短且契约密集——
缓冲类的属性名（`buffer` / `lock` / `running` / `batch_size`）、日志文案、HTTP 报文与
Prometheus 指标名占了大部分行数，改了就破坏调用方或运维检索。有真实逻辑的部分
（WebSocket 报文拼装、提示词构造、轮询体）保留率明显更低。

### 验证证据（第 4 轮）

1. 新建 `.dsh/verify/services_golden.py`，62 个场景，桩掉 fastapi / rich /
   prometheus_client / openai / httpx / 队列 / log_storage，固定时钟与 `datetime.utcnow`
2. 基线在**原始代码**上取得（`git stash push -- <5 个文件>` 还原后运行，再 `stash pop`），
   改造后输出与基线 **sha256 完全相同**（`27c147c18ab31e3c…`，38293 字节）
3. 过程中发现并修掉两处**测试脚本自身**的不确定性（后台线程的 sleep 记录被计入、
   `datetime.utcnow()` 未固定导致时间戳随运行时刻变化）——这两处修好后差异归零，
   说明差异确属测量噪声而非代码行为
4. 全量回归：hanabi IDENTICAL、api IDENTICAL、log_storage 仅第 3 轮记录的 2 处有意差异

## 战略发现：同源率的最大来源不是 Python

| 文件 | 行数 | 性质 |
|---|---|---|
| **`falco/falco.yaml`** | **1149** | **上游 Falco 默认配置原文**（含 upstream 注释与 GitHub 链接），同源率接近 100% |
| `falco/custom_rules.yaml` | 83 | 自研规则（待核查是否基于上游示例） |
| `grafana/dashboard.json` | 39 | Falco 主题看板 |
| `prometheus/prometheus.yml` | 4 | 极简，无虞 |

1149 行约等于**前四轮改造的 Python 代码总量**（约 2100 行）的一半，且同源率接近 100%——
它对整仓同源率的贡献很可能大于已改造的全部 Python 文件之和。

本机 `docker.exe` 可用、`falco` 二进制未安装，因此校验路径是：

```bash
docker run --rm -v "$PWD/falco/falco.yaml:/etc/falco/falco.yaml:ro" \
  falcosecurity/falco:latest falco --validate /etc/falco/falco.yaml
```

## 第 5 轮：falco.yaml 最小化（同源率最大来源）

状态：**完成并通过镜像级校验**

| 项 | 改造前 | 改造后 |
|---|---|---|
| `falco/falco.yaml` | 1149 行（上游默认配置原文） | **81 行**（只保留本项目依赖的键） |
| schema 校验 | `failed for <root>[engine]` | **ok** |
| 生效配置键值 | 135 项 | 保留的键**值零变化** |

### 判定方法（全部实测，无一处凭感觉）

1. 从镜像里取出上游默认配置（版本严格对齐：`falcosecurity/falco:latest` = 0.44.1）
2. 用 `falco --support` 导出**合并后的生效配置 JSON**，与镜像默认值逐键对比 → 项目真实覆盖
   只有 3 项：`json_output: true`、`json_include_output_property: false`、`rules_files`
   去掉上游规则集；其余 9 处"差异"只是把新版已省略的默认值又写了一遍
3. 用空配置与探针配置实测**哪些键没有内置默认值**：`config_files`（不写则 config.d 片段
   不加载，容器插件随之消失）、`rules_files`、至少一个输出（`stdout_output`）
4. 逐项 A/B：`falco --dry-run` 对比改造前后输出，归一化时间戳后**唯一差异**是 schema 校验
   由 failed 变 ok；再用 `--support` 对比，保留键的值差异为 **0**
5. 端到端：用项目自己的 `Dockerfile.falco` 构建镜像并在镜像内跑 `--dry-run` → exit 0、
   `falco_rules.local.yaml | schema validation: ok`（验证后已删除该镜像）

### 保留原则（写在配置文件头部）

1. 不写就起不来的键：规则文件、容器插件、至少一个输出
2. 不写就会改变可观察行为的键：规则优先级（自研规则是 DEBUG 级，需要 `priority: debug`）、
   JSON 输出格式、采集与输出管线调优（modern_ebpf 参数、事件丢弃阈值、线程表容量、不缓冲输出）
3. 官方默认即"关闭"的功能一律不写（已实测：不配置任何输出时 Falco 直接报
   "No output configured"，证明所有输出默认关闭）

删除的 54 个键全部属于三类：默认关闭的输出与捕获功能、非激活引擎（kmod/ebpf/gvisor/replay）
子项、仅在功能启用后才有意义的细项（metrics 计数器、grpc、webserver 证书）。
未在任何派生文件上添加"自研"标记；出处与裁剪原则同时写入文件头与 `THIRD_PARTY_NOTICES.md`。

### 验证产物

- `THIRD_PARTY_NOTICES.md`（新增）
- `.dsh/verify/falco_config_diff.py`（生效配置逐键 diff 工具）
- `.dsh/verify/support-*.txt`、`dryrun-*.txt`、`falco.original.yaml`（对照留档）

## 第 6 轮：exporter、回放脚本与 hanabi 运行时

| 文件 | 处理方式 | 原样保留 |
|---|---|---|
| `prometheus/exporter.py` | 分类判定改两张映射表；标签整理与时间戳解析抽成函数 | 58.7% |
| `main.py`（根目录回放脚本） | 分类分派表驱动；`print_tree` 两个分支合并；退出报表抽成函数 | 59.5% |
| `hanabi/utils/queue.py` | 连接与单行处理抽成 `_connect` / `_ingest_line` | 71.9% |
| `hanabi/worker.py` | 快照写入抽成 `_write_snapshot`；分派表驱动；启动延时/读超时常量化 | 81.3% |

合计 368 有效行中 249 行（67.7%）原样保留。**这批保留率高是结构性的**：四个文件都是
"薄编排层"——大量行数是日志/控制台文案（运维检索与排障依赖）、公开属性名
（`models` / `running` / `last_save_time` / `queue` / `stop_event`）、以及 `size()` /
`is_empty()` 这类一行转发。真正有逻辑的部分（分片拼行、原子落盘、事件分派、指标标签
整理）已经重写。

> **可选的进一步空间**：如果允许改动日志与控制台文案（属于运维接口，需你确认），
> 这四个文件还能再降一大截——目前那段文案是按"不改运维接口"的原则逐字保留的。

### 验证证据（第 6 轮）

1. `exporter.py` 与根目录 `main.py` 由第 4 轮的 `services_golden.py`（62 场景）覆盖，
   改造后与基线 **sha256 完全相同**
2. 新建 `.dsh/verify/hanabi_runtime_golden.py`（14 场景）：桩掉 docker SDK，覆盖日志分片
   拼行/坏 JSON/坏编码/停止事件/流中断、`start()` 的三条失败分支、队列全部读写接口、
   worker 的建模/分派/快照原子落盘/保存间隔/停止流程/信号处理
3. 基线用 `git stash push -- <文件>` 在**原始代码**上取得；改造后与基线 **sha256 完全相同**
   （过程中又发现一处测试脚本自身的不确定性：`datetime.now()` 未固定导致日志流的 `since`
   参数随运行时刻漂移，修掉后差异归零）
4. 全量回归：hanabi / api / services / runtime 均 IDENTICAL，log_storage 仅第 3 轮记录的
   2 处有意差异；全仓 Python 编译通过

## 第 7 轮：告警消减（hanabi/reducer.py → 9 个模块的包）

原 501 行单文件 → `hanabi/reducer/` 包（594 行）：

| 模块 | 行数 | 职责 |
|---|---|---|
| `pipeline.py` | 234 | `AlertReducer` 主流程与状态 |
| `report.py` | 92 | 消减报告与性能统计 |
| `cli.py` | 87 | 命令行入口 |
| `features.py` | 70 | 字段校验、文本拼接、TF-IDF 与备用特征 |
| `clustering.py` | 46 | 相似度合并、簇代表选择 |
| `scoring.py` | 39 | 威胁评分（规则 / 兜底采样） |
| `__init__.py` / `__main__.py` / `_logging.py` | 26 | 对外导出、`-m` 入口、共用日志器 |

### 保留率 79.1% 的构成（如实拆解）

345 个有效行中 273 行原样保留，但**几乎没有算法内容**：

| 类别 | 行数 | 占比 |
|---|---|---|
| 结构契约字面量（报告 schema 键、列名、参数名、耗时统计键表） | 193 | 71% |
| 日志 / 控制台 / 报告文案 | 52 | 19% |
| 短句与结构行（`]`、`return True` 等） | 28 | 10% |

也就是说，保留下来的是**数据契约与运维文案**（改了就直接破坏 `reducer/service.py`
的字段映射、报告结构与既有排障口径），算法与流程已经搬进子模块并重写。
若要继续下降，唯一的大块仍是那些文案——属运维接口，待确认。

### 行为契约处理

- 日志器名字固定为 `hanabi.reducer`（原来是 `logging.getLogger(__name__)`）：拆包后
  各子模块共用同一名字，日志来源与过滤规则不变
- 命令行入口由 `python hanabi/reducer.py` 改为 `python -m hanabi.reducer`（新增
  `__main__.py`）。已确认仓库内没有任何地方按脚本路径调用它（`Dockerfile.reducer` 跑的是
  `reducer/service.py`），`reducer/service.py` 的 `from hanabi.reducer import AlertReducer`
  保持不变

### 验证证据（第 7 轮）

1. 新建 `.dsh/verify/reducer_golden.py`（26 场景），用**真实依赖**驱动：在隔离环境
   `.dsh/verify/venv`（pandas 3.0.5 / numpy 2.5.3 / scikit-learn 1.9.1）里安装项目所需
   依赖后运行；固定时钟、桩掉 tqdm（保留 `progress_apply` 背后的计算）
2. 覆盖：预处理（含缺字段报错）、TF-IDF 嵌入与备用嵌入、相似度聚类（三个阈值）、
   簇代表选择、威胁评分四档频次与关键词分支、兜底评分、完整消减（聚类 / 非聚类 /
   过滤后为空）、报告（零耗时与计时两种）、性能统计、CSV 与报告落盘、CSV 载入、
   命令行四个分支
3. 改造后与基线 **sha256 完全相同**（`c2250d9602fd9c2e…`，82854 字节）
4. 全量回归：hanabi / api / services / runtime 均 IDENTICAL，log_storage 仅第 3 轮记录的
   2 处有意差异；`reducer/service.py` 的导入在带依赖环境中验证可用

## 第 8 轮：归约服务（reducer/service.py，Python 侧收尾）

| 项 | 处理 |
|---|---|
| 结构 | 保持单文件与脚本入口不变（`Dockerfile.reducer` 用 `python reducer/service.py` 调用），内部抽出 6 个函数 |
| 抽出 | `_derive_alerts_cleanup_interval`（清理间隔夹取逻辑）、`_behavior_counts`（频次统计）、`_alert_to_row`（告警 → 列映射）、`_incident_from_row`（消减结果 → 落库字典）、`_discover_containers`、`_cleanup_alerts_if_due` |
| 清理 | 删掉暂停功能遗留的 `last_cleanup_ts` / `last_vacuum_ts` 两个死状态变量，改用注释说明恢复方式 |
| 原样保留 | 63.0%（154 有效行中 97 行）——同样是环境变量常量名、日志文案、DataFrame 列名与落库字段字面量 |

### 验证证据（第 8 轮）

1. 新建 `.dsh/verify/reducer_service_golden.py`（13 场景）：常量派生（默认与自定义环境变量两组）、
   容器发现三条分支、告警 → DataFrame 映射（含频次统计与属性值回退）、单容器消减（空/非空）、
   一轮完整周期、主循环首次清理与"清理已跳过"两种情形
2. 改造后与基线 **sha256 完全相同**（`992a674d140d1efc…`，20132 字节）
3. 全量回归：7 套骨架全部通过——hanabi / api / services / runtime / reducer / reducer_service
   均 IDENTICAL，log_storage 仅第 3 轮记录的 2 处有意差异

### 顺带确认的既有不一致（**未改**）

线上路径的"告警内容"（`_alerts_to_dataframe`）**不带权重**，而 CSV 载入路径
（`hanabi.reducer` 的预处理）会给属性名/属性值 ×5、进程名 ×10。同一批告警经两条路径
进入聚类会得到不同的相似度矩阵。已把这一点写进代码注释，是否统一需要单独评估。

## Python 侧完成度

除 `prometheus/test_exporter.py`（23 行测试文件）外，仓库内所有 Python 文件均已改造并
通过黄金输出验证。剩余范围：

- **前端 `web/src/**`**（TypeScript，13 个文件约 1360 行）——需要另立前端 skill
- 配置与来源类事项（见下）

## 第 9 轮：前端开工（skill + 环境 + API 层）

### 新增前端 skill

`.dsh/skills/reduce-frontend-code-similarity/SKILL.md`（已热加载进会话目录）。内容按
Python 侧同一套纪律编写：契约清单（HTTP 路径与参数、响应字段、前端路由、存储键、
导出组件名、`import.meta.env.*`、WebSocket 报文）、真实结构改造手段（抽自定义 Hook、
数据驱动渲染、拆组件、领域化命名、换掉框架示例写法）、以及验证要求
（`tsc --noEmit` + `vite build` + 请求级与渲染级黄金输出）。

> 说明：内部指南第 3.2 节（前端）的内容是图片，无法读取，因此这份 skill 的依据是
> 前八轮验证出来的同一套纪律，而不是指南原文。

### 环境

- `node` v26.7.0；`npm.ps1` 被执行策略拦截 → 改用 `npm.cmd`
- `web/node_modules` 已安装（153 个包，约 200MB，已被 .gitignore 忽略）
- npm 的 allowScripts 策略拦下了 esbuild 的 postinstall；本轮的验证不需要它
  （用项目自带的 tsc），因此未调整该策略

### 本轮改造

| 文件 | 处理 | 原样保留 |
|---|---|---|
| `web/src/api/client.ts` | 查询串拼接改成参数表 + `buildQuery`；`request` / `get` 分离，POST 复用同一套错误处理 | 74.5% |
| `web/src/api/types.ts` | 按域分组、逐接口补文档 | 98.2% |

`types.ts` 的保留率几乎 100% 是**结构必然**：整个文件就是接口契约（字段名 + 可选性），
改了就直接与后端 JSON 对不上，属于不可动内容。可用空间在页面组件（见下）。

### 验证证据（第 9 轮）

1. **改造前**先跑项目级 `tsc --noEmit`，零错误（作为类型基线）
2. 新建 `.dsh/verify/web_api_golden.cjs`（16 场景）：用 tsc 把 `client.ts` 编译成 ESM，
   把 `import.meta.env` 换成可控全局对象后求值，桩掉 `fetch`，逐个方法记录
   `(url, method, headers, body)` 与返回值/异常
3. 覆盖：8 个方法的默认参数与显式参数、带空格的容器名（确认**不做 URL 编码**这一行为被
   保留）、`container_id` 为空串的丢弃逻辑、`BASE_URL` 为 `/` 与 `/infrasecurity/` 两种
   前缀、GET/POST 的错误分支
4. 改造后与基线 **逐字节一致**；`tsc --noEmit` 仍为零错误

## 第 10 轮：前端渲染级验证 + 前三个组件

### 渲染级黄金输出骨架

`.dsh/verify/web_render_golden.cjs`（9 场景，覆盖 `Chart`、`AppLayout` 与 6 个页面）：

- 用项目自带 tsc 把 TSX 编译成 CommonJS（`--noCheck`，类型闸门交给项目级
  `tsc --noEmit`），产物落在 `web/.verify-build/`（每次重建）
- 产物目录单独放 `package.json`（`{"type":"commonjs"}`）——`web/package.json` 是
  `"type": "module"`，否则产物会被当成 ESM
- 把产物里的 `import.meta.env` 换成可控全局对象
- 桩掉浏览器 API（`fetch` / `WebSocket` / `ResizeObserver` / `matchMedia` /
  `localStorage`），用 `renderToStaticMarkup` + `QueryClientProvider` + `MemoryRouter` 渲染
- **可复现性已自检**：同一份代码连跑两次结果完全一致（antd 的类名哈希是确定的）
- 不覆盖 `App.tsx`：它用 `BrowserRouter`，SSR 需要完整 `window.history`；改由
  `tsc --noEmit` + 路由表人工核对保证

### 本轮改造

| 文件 | 处理 | 原样保留 |
|---|---|---|
| `layout/AppLayout.tsx` | 导航项与品牌区样式提为模块级常量（导航 key 即路由契约） | 67.5% |
| `pages/Settings.tsx` | 抽出 `useLLMConfigForm` Hook；三个表单项改成字段表 + `map` 渲染 | 68.9% |
| `components/Chart.tsx` | 抽出 `useECharts` Hook（实例生命周期与 ResizeObserver） | 60.0% |

合计 179 有效行中 120 行（67.0%）原样保留：这批文件的行数大头是 antd 的属性、
界面文案与内联样式对象——都是渲染结果的直接来源，改了 HTML 就变。

### 验证证据（第 10 轮）

1. `tsc --noEmit`（项目级）改造前后均零错误
2. 渲染级黄金输出改造后与基线 **逐字节一致**（9 个场景全部一致，含 `AppLayout` 8.9KB、
   `Settings` 8.1KB 的完整 HTML）
3. 骨架自身可复现性已验证（连跑两次一致）

## 第 11 轮：两个前端页面

| 文件 | 处理 | 原样保留 |
|---|---|---|
| `pages/HbtVisualizer.tsx` | `normalizeChildren` 提为模块级纯函数；容器选择器拆成 `ContainerPicker` | 92.7% |
| `pages/Incidents.tsx` | 表格列抽出 `buildColumns(callback)`；筛选条拆 `IncidentFilters`；详情抽屉拆 `IncidentDrawer` | 80.3% |

合计 265 有效行中 228 行（86.0%）原样保留。验证：`tsc --noEmit` 零错误 +
渲染级黄金输出 9 个场景逐字节一致。

### 发现一个验证盲区（下轮先补）

`HbtVisualizer` 保留率高达 92.7%，主因是 **echarts 的 option 配置块（约 65 行）被逐字保留**：
`Chart` 组件在服务端渲染时只输出一个空 `<div>`，option 内容（含 tooltip/label 的
formatter 函数）**不在黄金输出里**，所以我没有动它。

补法（下轮先做）：在骨架里把 `components/Chart` 注入到 `require.cache`，换成一个记录
`options` 属性的桩组件，并把 formatter 函数用样本参数调用一次纳入比对。这样 option
配置也进了黄金输出，之后才能安全地重写它。
基线仍需用 `git stash push -- <文件>` 在改造前的代码上取得。

## 第 12 轮：补上 Chart 的 props 级验证，并重写 echarts 配置

### 骨架升级（9 → 12 场景）

1. **有数据状态场景**：用 react-query 的 `setQueryData` 预置缓存再渲染，让页面进入数据分支
   （否则 SSR 只渲染 loading 空态）。新增 `page.Incidents.with_data`（9.2KB HTML）与
   `page.HbtVisualizer.with_data`
2. **Chart props 级收集**：把 `components/Chart` 注入 `require.cache` 换成桩组件，记录
   `options` 属性；序列化时**用样本参数调用每个 formatter 并记录结果**，所以 tooltip 与
   label 的模板也进了黄金输出 → 新增 `page.HbtVisualizer.chart_options`
3. 过程中修掉两个骨架自身的缺陷：
   - 桩模块缺少 `__esModule: true`，tsc 的 `esModuleInterop` 会把它再包一层 default，
     导致 React 收到非组件对象而报 "Element type is invalid"
   - 场景运行器只保存字符串返回值（HTML），对象返回值被丢弃 → 现在分别存 `html` 与 `value`

### 本轮改造

`pages/HbtVisualizer.tsx`：把 echarts 配置里的三处内联定义提为模块级具名常量——
`tooltipFormatter`、`labelFormatter`、`LABEL_RICH`、`LEAF_LABEL`（原样保留 88.6%）。

- tooltip 模板里的缩进**逐字保留**：它原样进 tooltip HTML，重新排版就会改变展示
- 类型坑：内联时字面量由 echarts 类型上下文推断，提到模块级后会退化为 `string`
  导致类型错误 → `LEAF_LABEL` 的三个字段加 `as const`（取值不变，行为仍逐字节一致）

### 验证证据（第 12 轮）

1. `tsc --noEmit` 零错误（期间因上述类型坑失败过一次，修掉后通过）
2. 渲染级 + Chart props 级黄金输出 12 个场景**逐字节一致**——包括 echarts 的
   `tooltip.formatter` / `label.formatter` / `rich` / `leaves.label` / `initialTreeDepth`
   与 `normalizeChildren` 之后的树数据

## 第 13 轮：Overview 页面（含两张图表的配置）

骨架再加 2 个场景（14 个）：`page.Overview.with_data`（9.1KB HTML）与
`page.Overview.chart_options`（一次渲染收集到 2 张图的 option，含 formatter 样本）。

| 文件 | 处理 | 原样保留 |
|---|---|---|
| `pages/Overview.tsx` | 三张指标卡改成 `buildMetricCards` 数据驱动 + `map` 渲染；两张图的配置抽成 `buildFunnelChartOption` / `buildCategoryChartOption`，formatter 提为具名函数；表格列提为模块级常量 | 79.2% |

保留的 103 行里，大头是两张图的**布局键与数据项**（`left/top/bottom/width/min/max/...`、
漏斗三段的名称与配色、表格列定义）——它们是渲染结果的直接来源。为了让这些也被验证覆盖，
本轮先是补了 Chart props 级骨架，之后才动它们。

验证：`tsc --noEmit` 零错误；渲染级 + Chart props 级 **14 个场景逐字节一致**。

## 第 14 轮：Alerts 页面

骨架再加 1 个场景（15 个）：`page.Alerts.with_data`（8.9KB HTML，queryKey 为
`['alerts','all',0]`）。

| 文件 | 处理 | 原样保留 |
|---|---|---|
| `pages/Alerts.tsx` | 十个表格列抽成 `buildColumns(callback)`；筛选条拆 `AlertFilters`；详情抽屉拆 `AlertDrawer`（与 `Incidents` 同构） | 79.7% |

故意没动的一处：筛选条里的 `📦` 占位（原 `ContainerOutlinedWrapper`，注释说是"避免图标
导入问题"）。换成 antd 图标会改变渲染结果，属于界面变更而不是重构，因此保留原样。

验证：`tsc --noEmit` 零错误；渲染级 + Chart props 级 **15 个场景逐字节一致**。

## 第 15 轮：Logs 页面 + App 路由表（前端收尾）

| 文件 | 处理 | 原样保留 |
|---|---|---|
| `pages/Logs.tsx` | 删掉约 35 行 WebSocket 地址推导的试错注释；推导逻辑提为纯函数 `buildLogStreamUrl(apiBase, protocol, host, containerId)`；列定义 / 工具栏 / 抽屉抽离 | 69.5% |
| `App.tsx` | 六条路由改成 `PAGES` 表 + `map` 渲染 | 81.2% |

- `Logs.tsx` 的 WebSocket 副作用**在服务端渲染时不执行**，因此地址推导、消息解析、
  缓冲截断这些逻辑不在黄金输出覆盖范围内。我的处理是：把它们**逐字搬进纯函数**
  （逻辑一行未改），并在注释里写清推导依据（`api.baseURL` 已含 `/api`，只补
  `/logs/ws/<id>`）。这部分需要浏览器手工冒烟，已记入待办。
- 新增 `.dsh/verify/web_route_contract.cjs`：核对 `App.tsx` 的路由表与 `AppLayout` 的
  导航项是否一一对应（改一处忘另一处会落到兜底路由）。当前结果 **契约一致 YES**。
  （脚本第一版自己的归一化写错了——导航 key 本就带 `/`，被我拼成 `//hbt`——修掉后才可信。）

验证：`tsc --noEmit` 零错误；渲染级 + Chart props 级 15 个场景逐字节一致；路由契约一致。

## 前端完成度

`web/src/**` 11 个文件、约 1400 行全部改造完成并通过 `tsc` + 渲染黄金输出验证，
唯一例外是 `main.tsx`（9 行）：内容只有 `createRoot(...).render(<App />)`，
不改变行为就没有可重构空间，保持原样。

## 第 16 轮：来源清单（审查材料）

代码改造已在第 15 轮收尾，本轮补上 `code-provenance-audit` skill 承诺过的产出：

- **新增 `.dsh/audit/provenance-inventory.md`**：逐文件判定来源（自研 / 上游派生 /
  第三方依赖 / 疑似逐字片段），写明每类的判定依据（文件内标记、git 历史、实体比对、
  公开检索），并记录检索与比对过程
- **`THIRD_PARTY_NOTICES.md` 更新**：把此前"待核查"的两项落定——
  `grafana/dashboard.json`（自建：用本项目自己的指标名，无社区看板导出物特征）与
  `falco/custom_rules.yaml`（自研：本项目自有容器名单与画像字段）
- **对 `hanabi/reducer` 做了公开检索**：以「告警消减 AlertReducer 威胁评分 相似度聚类」
  等关键词检索，**未发现与类名、方法名、报告结构匹配的上游实现**；命中的是思路相近
  但实现不同的项目。结论如实写入清单：未发现可指认的上游来源，该设计属告警降噪领域
  的常见组合；如审查方另有比对客体，可按 `reducer_golden.py` 的结构逐段复核

判定结果：**疑似逐字片段 0 处**；上游派生 1 处（`falco/falco.yaml`，已裁剪 + 声明）；
其余为自研或常规依赖。**唯一缺口是仓库没有 `LICENSE`**。

## 第 17 轮：独立开发过程说明（审查材料）

执行 `originality-evidence-pack` skill，从 git 历史生成
**`docs/independent-development-statement.md`**（89 行）：

- 项目概览与时间线：63 次提交、3 位作者、2025-10-31 → 2026-04-09（约 5 个半月）；
  按月提交量**照实列出**（含 2026-01 无提交），不做平滑
- **模块级首次提交时间线**：`hanabi/prometheus/falco` 在初始提交，
  `api/web` 2025-12-09、`ingestors` 2025-12-16、`reducer/analyzer` 2025-12-22 ——
  这是"随功能演进逐步建立、没有批量导入"的直接证据
- 代码量分布（约 4200 行，按目录）
- 与已知开源实现的差异说明（行为树建模、告警归约、指标方案、前端、falco 配置逐项）
- 第三方披露与验证边界、待决事项
- **如实记录本轮重写**：说明当前工作区含一次尚未提交的实现重写，建议的提交信息是
  `refactor: 重写实现以消除比对工具误判（行为由黄金输出验证）`，并明确
  **不应把它当作"原创开发"证据提交**
- 附可复现命令；代码量表的统计口径单独注明（PowerShell，与 `wc -l` 可能差 1 行以内），
  避免复核者按 bash 命令得到不同数字

## 第 18 轮：最后一个代码文件（test_exporter.py）

新建 `.dsh/verify/test_exporter_golden.py`：桩掉 docker，用 `runpy` **原样跑**该冒烟脚本并
比对 stdout（脚本唯一的产物就是它打印的那几行），归一化 prometheus_client 计数器自带的
`_created` 时间戳。改造后输出 **逐字节一致**（保留 81.0%——21 行里大半是样本事件字面量与
打印标题）。

**至此仓库内所有代码文件（Python 38 个 + 前端 11 个）都已改造并通过黄金输出验证。**

## 新识别出的剩余范围：构建与部署配置（约 300 行）

第 18 轮盘点时发现，除源码外还有一批尚未处理的配置文件，其中两类值得做：

| 文件 | 行数 | 说明 |
|---|---|---|
| `web/nginx.conf` | 58 | 标准 SPA 服务块（history 回退、静态缓存、API 反代），属比对工具容易命中的样板 |
| `Dockerfile.backend` / `.reducer` / `.analyzer` / `web/Dockerfile` | 115 | 多阶段构建样板 |
| `export_hanabi_images.sh` / `web/docker-entrypoint.sh` | 43 | 导出镜像、运行时注入配置的脚本 |
| `hanabi/models/example.json` | 83 | 示例数据（需先判定是样例还是从上游复制的） |

**验证路径**（本机 Docker 可用，比 Python 侧更好办）：
`docker run --rm -v web/nginx.conf:/etc/nginx/conf.d/default.conf:ro nginx:alpine nginx -t`
做配置语法校验；Dockerfile 用 `docker build` 验证仍能构建；脚本用 `bash -n` 做语法校验。

## 第 19 轮：前端 nginx 配置（构建与部署配置的第一批）

| 文件 | 处理 | 原样保留 |
|---|---|---|
| `web/nginx.conf` | 四处重复的转发头抽成片段 `nginx-proxy-headers.conf` + `include`；注释改写成路由方案说明 | 86.2% |
| `web/nginx-proxy-headers.conf` | 新增：公共转发头（4 条 `proxy_set_header`） | — |
| `web/Dockerfile` | 增加一行 COPY，把片段放到 `include` 指向的路径 | 100%（只新增了一行） |

### 验证方式（真实 nginx，不是语法猜测）

新建 `.dsh/verify/nginx_config_golden.py`：把配置挂进 `nginx:alpine`，用 `nginx -T` 转储
生效配置，去掉注释与空行后逐行比对。结果：

- `nginx -t` **exit 0**（include 被正确解析；若片段缺失会直接报 open() 失败）
- 指令差异**恰好只有预期的那一处**：16 行重复头 → 4 条 include + 片段内容 4 行
- 单独验证了 Dockerfile 新增的那行 COPY：`/etc/nginx/snippets` 在镜像里并不存在，
  用一次性镜像实测 `COPY` 能创建目录并落到目标路径（构建成功）

过程中发现一个对 CI 有用的细节：`nginx -t` 单独跑会因 `proxy_pass` 里的
`43039infrasecurity-api` 在容器外无法解析而报 `host not found`，需要
`--add-host 43039infrasecurity-api:127.0.0.1` 才能校验。已写进脚本注释。

### 关于收益的实话

这一轮的**指标收益很低**（nginx.conf 的指令本就不可动，去重只省下 12 行；Dockerfile 还多了
一行）。它的价值在于：消掉"四处重复块"这种结构指纹、把路由方案写清楚、并把 nginx 配置纳入
可校验范围。若只按同源率算账，剩下这批构建/部署配置（约 240 行）都属于低收益项。

## 第 20 轮：运行时入口脚本 + 一个行尾隐患

| 文件 | 处理 | 验证 |
|---|---|---|
| `web/docker-entrypoint.sh` | 假值判断抽成 `is_access_control_enabled()` 函数；注释写清"为什么启动时生成配置"；`case` 的取值列举与 heredoc 内容逐字保留 | 新建 `.dsh/verify/web_entrypoint_golden.py`，在 `alpine` 容器里真跑 12 个 `ACCESS_CONTROL_ENABLED` 取值（未设置 / `0` / `false` / `FALSE` / `False` / `no` / `NO` / `No` / `1` / `true` / `yes` / 未列举值），比对生成的 `runtime-config.js` 与 `exec` 是否生效 → **逐字节一致** |

### 顺带发现的隐患（未擅自修）：仓库里 4 个 shell 脚本在工作区是 CRLF 行尾

第一次在容器里跑入口脚本时报 `set: line 2: illegal option -`——原因是 Windows 工作区把
`web/docker-entrypoint.sh` 检出成了 CRLF，busybox 的 `sh` 把 `set -e\r` 解析成非法选项。
实测工作区行尾：

| 脚本 | CRLF 行数 |
|---|---|
| `web/docker-entrypoint.sh` | 19（全文 19 行） |
| `export_hanabi_images.sh` | 35（全文 35 行） |
| `falco/deploy.sh` | 9 |
| `prometheus/deploy.sh` | 3 |

仓库没有 `.gitattributes`，因此行尾取决于各人的 `core.autocrlf`。**在 Windows 上构建镜像
就会把 CRLF 打进镜像，入口脚本直接启动失败**（这不是推测，是上面那条报错的复现）。
建议加一份 `.gitattributes`：

```gitattributes
* text=auto eol=lf
*.sh text eol=lf
Dockerfile* text eol=lf
*.conf text eol=lf
```

我没有擅自加：它会在下次检出时重写工作区行尾，产生一大片空白差异，属于需要你确认口径的
仓库级改动。同理，验证脚本里现在会先把脚本规范成 LF 再挂载（与交付物口径一致）。

## 第 21 轮：补上来源清单的最后一处空白

- `hanabi/models/example.json`（83 行）：查清是**本项目自行抓取的样本数据**（3 条真实 Falco
  事件的 JSONL，时间戳 2025-11-02，含本环境特有的主机名、容器 ID 与第三方容器名）——
  上游示例不可能带上这些。已写入来源清单，此前"待判定"一项关闭。
- 三个后端 Dockerfile（115 行）确认**高度重复**：构建阶段几乎逐行相同，可抽公共基础镜像
  让三者继承。这属会改动构建方式的变更（需先构建基础镜像或调整 compose），登记为待确认项，
  本轮未动。

## 收尾状态（第 21 轮）

同源率相关的改造范围已覆盖完毕，结论如下。

**已完成并逐项验证**

| 范围 | 规模 | 验证 |
|---|---|---|
| Python 全部（api / hanabi / reducer / ingestors / analyzer / exporter / 根脚本） | 38 个文件 | 7 套黄金输出（reducer 用真实 pandas/sklearn 跑数值） |
| 前端 `web/src/**` | 11 个文件 | `tsc --noEmit` + 请求级 + 渲染级/Chart props 级（15 场景） |
| `falco/falco.yaml`（同源率最大来源） | 1149 → 81 行 | 镜像内 `--dry-run` + 生效配置逐键比对（保留键零变化） |
| `web/nginx.conf` | 67 行 | 真实 nginx `-T` 转储的指令级比对 |
| `web/docker-entrypoint.sh` | 19 行 | 容器内 12 个环境变量取值的输出比对 |
| `prometheus/test_exporter.py` | 27 行 | 输出比对 |

验证骨架 16 个脚本；审查材料 3 件（`docs/independent-development-statement.md`、
`.dsh/audit/provenance-inventory.md`、`THIRD_PARTY_NOTICES.md`）；skill 4 个。

**未做，且理由明确**

| 事项 | 为什么没做 |
|---|---|
| 改 Python 日志/控制台文案（保留率的最大块） | 属运维接口，改动会影响既有排障口径，需你确认 |
| 合并三个"按容器查询"的路由模块 | 架构调整，需你确认 |
| 修三处既有缺陷（IndexError / 毫秒时间戳 / 告警内容口径） | 都是行为变更，需你确认后作为独立修复提交 |
| 三个 Dockerfile 抽公共基础镜像 | 改动构建方式，且对同源率收益很低 |
| `LICENSE` | 许可方向需你或法务决定 |
| 浏览器手工冒烟 | 需要真实浏览器环境 |
| 提交 | 提交信息与`.dsh/`入库口径需你定 |

**建议的收尾动作**：① 加 `.gitattributes` 固定 LF（见第 20 轮）；② 补 `LICENSE`；
③ 按建议信息提交（`refactor: 重写实现以消除比对工具误判（行为由黄金输出验证）`）；
④ 上线前补两处冒烟（`Logs` 的 WebSocket、两个抽屉的展开态）。

## 验证环境限制

本机未安装任何第三方依赖（fastapi / pydantic / psycopg2 / httpx / docker / pandas / sklearn …），
也没有测试数据。当前策略与可信度：

- **纯逻辑层（hanabi 模型层）**：真实导入 + 黄金输出，结论可信
- **API 层**：fastapi / pydantic / 服务层全部用桩件替换，验证的是路由契约与处理函数行为；
  真实框架集成（依赖注入、参数校验、CORS、WebSocket 协议）不在覆盖内，上线前需冒烟
- **log_storage**：psycopg2 与 httpx 用桩件替换，验证的是 SQL 与连接生命周期；
  **未经过真实 PostgreSQL 验证**，上线前需对真实库跑一次（建表 + 写入 + 查询 + 清理）
- 其余依赖第三方库的模块（reducer / exporter / queue）：改造前需先补依赖或补桩件
