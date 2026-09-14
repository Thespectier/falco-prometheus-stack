"""告警消减子系统。

对外入口是 `AlertReducer`；命令行用法为 `python -m hanabi.reducer <csv>`。
子模块划分：

| 模块 | 职责 |
|---|---|
| `features` | 字段校验、文本拼接、TF-IDF 向量化与备用特征 |
| `clustering` | 相似度合并与簇代表选择 |
| `scoring` | 威胁评分（规则打分与兜底采样） |
| `report` | 消减报告与性能统计 |
| `pipeline` | 主流程编排（AlertReducer） |
| `cli` | 命令行入口 |
"""

from .cli import main
from .pipeline import AlertReducer

__all__ = ["AlertReducer", "main"]
