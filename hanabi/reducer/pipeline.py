"""告警消减主流程。

`AlertReducer` 是对外入口：先 `load_alerts` 载入（或直接给一个符合字段要求的
DataFrame），再 `reduce_alerts` 消减，最后 `generate_report` / `save_results` 产出。

各步骤的纯计算放在 features / clustering / scoring / report 里，这里只负责串流程、
记录各阶段耗时并保留中间状态（原始数据、消减结果、聚类结果、威胁分数），供报告与
排障使用。
"""

import json
import time
from typing import Any, Dict, List

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from tqdm import tqdm

from . import clustering, features, scoring
from . import report as report_module
from ._logging import logger

# 各阶段耗时统计的键
_TIME_STAT_KEYS = [
    'data_loading', 'data_preprocessing', 'embedding_generation',
    'clustering', 'threat_scoring', 'alert_reduction',
    'report_generation', 'result_saving', 'total_processing',
]


class AlertReducer:
    """告警消减模块。"""

    def __init__(self, model_endpoint: str = None, api_key: str = None):
        self.model_endpoint = model_endpoint
        self.api_key = api_key
        self.original_alerts = self.processed_alerts = self.cluster_results = self.threat_scores = None
        self.time_stats = dict.fromkeys(_TIME_STAT_KEYS, 0)

    def _record_time(self, operation: str, start_time: float):
        """记录某阶段的耗时。"""
        elapsed_time = time.time() - start_time
        self.time_stats[operation] = elapsed_time
        logger.info(f"{operation} 耗时: {elapsed_time:.3f} 秒")

    # --------------------------------------------------------------- 载入
    def load_alerts(self, csv_file_path: str) -> pd.DataFrame:
        """从 CSV 载入告警并完成预处理。"""
        start_time = time.time()
        try:
            df = pd.read_csv(csv_file_path, encoding='utf-8')
            logger.info(f"成功加载告警数据：{len(df)} 条记录")

            preprocess_start = time.time()
            df = self._preprocess_data(df)
            self._record_time('data_preprocessing', preprocess_start)

            self.original_alerts = df
            self._record_time('data_loading', start_time)
            return df
        except Exception as e:
            logger.error(f"加载告警数据失败：{e}")
            raise

    def _preprocess_data(self, df: pd.DataFrame) -> pd.DataFrame:
        return features.prepare_dataframe(df)

    # --------------------------------------------------------------- 向量化
    def get_embeddings(self, texts: List[str]) -> np.ndarray:
        """取文本向量；主路径失败时退回备用特征，不中断后续聚类。"""
        start_time = time.time()
        try:
            embeddings = self._simulate_embeddings(texts)
            logger.info(f"获取嵌入向量完成：{len(texts)} 个文本")
        except Exception as e:
            logger.error(f"获取嵌入向量失败：{e}")
            embeddings = self._fallback_embeddings(texts)

        self._record_time('embedding_generation', start_time)
        return embeddings

    def _simulate_embeddings(self, texts: List[str]) -> np.ndarray:
        return features.build_embeddings(texts)

    def _fallback_embeddings(self, texts: List[str]) -> np.ndarray:
        return features.fallback_embeddings(texts)

    # ---------------------------------------------------------------- 聚类
    def cluster_alerts(self, df: pd.DataFrame, similarity_threshold: float = 0.8) -> Dict[str, Any]:
        """按相似度聚类并选出簇代表，结果缓存在 self.cluster_results。"""
        start_time = time.time()
        print("开始告警聚类...")

        alert_texts = df['告警内容'].tolist()
        embeddings = self.get_embeddings(alert_texts)

        print("计算相似度矩阵...")
        similarity_start = time.time()
        similarity_matrix = cosine_similarity(embeddings)
        logger.info(f"相似度矩阵计算耗时: {time.time() - similarity_start:.3f} 秒")

        print("执行聚类算法...")
        clustering_start = time.time()
        clusters = self._similarity_clustering(similarity_matrix, similarity_threshold)
        logger.info(f"聚类算法耗时: {time.time() - clustering_start:.3f} 秒")

        print("选择代表性告警...")
        representative_start = time.time()
        cluster_representatives = self._select_cluster_representatives(df, clusters, similarity_matrix)
        logger.info(f"代表性告警选择耗时: {time.time() - representative_start:.3f} 秒")

        self.cluster_results = {
            'clusters': clusters, 'similarity_matrix': similarity_matrix, 'embeddings': embeddings,
            'cluster_count': len(set(clusters)), 'original_count': len(df), 'representatives': cluster_representatives
        }

        self._record_time('clustering', start_time)
        print(f"聚类完成：{len(df)} 个告警聚类为 {self.cluster_results['cluster_count']} 个簇")
        return self.cluster_results

    def _similarity_clustering(self, similarity_matrix: np.ndarray, threshold: float) -> List[int]:
        return clustering.merge_similar(similarity_matrix, threshold)

    def _select_cluster_representatives(
        self,
        df: pd.DataFrame,
        clusters: List[int],
        similarity_matrix: np.ndarray,
    ) -> Dict[int, int]:
        return clustering.pick_representatives(df, clusters, similarity_matrix)

    # ------------------------------------------------------------ 威胁评分
    def score_threats(self, df: pd.DataFrame) -> np.ndarray:
        """给每条告警打分；规则评分失败时退回采样评分。"""
        start_time = time.time()
        print("开始威胁评分...")

        try:
            scores = self._simulate_threat_scoring(df)
            print("威胁评分完成")
        except Exception as e:
            logger.error(f"威胁评分失败：{e}")
            scores = self._rule_based_scoring(df)

        self._record_time('threat_scoring', start_time)
        return scores

    def _simulate_threat_scoring(self, df: pd.DataFrame) -> np.ndarray:
        return scoring.score_by_rules(df)

    def _rule_based_scoring(self, df: pd.DataFrame) -> np.ndarray:
        return scoring.score_by_sampling(df)

    # ------------------------------------------------------------ 消减流程
    def reduce_alerts(
        self,
        df: pd.DataFrame,
        cluster_reduction: bool = True,
        threat_threshold: float = 60.0,
        max_alerts_per_cluster: int = 3,
        similarity_threshold: float = 0.8,
    ) -> pd.DataFrame:
        """五步消减：聚类 → 评分 → 过滤 → 选代表 → 排序。"""
        start_time = time.time()
        print("\n" + "=" * 60)
        print("开始告警消减流程")
        print("=" * 60)

        total_steps = 5 if cluster_reduction else 4
        with tqdm(total=total_steps, desc="告警消减进度", unit="步骤") as main_pbar:

            # 步骤1: 聚类处理
            main_pbar.set_description("步骤1: 聚类处理")
            if cluster_reduction:
                cluster_results = self.cluster_alerts(df, similarity_threshold)
                df_clustered = df.copy()
                df_clustered['cluster'] = cluster_results['clusters']
            else:
                df_clustered = df.copy()
                df_clustered['cluster'] = range(len(df))
            main_pbar.update(1)

            # 步骤2: 威胁评分
            main_pbar.set_description("步骤2: 威胁评分")
            threat_scores = self.score_threats(df_clustered)
            df_clustered['threat_score'] = threat_scores
            self.threat_scores = threat_scores
            main_pbar.update(1)

            # 步骤3: 威胁过滤
            main_pbar.set_description("步骤3: 威胁过滤")
            filter_start = time.time()
            df_filtered = df_clustered[df_clustered['threat_score'] >= threat_threshold].copy()
            logger.info(f"威胁分数过滤耗时: {time.time() - filter_start:.3f} 秒")
            main_pbar.update(1)

            # 步骤4: 告警选择
            main_pbar.set_description("步骤4: 告警选择")
            selection_start = time.time()
            if cluster_reduction:
                if df_filtered.empty:
                    df_reduced = df_filtered.head(0)
                else:
                    reduced_alerts = [
                        df_filtered[df_filtered['cluster'] == cluster_id].nlargest(
                            max_alerts_per_cluster, 'threat_score'
                        )
                        for cluster_id in tqdm(
                            df_filtered['cluster'].unique(),
                            desc="处理各簇告警",
                            leave=False
                        )
                    ]
                    df_reduced = (
                        pd.concat(reduced_alerts, ignore_index=True)
                        if reduced_alerts
                        else df_filtered.head(0)
                    )
            else:
                df_reduced = df_filtered.nlargest(len(df_filtered), 'threat_score')
            logger.info(f"告警选择耗时: {time.time() - selection_start:.3f} 秒")
            main_pbar.update(1)

            # 步骤5: 结果排序
            main_pbar.set_description("步骤5: 结果排序")
            sort_start = time.time()
            df_reduced = df_reduced.sort_values('threat_score', ascending=False).reset_index(drop=True)
            logger.info(f"排序耗时: {time.time() - sort_start:.3f} 秒")
            main_pbar.update(1)

        self.processed_alerts = df_reduced
        self._record_time('alert_reduction', start_time)

        print(f"告警消减完成：{len(df)} -> {len(df_reduced)} 条告警")
        print(f"消减率: {((len(df) - len(df_reduced)) / len(df) * 100):.2f}%")
        return df_reduced

    # ---------------------------------------------------------------- 报告
    def generate_report(self) -> Dict[str, Any]:
        """生成消减报告；未跑过消减流程时抛错。"""
        start_time = time.time()

        if self.original_alerts is None or self.processed_alerts is None:
            raise ValueError("请先执行告警消减流程")

        report = report_module.build_report(
            original_count=len(self.original_alerts),
            reduced_count=len(self.processed_alerts),
            performance_stats_factory=self._generate_performance_stats,
            cluster_results=self.cluster_results,
            threat_scores=self.threat_scores,
            processed_alerts=self.processed_alerts,
        )

        self._record_time('report_generation', start_time)
        return report

    def _generate_performance_stats(self) -> Dict[str, Any]:
        return report_module.build_performance_stats(
            time_stats=self.time_stats,
            original_count=len(self.original_alerts) if self.original_alerts is not None else 0,
            reduced_count=len(self.processed_alerts) if self.processed_alerts is not None else 0,
            cluster_results=self.cluster_results,
        )

    # ---------------------------------------------------------------- 落盘
    def save_results(self, output_path: str = 'reduced_alerts.csv'):
        """把消减结果写成 CSV，并同时落一份报告 JSON。"""
        start_time = time.time()
        print("保存处理结果...")

        if self.processed_alerts is None:
            raise ValueError("没有可保存的消减结果")

        with tqdm(total=2, desc="保存文件") as pbar:
            pbar.set_description("保存CSV文件")
            self.processed_alerts.to_csv(output_path, index=False, encoding='utf-8')
            logger.info(f"消减后的告警数据已保存到：{output_path}")
            pbar.update(1)

            pbar.set_description("保存报告文件")
            report_path = output_path.replace('.csv', '_report.json')
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(self.generate_report(), f, ensure_ascii=False, indent=2)
            logger.info(f"消减报告已保存到：{report_path}")
            pbar.update(1)

        self._record_time('result_saving', start_time)
