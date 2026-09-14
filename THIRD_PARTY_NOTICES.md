# 第三方组件与出处声明

本仓库包含基于开源项目裁剪或派生的配置文件。本文件登记其出处与许可证义务；
新增此类文件时应同步登记。

## Falco 配置

| 文件 | 来源 | 许可证 | 本项目的处理 |
|---|---|---|---|
| `falco/falco.yaml` | [falcosecurity/falco](https://github.com/falcosecurity/falco) 的默认配置 `falco.yaml`，取自镜像 `falcosecurity/falco:latest`（Falco 0.44.1） | Apache-2.0 | **裁剪**：只保留本项目依赖的配置键（规则文件、容器插件、输出与 JSON 格式、采集引擎调优等 81 行），删除上游的说明注释与默认值条目。文件头注明上游出处，未添加任何"自研"标记 |
| `falco/custom_rules.yaml` | 本项目自研规则（容器名单、条件与输出字段均为本项目定义） | 本项目 | 无 |
| `falco/deploy.sh` | 本项目 | 本项目 | 无 |

`falco/falco.yaml` 的裁剪依据、逐项判定过程与校验结果记录在
`.dsh/similarity-refactor-progress.md`（第 5 轮）。校验方式：

```bash
docker build -f Dockerfile.falco -t hanabi_falco:latest .
docker run --rm --entrypoint falco hanabi_falco:latest --dry-run   # 期望：exit 0，schema validation: ok
```

裁剪只删除以下三类键，均不影响运行时行为：

1. 官方默认即"关闭"的功能：`file_output` / `http_output` / `program_output` / `grpc_output`、
   `capture.*`（已实测：不配置任何输出时 Falco 直接报 "No output configured"，
   说明所有输出默认关闭）
2. 非激活引擎的子项：`engine.kmod.*` / `engine.ebpf.*` / `engine.gvisor.*` / `engine.replay.*`
   （本项目用 `engine.kind: modern_ebpf`）
3. 仅在对应功能启用后才有意义的细项：`metrics.*` 的计数器开关（`metrics.enabled` 保留为
   false）、`grpc.*`、`webserver.*` 的证书相关项

其中删除 `engine.ebpf` 还顺带修掉了一处问题：该键在 Falco 0.44.1 的配置 schema 中已不存在，
原文件会导致 `schema validation: failed for <root>[engine]`。

## 其他配置与依赖

| 文件 | 说明 |
|---|---|
| `prometheus/prometheus.yml` | 本项目自建（4 行，抓取本项目 exporter） |
| `grafana/dashboard.json` | **自建**：39 行最简看板，查询用的是本项目 exporter 自己的指标名（`syscall_events_total` 等），无社区看板导出物特征（无 `__inputs`、无 datasource 变量、无导出元数据） |
| `falco/custom_rules.yaml` | **自研**：规则条件与输出字段都是本项目自有的容器名单（`43039infrasecurity-*`）与画像字段 |
| `pyproject.toml` / `uv.lock` / `web/package.json` | 常规开源依赖，许可证随各自分发包提供 |

逐文件的来源判定与检索记录见 `.dsh/audit/provenance-inventory.md`。

## 缺失项

- 仓库根目录没有 `LICENSE`：本项目自身的许可方向（专有 / 开源）尚未确定，
  需由项目负责人或法务决定；确定后应补充本文件与源码头部的相应声明。
