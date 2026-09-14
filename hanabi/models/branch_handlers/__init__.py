"""行为树的分支处理器。

层次定义按分支拆到 process / network / file 三个模块，公共骨架在 base。
对外仍从本包导出四个类，既有的
`from .branch_handlers import ProcessBranchHandler` 等导入路径不受影响。
"""

from .base import BranchHandler, generalize_key, publish_alert, update_learn_state
from .file import FileBranchHandler
from .network import NetworkBranchHandler
from .process import ProcessBranchHandler

__all__ = [
    "BranchHandler",
    "FileBranchHandler",
    "NetworkBranchHandler",
    "ProcessBranchHandler",
    "generalize_key",
    "publish_alert",
    "update_learn_state",
]
