# 代码来源清单

按 `code-provenance-audit` skill 产出：逐文件判定来源，供首版次材料使用。
判定依据是仓库内可核查的证据（文件内标记、git 历史、与上游客体的比对），不是事后回忆。

仓库：falco-prometheus-stack（分支 `sbc`）
判定时间：见本文件的 git 提交记录

## 判定方法

| 手段 | 说明 |
|---|---|
| 文件内标记 | 上游 URL、版权头、`SPDX-License-Identifier`、上游特有的键名与默认值 |
| 文件形态 | 整份拷贝的上游默认配置、社区看板导出物、示例代码集 |
| git 历史 | `git log --diff-filter=A` 首次提交是否随功能演进逐个加入，是否有批量导入 |
| 实体比对 | 与上游同版本文件做逐键对比（falco 配置即用此法，含生效配置对比） |
| 公开检索 | 对疑似"设计模式化"的模块检索是否存在同名/同结构的开源实现 |

## 结论汇总

| 类别 | 文件数 | 说明 |
|---|---|---|
| 自研 | 除下表所列外的全部源码与配置 | Python 38 个、前端 11 个、Docker/compose/脚本/YAML 等 |
| 上游派生（已裁剪并声明出处） | 1 | `falco/falco.yaml` |
| 第三方依赖 | 3 个清单 | `pyproject.toml` / `uv.lock` / `web/package.json`（另有各 Dockerfile 内的镜像） |
| 疑似逐字片段 | 0（未发现） | 见下方"检索与比对记录" |

## 逐项判定

### 自研代码

| 范围 | 判定依据 |
|---|---|
| `api/**`、`hanabi/**`、`reducer/**`、`ingestors/**`、`analyzer/**`、`prometheus/exporter.py`、根 `main.py` | git 历史为逐功能演进（63 次提交、3 位作者、`first init` → 目录重构 → HBT 模型 → PostgreSQL 迁移）；无上游版权头或 URL；无批量导入提交。本轮已全部重写并通过黄金输出验证 |
| `web/src/**` | 同上；接口字段与后端一一对应，属本项目自有契约；无组件库示例代码残留标记 |
| `falco/custom_rules.yaml` | 规则条件与输出字段都是本项目自有的容器名单（`43039infrasecurity-*`）与画像字段；属 Falco 规则语法的常规写法 |
| `grafana/dashboard.json` | 39 行最简看板，查询用的是**本项目 exporter 自己的指标名**（`syscall_events_total` 等）；无社区看板导出物特征（无 `__inputs`、无 datasource 变量、无导出元数据） |
| `prometheus/prometheus.yml`、`falco/deploy.sh`、`prometheus/deploy.sh`、`docker-compose*.yml`、`Dockerfile.*`、`web/nginx.conf`、`web/nginx-proxy-headers.conf` | 4~226 行的项目编排，目标地址与容器名均为本项目专有 |
| `hanabi/models/example.json` | **本项目自行抓取的样本数据**：3 条真实 Falco 事件（JSONL），时间戳为 2025-11-02，含本环境特有的主机名、容器 ID 与第三方容器名（如 `gemini-balance-mysql`）——上游示例不可能带上这些；属测试/演示数据，非代码 |

### 上游派生

| 文件 | 上游 | 许可证 | 处理 |
|---|---|---|---|
| `falco/falco.yaml` | [falcosecurity/falco](https://github.com/falcosecurity/falco) 默认配置（版本对齐 0.44.1） | Apache-2.0 | 从 1149 行裁剪到 81 行，只保留本项目依赖的键；文件头声明出处；已用 `falco --dry-run` 在镜像内校验（exit 0，schema ok），并与改造前的生效配置逐键比对（保留键的值零变化）。详见 `THIRD_PARTY_NOTICES.md` 与 `.dsh/similarity-refactor-progress.md` 第 5 轮 |

### 第三方依赖

| 清单 | 说明 |
|---|---|
| `pyproject.toml` / `uv.lock` | docker、flask、prometheus-client、waitress、rich、fastapi、uvicorn、httpx、pydantic-settings、psycopg2-binary；reducer 另用 pandas / numpy / scikit-learn / tqdm |
| `web/package.json` / `package-lock.json` | react、antd、echarts、@tanstack/*、zustand、react-router-dom、vite、typescript |
| `Dockerfile.*` | 基础镜像：`falcosecurity/falco:latest`、`postgres:15-alpine`、python/node 官方镜像 |

依赖的许可证随各自分发包提供，仓库内不需要重复声明；如需在材料中列出，按上表逐项引用其官方许可证页。

## 检索与比对记录

- **falco 配置**：与镜像内同版本默认配置逐键比对（`--support` 导出生效配置），确认项目真实覆盖仅 3 项。
- **`hanabi/reducer`（告警消减：TF-IDF 向量化 → 相似度聚类 → 规则威胁评分 → 报告）**：
  以「告警消减 AlertReducer 威胁评分 相似度聚类」「AlertReducer reduce_alerts threat_score」
  等关键词检索公开代码库，**未发现与该项目类名、方法名、报告结构匹配的上游实现**；
  命中的是思路相近但实现不同的项目（如告警聚合/威胁情报平台）。
  结论：未发现可指认的上游来源；该设计属"告警降噪"领域的常见组合，
  如审查方另有比对上游客体，可按 `.dsh/verify/reducer_golden.py` 的结构逐段复核。
- **其余源码**：本轮改造前后均无上游版权头、URL 或示例残留。

## 待决事项

1. **仓库缺少 `LICENSE`**：本项目自身的许可方向（专有 / 开源）未定，需项目负责人或法务决定。
   这是首版次材料中最需要补的一项——"自主知识产权"的主张需要落脚点。
2. **三个后端 Dockerfile 高度重复**（`Dockerfile.backend` / `.reducer` / `.analyzer` 共 115 行，
   构建阶段几乎逐行相同）。可抽一个公共基础镜像让三者继承，能显著减少样板；但这会改动构建
   方式（需先构建基础镜像 / 调整 compose），属需要确认的改动，本轮未做。
3. **shell 脚本在 Windows 工作区是 CRLF**（4 个脚本全部如此，仓库无 `.gitattributes`）：
   在 Windows 上构建镜像会让入口脚本在容器里直接报 `illegal option -`（已复现）。
   建议加 `.gitattributes` 固定 LF，属仓库级口径，需确认。
4. 若审查方提供其比对工具的**判定口径**（粒度、是否归一化标识符、是否计入注释），
   可按该口径复核本轮改造结果；本轮只保证实现被真实重写，不声称任何同源率读数。
