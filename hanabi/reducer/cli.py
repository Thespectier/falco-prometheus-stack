"""命令行入口：对离线导出的告警 CSV 跑一遍消减并落盘。

用法：`python -m hanabi.reducer <告警CSV> [-t 阈值] [-m 每簇上限] [-s 相似度] [--no-cluster] [-v]`

输出文件与输入文件同级：`<名称>_reduced.csv` 与 `<名称>_reduced_report.json`。
"""

import argparse
import logging
import os
import sys

from ._logging import logger
from .pipeline import AlertReducer


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
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
    return parser


def _print_performance(report):
    """打印性能统计明细（-v 时才输出）。"""
    perf_stats = report['performance_stats']
    print(f"\n" + "=" * 80 + "\n性能统计报告\n" + "=" * 80)

    print("时间开销分解:")
    for operation, time_cost in perf_stats['time_breakdown'].items():
        print(f"  {operation}: {time_cost}")

    print(f"\n处理速度:")
    for metric, value in perf_stats['processing_speed'].items():
        print(f"  {metric}: {value}")

    print(f"\n效率指标:")
    for metric, value in perf_stats['efficiency_metrics'].items():
        print(f"  {metric}: {value}")


def main():
    """执行一次离线消减；成功返回 True，参数或处理失败返回 False。"""
    args = build_parser().parse_args()
    alerts_file = args.alerts_file

    if not os.path.exists(alerts_file):
        print(f"错误: 告警文件 '{alerts_file}' 不存在", file=sys.stderr)
        return False

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
            _print_performance(report)

        # 输出文件放在输入文件同级目录
        alerts_dir = os.path.dirname(alerts_file)
        alerts_basename = os.path.splitext(os.path.basename(alerts_file))[0]
        output_path = os.path.join(alerts_dir, f"{alerts_basename}_reduced.csv")

        reducer.save_results(output_path)

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
