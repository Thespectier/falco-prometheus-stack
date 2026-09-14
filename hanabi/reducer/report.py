"""消减报告与性能统计。

报告是给人看的：消减前后条数、聚类概况、威胁分布、Top10 高威胁告警，以及各阶段耗时。
耗时字符串直接取自 time_stats，跨机器不可比，只用于定位本次运行的瓶颈。

`build_report` 的取值顺序与原实现保持一致（先算消减率、再算性能统计、最后拼各段），
因为性能统计会读写成时间统计表，顺序会影响异常路径下的中间状态。
"""

from typing import Any, Callable, Dict

import numpy as np
import pandas as pd

# 威胁分布的分箱与标签
_THREAT_BINS = [0, 30, 50, 70, 90, 100]
_THREAT_LABELS = ['低威胁(0-30)', '中低威胁(30-50)', '中威胁(50-70)', '高威胁(70-90)', '极高威胁(90-100)']

# TopN 高威胁告警
_TOP_THREATS = 10

# 报告里截断展示的告警内容长度
_CONTENT_PREVIEW = 100


def build_performance_stats(
    time_stats: Dict[str, float],
    original_count: int,
    reduced_count: int,
    cluster_results,
) -> Dict[str, Any]:
    """汇总各阶段耗时与吞吐；total_processing 会写回传入的 time_stats。"""
    total_time = sum(v for k, v in time_stats.items() if k != 'total_processing')
    time_stats['total_processing'] = total_time

    return {
        'time_breakdown': {
            '数据加载': f"{time_stats['data_loading']:.3f}s", '数据预处理': f"{time_stats['data_preprocessing']:.3f}s",
            '嵌入向量生成': f"{time_stats['embedding_generation']:.3f}s", '聚类处理': f"{time_stats['clustering']:.3f}s",
            '威胁评分': f"{time_stats['threat_scoring']:.3f}s", '告警消减': f"{time_stats['alert_reduction']:.3f}s",
            '报告生成': f"{time_stats['report_generation']:.3f}s", '结果保存': f"{time_stats['result_saving']:.3f}s",
            '总耗时': f"{total_time:.3f}s"
        },
        'processing_speed': {
            '原始告警处理速度': f"{original_count / total_time:.1f} 条/秒" if total_time > 0 else "N/A",
            '消减后告警生成速度': f"{reduced_count / total_time:.1f} 条/秒" if total_time > 0 else "N/A",
            '平均每条告警处理时间': f"{total_time / original_count * 1000:.2f} 毫秒" if original_count > 0 else "N/A"
        },
        'efficiency_metrics': {
            '最耗时操作': max(time_stats.items(), key=lambda x: x[1])[0] if time_stats else "N/A",
            '最耗时操作时间': f"{max(time_stats.values()):.3f}s" if time_stats else "N/A",
            '聚类效率': f"{cluster_results['cluster_count'] / time_stats['clustering']:.1f} 簇/秒" if cluster_results and time_stats['clustering'] > 0 else "N/A",
            '评分效率': f"{original_count / time_stats['threat_scoring']:.1f} 条/秒" if original_count > 0 and time_stats['threat_scoring'] > 0 else "N/A"
        }
    }


def _threat_distribution(threat_scores: np.ndarray) -> Dict[str, int]:
    """按分箱统计威胁分数分布；最后一箱只取上界。"""
    distribution = {}
    for index, label in enumerate(_THREAT_LABELS):
        if index < len(_THREAT_BINS) - 1:
            count = np.sum((threat_scores >= _THREAT_BINS[index]) & (threat_scores < _THREAT_BINS[index + 1]))
        else:
            count = np.sum(threat_scores >= _THREAT_BINS[index])
        distribution[label] = int(count)
    return distribution


def _top_threats(processed_alerts: pd.DataFrame) -> list:
    """取威胁分数最高的若干条，内容过长时截断后加省略号。"""
    return [
        {
            'threat_score': row['threat_score'], 'event_type': row['事件类型'],
            'process_name': row['进程名'], 'frequency': row['异常频次'],
            'alert_content': row['告警内容'][:_CONTENT_PREVIEW]
            + ('...' if len(row['告警内容']) > _CONTENT_PREVIEW else '')
        }
        for _, row in processed_alerts.head(_TOP_THREATS).iterrows()
    ]


def build_report(
    original_count: int,
    reduced_count: int,
    performance_stats_factory: Callable[[], Dict[str, Any]],
    cluster_results,
    threat_scores,
    processed_alerts: pd.DataFrame,
) -> Dict[str, Any]:
    """拼装完整报告。"""
    reduction_rate = (original_count - reduced_count) / original_count * 100

    report = {
        'summary': {
            'original_alerts': original_count, 'reduced_alerts': reduced_count,
            'reduction_count': original_count - reduced_count, 'reduction_rate': f"{reduction_rate:.2f}%"
        },
        'cluster_info': {}, 'threat_distribution': {}, 'top_threats': [],
        'performance_stats': performance_stats_factory()
    }

    if cluster_results:
        report['cluster_info'] = {
            'total_clusters': cluster_results['cluster_count'],
            'avg_alerts_per_cluster': original_count / cluster_results['cluster_count'],
            'reduction_by_clustering': f"{(1 - cluster_results['cluster_count'] / original_count) * 100:.2f}%"
        }

    if threat_scores is not None:
        report['threat_distribution'] = _threat_distribution(threat_scores)

    if len(processed_alerts) > 0:
        report['top_threats'] = _top_threats(processed_alerts)

    return report
