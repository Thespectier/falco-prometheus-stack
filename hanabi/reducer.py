import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
from typing import List, Dict, Any
import json
import time
import logging
import argparse
import sys
import os
from tqdm import tqdm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AlertReducer:
    """告警消减模块"""

    def __init__(self, model_endpoint: str = None, api_key: str = None):
        self.model_endpoint = model_endpoint
        self.api_key = api_key
        self.original_alerts = self.processed_alerts = self.cluster_results = self.threat_scores = None
        self.time_stats = dict.fromkeys(['data_loading', 'data_preprocessing', 'embedding_generation',
                                        'clustering', 'threat_scoring', 'alert_reduction',
                                        'report_generation', 'result_saving', 'total_processing'], 0)

    def _record_time(self, operation: str, start_time: float):
        elapsed_time = time.time() - start_time
        self.time_stats[operation] = elapsed_time
        logger.info(f"{operation} 耗时: {elapsed_time:.3f} 秒")

    def load_alerts(self, csv_file_path: str) -> pd.DataFrame:
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
        # 验证必需字段是否存在
        required_fields = ['异常事件序号', '异常属性名', '异常属性值', '异常频次',
                          '进程名', '事件类型', '事件详情', '完整日志']
        missing_fields = [field for field in required_fields if field not in df.columns]
        if missing_fields:
            raise ValueError(f"缺少必需字段: {missing_fields}")

        # 填充缺失值
        df = df.fillna('')

        # 处理时间字段
        if '日志时间' in df.columns:
            df['日志时间'] = pd.to_datetime(df['日志时间'], errors='coerce')

        # 确保异常频次为数值型
        df['异常频次'] = pd.to_numeric(df['异常频次'], errors='coerce').fillna(0)

        # 确保异常事件序号为数值型
        df['异常事件序号'] = pd.to_numeric(df['异常事件序号'], errors='coerce').fillna(0)

        tqdm.pandas(desc="生成告警特征")
        # 优化：加入进程名，并对关键字段进行加权
        # Weight adjustment: 
        # - Attribute Name/Value: x5
        # - Process/Event Type: x10
        df['告警内容'] = df.progress_apply(
            lambda x: f"{x['异常属性名']} " * 5 + 
                      f"{x['异常属性值']} " * 5 + 
                      f"{x['进程名']} " * 10 + 
                      f"{x['事件类型']} " * 10 + 
                      f"{x['事件详情']}", 
            axis=1
        )

        tqdm.pandas(desc="生成威胁特征")
        df['威胁特征'] = df.progress_apply(lambda x: f"进程:{x['进程名']} 事件:{x['事件类型']} 详情:{x['事件详情']} 频次:{x['异常频次']}", axis=1)

        logger.info("数据预处理完成")
        return df

    def get_embeddings(self, texts: List[str]) -> np.ndarray:
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
        vectorizer = TfidfVectorizer(max_features=512, stop_words=None)
        try:
            with tqdm(total=2, desc="向量化处理") as pbar:
                pbar.set_description("拟合向量化器")
                embeddings = vectorizer.fit_transform(texts).toarray().astype(np.float32)
                pbar.update(2)
        except:
            embeddings = np.random.rand(len(texts), 512).astype(np.float32)
        return embeddings

    def _fallback_embeddings(self, texts: List[str]) -> np.ndarray:
        embeddings = []
        for text in tqdm(texts, desc="生成备用特征向量"):
            features = [len(text), text.count('error'), text.count('warning'), text.count('failed'),
                       text.count('exception'), len(set(text.lower())), text.count('.')]
            features.extend([0] * (512 - len(features)))
            embeddings.append(features[:512])
        return np.array(embeddings, dtype=np.float32)

    def cluster_alerts(self, df: pd.DataFrame, similarity_threshold: float = 0.8) -> Dict[str, Any]:
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
        n = similarity_matrix.shape[0]
        clusters = list(range(n))

        with tqdm(total=n*(n-1)//2, desc="合并相似告警") as pbar:
            for i in range(n):
                for j in range(i + 1, n):
                    if similarity_matrix[i, j] >= threshold:
                        old_cluster, new_cluster = clusters[j], clusters[i]
                        clusters = [new_cluster if c == old_cluster else c for c in clusters]
                    pbar.update(1)

        unique_clusters = list(set(clusters))
        cluster_mapping = {old: new for new, old in enumerate(unique_clusters)}
        return [cluster_mapping[c] for c in clusters]

    def _select_cluster_representatives(self, df: pd.DataFrame, clusters: List[int],
                                     similarity_matrix: np.ndarray) -> Dict[int, int]:
        representatives = {}
        df_with_clusters = df.copy()
        df_with_clusters['cluster'] = clusters

        for cluster_id in tqdm(set(clusters), desc="选择簇代表"):
            cluster_indices = df_with_clusters[df_with_clusters['cluster'] == cluster_id].index.tolist()

            if len(cluster_indices) == 1:
                representatives[cluster_id] = cluster_indices[0]
            else:
                best_idx = max(cluster_indices, key=lambda idx: np.mean([similarity_matrix[idx, other_idx]
                                                                        for other_idx in cluster_indices if other_idx != idx]))
                representatives[cluster_id] = best_idx

        return representatives

    def score_threats(self, df: pd.DataFrame) -> np.ndarray:
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
        high_risk_events = ['error', 'exception', 'failed', 'deny', 'block', 'attack']
        critical_processes = ['system', 'kernel', 'service', 'daemon']
        security_keywords = ['attack', 'intrusion', 'malware', 'virus', 'exploit', 'breach']

        scores = []
        for _, row in tqdm(df.iterrows(), total=len(df), desc="计算威胁分数"):
            score = 50
            frequency = row['异常频次']
            score += 30 if frequency > 100 else (20 if frequency > 50 else (10 if frequency > 10 else 0))

            event_type = str(row['事件类型']).lower()
            score += 25 if any(risk_word in event_type for risk_word in high_risk_events) else 0

            process_name = str(row['进程名']).lower()
            score += 15 if any(proc in process_name for proc in critical_processes) else 0

            event_detail = str(row['事件详情']).lower()
            score += sum(10 for keyword in security_keywords if keyword in event_detail)

            scores.append(max(0, min(100, score)))

        return np.array(scores)

    def _rule_based_scoring(self, df: pd.DataFrame) -> np.ndarray:
        return np.array([30 + np.random.randint(0, 40) for _ in tqdm(range(len(df)), desc="规则评分")])

    def reduce_alerts(self, df: pd.DataFrame, cluster_reduction: bool = True,
                     threat_threshold: float = 60.0, max_alerts_per_cluster: int = 3, similarity_threshold: float = 0.8) -> pd.DataFrame:
        start_time = time.time()
        print("\n" + "="*60)
        print("开始告警消减流程")
        print("="*60)

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

    def generate_report(self) -> Dict[str, Any]:
        start_time = time.time()

        if self.original_alerts is None or self.processed_alerts is None:
            raise ValueError("请先执行告警消减流程")

        original_count, reduced_count = len(self.original_alerts), len(self.processed_alerts)
        reduction_rate = (original_count - reduced_count) / original_count * 100

        report = {
            'summary': {
                'original_alerts': original_count, 'reduced_alerts': reduced_count,
                'reduction_count': original_count - reduced_count, 'reduction_rate': f"{reduction_rate:.2f}%"
            },
            'cluster_info': {}, 'threat_distribution': {}, 'top_threats': [],
            'performance_stats': self._generate_performance_stats()
        }

        # 聚类信息
        if self.cluster_results:
            report['cluster_info'] = {
                'total_clusters': self.cluster_results['cluster_count'],
                'avg_alerts_per_cluster': original_count / self.cluster_results['cluster_count'],
                'reduction_by_clustering': f"{(1 - self.cluster_results['cluster_count'] / original_count) * 100:.2f}%"
            }

        # 威胁分布
        if self.threat_scores is not None:
            threat_bins = [0, 30, 50, 70, 90, 100]
            threat_labels = ['低威胁(0-30)', '中低威胁(30-50)', '中威胁(50-70)', '高威胁(70-90)', '极高威胁(90-100)']

            threat_distribution = {}
            for i, label in enumerate(threat_labels):
                count = np.sum((self.threat_scores >= threat_bins[i]) &
                             (self.threat_scores < threat_bins[i+1]) if i < len(threat_bins) - 1
                             else self.threat_scores >= threat_bins[i])
                threat_distribution[label] = int(count)
            report['threat_distribution'] = threat_distribution

        # 高威胁告警Top 10
        if len(self.processed_alerts) > 0:
            report['top_threats'] = [{
                'threat_score': row['threat_score'], 'event_type': row['事件类型'],
                'process_name': row['进程名'], 'frequency': row['异常频次'],
                'alert_content': row['告警内容'][:100] + ('...' if len(row['告警内容']) > 100 else '')
            } for _, row in self.processed_alerts.head(10).iterrows()]

        self._record_time('report_generation', start_time)
        return report

    def _generate_performance_stats(self) -> Dict[str, Any]:
        total_time = sum(v for k, v in self.time_stats.items() if k != 'total_processing')
        self.time_stats['total_processing'] = total_time

        original_count = len(self.original_alerts) if self.original_alerts is not None else 0
        reduced_count = len(self.processed_alerts) if self.processed_alerts is not None else 0

        return {
            'time_breakdown': {
                '数据加载': f"{self.time_stats['data_loading']:.3f}s", '数据预处理': f"{self.time_stats['data_preprocessing']:.3f}s",
                '嵌入向量生成': f"{self.time_stats['embedding_generation']:.3f}s", '聚类处理': f"{self.time_stats['clustering']:.3f}s",
                '威胁评分': f"{self.time_stats['threat_scoring']:.3f}s", '告警消减': f"{self.time_stats['alert_reduction']:.3f}s",
                '报告生成': f"{self.time_stats['report_generation']:.3f}s", '结果保存': f"{self.time_stats['result_saving']:.3f}s",
                '总耗时': f"{total_time:.3f}s"
            },
            'processing_speed': {
                '原始告警处理速度': f"{original_count / total_time:.1f} 条/秒" if total_time > 0 else "N/A",
                '消减后告警生成速度': f"{reduced_count / total_time:.1f} 条/秒" if total_time > 0 else "N/A",
                '平均每条告警处理时间': f"{total_time / original_count * 1000:.2f} 毫秒" if original_count > 0 else "N/A"
            },
            'efficiency_metrics': {
                '最耗时操作': max(self.time_stats.items(), key=lambda x: x[1])[0] if self.time_stats else "N/A",
                '最耗时操作时间': f"{max(self.time_stats.values()):.3f}s" if self.time_stats else "N/A",
                '聚类效率': f"{self.cluster_results['cluster_count'] / self.time_stats['clustering']:.1f} 簇/秒" if self.cluster_results and self.time_stats['clustering'] > 0 else "N/A",
                '评分效率': f"{original_count / self.time_stats['threat_scoring']:.1f} 条/秒" if original_count > 0 and self.time_stats['threat_scoring'] > 0 else "N/A"
            }
        }

    def save_results(self, output_path: str = 'reduced_alerts.csv'):
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


def main():
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description='告警消减系统 - 对告警数据进行聚类和威胁评分')
    parser.add_argument('alerts_file',
                       help='告警数据CSV文件路径')
    parser.add_argument('-t', '--threshold',
                       type=float,
                       default=60.0,
                       help='威胁分数阈值 (默认: 60.0)')
    parser.add_argument('-m', '--max-per-cluster',
                       type=int,
                       default=3,
                       help='每个聚类最大告警数量 (默认: 3)')
    parser.add_argument('-s', '--similarity',
                       type=float,
                       default=0.8,
                       help='聚类相似度阈值 (默认: 0.8)')
    parser.add_argument('--no-cluster',
                       action='store_true',
                       help='禁用聚类，仅进行威胁评分')
    parser.add_argument('-v', '--verbose',
                       action='store_true',
                       help='显示详细处理信息')

    # 解析命令行参数
    args = parser.parse_args()
    alerts_file = args.alerts_file

    # 检查告警文件是否存在
    if not os.path.exists(alerts_file):
        print(f"错误: 告警文件 '{alerts_file}' 不存在", file=sys.stderr)
        return False

    # 检查文件是否可读
    if not os.access(alerts_file, os.R_OK):
        print(f"错误: 告警文件 '{alerts_file}' 无法读取", file=sys.stderr)
        return False

    reducer = AlertReducer()

    try:
        print(f"开始处理告警文件: {alerts_file}")
        alerts_df = reducer.load_alerts(alerts_file)
        print(f"原始告警数据：{len(alerts_df)} 条")

        reduced_alerts = reducer.reduce_alerts(
            alerts_df,
            cluster_reduction=not args.no_cluster,
            threat_threshold=args.threshold,
            max_alerts_per_cluster=args.max_per_cluster
        )
        print(f"消减后告警数据：{len(reduced_alerts)} 条")

        report = reducer.generate_report()

        if args.verbose:
            perf_stats = report['performance_stats']
            print(f"\n" + "="*80 + "\n性能统计报告\n" + "="*80)

            print("时间开销分解:")
            for operation, time_cost in perf_stats['time_breakdown'].items():
                print(f"  {operation}: {time_cost}")

            print(f"\n处理速度:")
            for metric, value in perf_stats['processing_speed'].items():
                print(f"  {metric}: {value}")

            print(f"\n效率指标:")
            for metric, value in perf_stats['efficiency_metrics'].items():
                print(f"  {metric}: {value}")

        # 构建输出文件路径（与输入文件同级目录）
        alerts_dir = os.path.dirname(alerts_file)
        alerts_basename = os.path.splitext(os.path.basename(alerts_file))[0]
        output_path = os.path.join(alerts_dir, f"{alerts_basename}_reduced.csv")

        reducer.save_results(output_path)

        # 输出文件路径
        report_path = output_path.replace('.csv', '_report.json')
        print(f"\n结果已保存:")
        print(f"  - 消减告警: {output_path}")
        print(f"  - 详细报告: {report_path}")

        return True

    except Exception as e:
        logger.error(f"告警消减处理失败: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return False


if __name__ == "__main__":
    main()
