"""命令行入口。

用法：`python -m hanabi.reducer <告警CSV> [-t 阈值] [-m 每簇上限] [-s 相似度] [--no-cluster] [-v]`

模块拆包前是 `python hanabi/reducer.py`，改为包之后入口统一走 `-m`。
"""

from .cli import main

if __name__ == "__main__":
    main()
