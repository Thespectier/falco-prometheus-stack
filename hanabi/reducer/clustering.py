"""告警聚类：按相似度合并同类告警，并选出每个簇的代表。

合并是单链式的：两条告警的相似度达到阈值就并入同一簇，不做层次或密度判断。告警
规模在千条量级，n² 的相似度矩阵与 O(n²) 的合并足够快，也避免了额外依赖。

代表告警取"簇内与其他成员平均相似度最高"的那条：它最贴近这个簇的行为共性，人工
核对时一条即可代表一片。
"""

from typing import Dict, List

import numpy as np
import pandas as pd
from tqdm import tqdm


def merge_similar(similarity_matrix: np.ndarray, threshold: float) -> List[int]:
    """按相似度合并告警，返回每条告警所属的簇号（从 0 起连续编号）。"""
    count = similarity_matrix.shape[0]
    clusters = list(range(count))

    with tqdm(total=count * (count - 1) // 2, desc="合并相似告警") as pbar:
        for i in range(count):
            for j in range(i + 1, count):
                if similarity_matrix[i, j] >= threshold:
                    old_cluster, new_cluster = clusters[j], clusters[i]
                    clusters = [new_cluster if c == old_cluster else c for c in clusters]
                pbar.update(1)

    unique_clusters = list(set(clusters))
    cluster_mapping = {old: new for new, old in enumerate(unique_clusters)}
    return [cluster_mapping[c] for c in clusters]


def pick_representatives(
    df: pd.DataFrame,
    clusters: List[int],
    similarity_matrix: np.ndarray,
) -> Dict[int, int]:
    """为每个簇挑一条代表告警；单成员簇直接取自己。"""
    representatives = {}
    df_with_clusters = df.copy()
    df_with_clusters['cluster'] = clusters

    for cluster_id in tqdm(set(clusters), desc="选择簇代表"):
        cluster_indices = df_with_clusters[df_with_clusters['cluster'] == cluster_id].index.tolist()

        if len(cluster_indices) == 1:
            representatives[cluster_id] = cluster_indices[0]
        else:
            best_idx = max(
                cluster_indices,
                key=lambda idx: np.mean([
                    similarity_matrix[idx, other_idx]
                    for other_idx in cluster_indices
                    if other_idx != idx
                ]),
            )
            representatives[cluster_id] = best_idx

    return representatives
