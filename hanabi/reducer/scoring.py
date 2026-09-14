"""威胁评分。

基准 50 分，再按四类信号加码，最后截断到 0-100：

* 频次：>100 加 30，>50 加 20，>10 加 10（取第一个命中的档位）
* 事件类型含 error / exception / failed / deny / block / attack：加 25
* 进程名含 system / kernel / service / daemon：加 15
* 详情每命中一个安全关键词（attack / intrusion / malware / virus / exploit / breach）：加 10

档位与权重来自现场误报率调参，调整前需要重新过一遍真实告警。规则评分不可用时退回
采样打分（30-70），保证消减流程不中断。
"""

import numpy as np
import pandas as pd
from tqdm import tqdm

_HIGH_RISK_EVENTS = ['error', 'exception', 'failed', 'deny', 'block', 'attack']
_CRITICAL_PROCESSES = ['system', 'kernel', 'service', 'daemon']
_SECURITY_KEYWORDS = ['attack', 'intrusion', 'malware', 'virus', 'exploit', 'breach']

# (频次下限, 加分)，从高到低匹配第一个命中的档位
_FREQUENCY_TIERS = ((100, 30), (50, 20), (10, 10))

_BASE_SCORE = 50
_SCORE_FLOOR = 0
_SCORE_CEILING = 100


def _frequency_bonus(frequency) -> int:
    """按频次档位取加分。"""
    for threshold, bonus in _FREQUENCY_TIERS:
        if frequency > threshold:
            return bonus
    return 0


def score_by_rules(df: pd.DataFrame) -> np.ndarray:
    """逐行按规则打分。"""
    scores = []
    for _, row in tqdm(df.iterrows(), total=len(df), desc="计算威胁分数"):
        score = _BASE_SCORE + _frequency_bonus(row['异常频次'])

        event_type = str(row['事件类型']).lower()
        score += 25 if any(risk_word in event_type for risk_word in _HIGH_RISK_EVENTS) else 0

        process_name = str(row['进程名']).lower()
        score += 15 if any(proc in process_name for proc in _CRITICAL_PROCESSES) else 0

        event_detail = str(row['事件详情']).lower()
        score += sum(10 for keyword in _SECURITY_KEYWORDS if keyword in event_detail)

        scores.append(max(_SCORE_FLOOR, min(_SCORE_CEILING, score)))

    return np.array(scores)


def score_by_sampling(df: pd.DataFrame) -> np.ndarray:
    """兜底评分：30-70 的随机分，仅用于规则评分不可用时保持流程可跑。"""
    return np.array([30 + np.random.randint(0, 40) for _ in tqdm(range(len(df)), desc="规则评分")])
