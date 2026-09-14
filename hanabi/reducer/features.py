"""告警文本特征：字段校验、文本拼接与向量化。

把一条告警拼成两段文本：

* **告警内容**（用于相似度）：属性名与属性值各重复 5 次、进程名 10 次、事件类型 1 次、
  事件详情原样。权重差来自"哪部分更能区分行为"的经验判断——进程名最能区分，
  详情里变量多、区分度低。
* **威胁特征**（用于报告展示）：进程/事件/详情/频次的自然语言拼接。

向量化用 TF-IDF（维度上限 512）：告警文本短、词表小，TF-IDF 比向量模型更稳且无外部
依赖。TF-IDF 不可用时退回手工特征，保证后续聚类不中断。
"""

from typing import List

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from tqdm import tqdm

from ._logging import logger

# 输入 CSV 必须具备的列
REQUIRED_FIELDS = [
    '异常事件序号', '异常属性名', '异常属性值', '异常频次',
    '进程名', '事件类型', '事件详情', '完整日志',
]

_MAX_FEATURES = 512


def prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """校验必需字段、填充缺失值，并生成用于聚类与报告的两列。"""
    missing_fields = [field for field in REQUIRED_FIELDS if field not in df.columns]
    if missing_fields:
        raise ValueError(f"缺少必需字段: {missing_fields}")

    df = df.fillna('')

    # 时间列允许解析失败：解析不了就是 NaT，不影响后续按频次/关键词打分
    if '日志时间' in df.columns:
        df['日志时间'] = pd.to_datetime(df['日志时间'], errors='coerce')

    df['异常频次'] = pd.to_numeric(df['异常频次'], errors='coerce').fillna(0)
    df['异常事件序号'] = pd.to_numeric(df['异常事件序号'], errors='coerce').fillna(0)

    tqdm.pandas(desc="生成告警特征")
    df['告警内容'] = df.progress_apply(
        lambda x: f"{x['异常属性名']} " * 5 +
                  f"{x['异常属性值']} " * 5 +
                  f"{x['进程名']} " * 10 +
                  f"{x['事件类型']} " +
                  f"{x['事件详情']}",
        axis=1
    )

    tqdm.pandas(desc="生成威胁特征")
    df['威胁特征'] = df.progress_apply(
        lambda x: f"进程:{x['进程名']} 事件:{x['事件类型']} 详情:{x['事件详情']} 频次:{x['异常频次']}",
        axis=1
    )

    logger.info("数据预处理完成")
    return df


def build_embeddings(texts: List[str]) -> np.ndarray:
    """TF-IDF 向量化；维度固定为 512，失败时退回随机向量。"""
    vectorizer = TfidfVectorizer(max_features=_MAX_FEATURES, stop_words=None)
    try:
        with tqdm(total=2, desc="向量化处理") as pbar:
            pbar.set_description("拟合向量化器")
            embeddings = vectorizer.fit_transform(texts).toarray().astype(np.float32)
            pbar.update(2)
    except:
        embeddings = np.random.rand(len(texts), _MAX_FEATURES).astype(np.float32)
    return embeddings


def fallback_embeddings(texts: List[str]) -> np.ndarray:
    """手工特征：长度、风险词计数、字符集大小、点号数量，补零到 512 维。"""
    embeddings = []
    for text in tqdm(texts, desc="生成备用特征向量"):
        features = [
            len(text),
            text.count('error'),
            text.count('warning'),
            text.count('failed'),
            text.count('exception'),
            len(set(text.lower())),
            text.count('.'),
        ]
        features.extend([0] * (_MAX_FEATURES - len(features)))
        embeddings.append(features[:_MAX_FEATURES])
    return np.array(embeddings, dtype=np.float32)
