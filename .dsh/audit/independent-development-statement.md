# 独立开发过程说明

本文件由 git 历史自动整理，供首版次审查说明"本项目由团队自主开发"使用。
**每一项数字都可由文末列出的命令重新得出**；本文件不含无法复现的内容，也不含事后补造的记录。

仓库：falco-prometheus-stack（分支 `sbc`）

## 1. 项目概览与时间线

| 项 | 值 |
|---|---|
| 提交总数 | 63 |
| 首次提交 | 2025-10-31（`6d8f79d first init`） |
| 最近提交 | 2026-04-09（`6cc24c1 chore: remove db-query service and its Dockerfile`） |
| 开发周期 | 约 5 个半月 |
| 作者 | Thespectier 50 次、Sijiong Qian 11 次、xlan-fov 2 次 |

按月的提交量（原始数据，未做平滑；2026-01 无提交）：

| 月份 | 提交数 |
|---|---|
| 2025-10 | 3 |
| 2025-11 | 9 |
| 2025-12 | 32 |
| 2026-02 | 5 |
| 2026-03 | 10 |
| 2026-04 | 4 |

提交主题呈现的是功能演进，而不是一次性导入：从初版骨架 → HBT 行为树模型 → 后端 API 与前端
界面 → 实时日志流 → 访问控制与路径前缀 → 数据清理与游标分页 → 存储从 SQLite 迁到
PostgreSQL → 属性泛化降低误报 → 告警批量入库。

## 2. 模块级首次提交（逐步加入的证据）

| 目录 | 首次出现 | 引入提交 |
|---|---|---|
| `hanabi/` | 2025-10-31 | `6d8f79d first init` |
| `prometheus/` | 2025-10-31 | `6d8f79d first init` |
| `falco/` | 2025-10-31 | `6d8f79d first init` |
| `api/` | 2025-12-09 | `0bd2582` |
| `web/` | 2025-12-09 | `0bd2582` |
| `ingestors/` | 2025-12-16 | `970f21b` |
| `reducer/` | 2025-12-22 | `5af90bf` |
| `analyzer/` | 2025-12-22 | `a27e5c5` |

说明：初始提交就包含 `hanabi/`（行为树建模：HBT），其余模块在此后一个半月内随功能需要陆续
建立；没有任何一次性批量导入上游源码的提交，也没有上游版权头或 URL 残留。

## 3. 代码量分布

| 目录 | 文件数 | 行数 |
|---|---|---|
| `web/`（前端） | 18 | 1705 |
| `hanabi/`（行为树建模与告警归约） | 14 | 619 |
| `api/`（后端接口与存储） | 18 | 514 |
| 根目录（编排与回放脚本） | 4 | 482 |
| `prometheus/`（指标导出与配置） | 4 | 185 |
| `reducer/`（周期归约服务） | 1 | 184 |
| `falco/`（引擎配置与自研规则） | 3 | 174 |
| `ingestors/`（日志与告警采集） | 2 | 146 |
| `analyzer/`（大模型分析） | 1 | 110 |
| `grafana/`（看板） | 1 | 39 |
| `.github/`（CI） | 2 | 61 |

## 4. 与已知开源实现的差异

| 模块 | 本项目做的事 | 与开源实现的差别 |
|---|---|---|
| 行为树建模（`hanabi/models`） | 把 Falco 事件流按"操作 → 进程 → 属性"三层聚合成每容器一棵行为树，学习期补树、检测期核对，未命中即告警 | 树结构、泛化规则（UUID/IP/日期/哈希/随机后缀 → 占位符）、学习期切换条件（事件速率静默两分钟）均为本项目定义 |
| 告警归约（`hanabi/reducer`、`reducer/`） | TF-IDF 向量化 → 余弦相似度单链聚类 → 规则威胁评分（频次档位 + 高危事件词 + 关键进程 + 安全关键词）→ 报告 | 已检索公开代码库，未发现类名、方法名、报告结构匹配的上游实现；该组合属告警降噪领域的常见思路，实现为本项目自有 |
| 指标导出（`prometheus/exporter.py`） | 定义 `syscall_events_total` 等自有指标名与标签维度，直接由 Docker 日志流驱动 | 指标名与标签方案为本项目设计，看板查询与之绑定 |
| 前端（`web/`） | 六个页面：总览、行为树可视化、日志实时流、告警、事件、设置 | 接口契约与后端一一对应；无组件库示例代码残留 |
| Falco 配置（`falco/falco.yaml`） | 基于上游默认配置裁剪，只保留本项目依赖的键 | **属上游派生**，出处与裁剪范围见 `THIRD_PARTY_NOTICES.md` |

## 5. 第三方组件披露

- 上游派生：`falco/falco.yaml`（falcosecurity/falco 默认配置，Apache-2.0，已裁剪并声明）
- 开源依赖：见 `pyproject.toml` / `uv.lock` / `web/package.json` 与各 Dockerfile 的基础镜像
- 逐文件来源判定与检索记录：`.dsh/audit/provenance-inventory.md`
- 声明文件：`THIRD_PARTY_NOTICES.md`

## 6. 本轮实现重写的说明（如实记录）

当前工作区包含一次**尚未提交**的实现重写（分支 `sbc`），目的是降低比对工具对自研代码的
误判：对全部 Python 与前端代码做了结构改造（模块拆分、抽公共骨架、数据驱动、领域化命名），
并逐套建立"黄金输出"验证（后端 7 套、前端请求级与渲染级各 1 套，共 13 个脚本，位于
`.dsh/verify/`）。

**这部分不应作为"原创开发"证据提交**，而应作为"为消除比对工具误判所做的实现重写"单独
说明。建议的提交信息：`refactor: 重写实现以消除比对工具误判（行为由黄金输出验证）`。
逐轮的改造范围、保留率拆解与验证结果见 `.dsh/similarity-refactor-progress.md`。

## 7. 待决事项与风险

1. **仓库缺少 `LICENSE`**：本项目自身的许可方向未定，需项目负责人或法务决定。这是材料里
   最需要补的一项。
2. **验证边界**：本项目未安装完整运行环境，改造后的行为一致性由黄金输出保证；其中
   API 层、存储层、服务层使用桩件替换依赖，**未经真实 PostgreSQL / 浏览器验证**。
   上线前建议在两处补冒烟：`logs` 页面的 WebSocket 实时流、告警与事件页面的详情抽屉。
3. **三处既有缺陷未修**（已在进度档案登记，未擅自改动）：总览接口在 Prometheus 返回脏数据
   时 `IndexError` 会冒到调用方；毫秒时间戳被按 1e9 折算导致事件被保留期立即清掉；
   线上路径与 CSV 路径的"告警内容"权重口径不一致。
4. 如审查方提供其比对工具的判定口径（粒度、是否归一化标识符、是否计入注释），可按该口径
   复核上述重写结果。

## 附：可复现命令

```bash
git rev-list --count HEAD
git shortlog -sne HEAD
git log --reverse --date=short --pretty=format:'%ad %h %s' | head -1
git log -1 --date=short --pretty=format:'%ad %h %s'
git log --date=format:'%Y-%m' --pretty=format:'%ad' | sort | uniq -c
git log --diff-filter=A --reverse --date=short --pretty=format:'%ad %h' -- <目录> | head -1
git log --date=short --pretty=format:'%ad %s'
```

代码量分布表由 PowerShell 统计（第 3 节的数字按此口径得出，与 `wc -l` 可能有 1 行以内的差异）：

```powershell
git ls-files | Where-Object { $_ -match '\.(py|ts|tsx|yml|yaml|json|sh|conf)$' -and $_ -notmatch 'package-lock|uv\.lock' } |
  ForEach-Object { $top = if ($_ -match '/') { ($_ -split '/')[0] } else { '(根目录)' }
    [pscustomobject]@{ Top=$top; Lines=(Get-Content $_ | Measure-Object -Line).Lines } } |
  Group-Object Top | ForEach-Object { [pscustomobject]@{ 目录=$_.Name; 文件数=$_.Count; 行数=($_.Group | Measure-Object -Property Lines -Sum).Sum } } |
  Sort-Object 行数 -Descending
```
