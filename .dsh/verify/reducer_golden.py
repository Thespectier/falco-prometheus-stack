"""hanabi/reducer.py 黄金输出验证。

需要用带依赖的解释器运行：`.dsh/verify/venv/Scripts/python.exe`（pandas / numpy /
scikit-learn / tqdm 已装在 .dsh/verify/venv 里）。

确定性处理：
  * `time.time` 换成可控时钟（默认不推进，报告里的耗时字符串固定为 0.000s；
    需要覆盖"有耗时"分支的场景再打开步进）
  * `tqdm` 换成桩件：保留 `tqdm.pandas()` 对 `progress_apply` 的挂载（计算照旧），
    去掉进度条输出
  * `numpy.random` 在使用随机数的场景前固定种子

被验证的内容：预处理、TF-IDF 嵌入与备用嵌入、相似度聚类、簇代表选择、威胁评分、
完整消减流程（聚类 / 非聚类 / 过滤后为空）、报告与性能统计、结果落盘、CSV 加载、
以及命令行入口的各条分支。

运行：.dsh/verify/venv/Scripts/python.exe .dsh/verify/reducer_golden.py <输出文件>
"""

import contextlib
import io
import json
import logging
import os
import shutil
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TMP = os.path.join(HERE, "tmp", "reducer")
sys.path.insert(0, ROOT)

shutil.rmtree(TMP, ignore_errors=True)
os.makedirs(TMP, exist_ok=True)

# ------------------------------------------------------------------ 可控时钟
CLOCK = {"base": 1700000000.0, "step": 0.0, "calls": 0, "sleeps": []}


def fake_time():
    CLOCK["calls"] += 1
    return CLOCK["base"] + CLOCK["calls"] * CLOCK["step"]


def fake_sleep(seconds):
    CLOCK["sleeps"].append(seconds)


import time as time_module  # noqa: E402

time_module.time = fake_time
time_module.sleep = fake_sleep


# --------------------------------------------------------------------- tqdm 桩
class StubTqdm:
    """只保留进度条背后的计算，不产生任何输出。"""

    def __init__(self, iterable=None, total=None, desc=None, unit=None, leave=None, **kwargs):
        self.iterable = iterable

    def __iter__(self):
        return iter(self.iterable) if self.iterable is not None else iter(())

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def update(self, n=1):
        return None

    def set_description(self, *args, **kwargs):
        return None

    @staticmethod
    def pandas(*args, **kwargs):
        import pandas as pd

        pd.DataFrame.progress_apply = pd.DataFrame.apply
        pd.Series.progress_apply = pd.Series.apply


tqdm_module = types.ModuleType("tqdm")
tqdm_module.tqdm = StubTqdm
sys.modules["tqdm"] = tqdm_module

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

CALLS = []
LOG_RECORDS = []


def record(call, **payload):
    CALLS.append({"call": call, **payload})


class _CaptureHandler(logging.Handler):
    def emit(self, record):
        LOG_RECORDS.append({"logger": record.name, "level": record.levelname, "message": record.getMessage()})


logging.getLogger().addHandler(_CaptureHandler())
logging.getLogger().setLevel(logging.DEBUG)

import hanabi.reducer as reducer_module  # noqa: E402

AlertReducer = reducer_module.AlertReducer

REQUIRED_ROW = {
    "异常事件序号": 0,
    "异常属性名": "evt.type not matched",
    "异常属性值": "openat",
    "异常频次": 5,
    "进程名": "bash",
    "事件类型": "openat",
    "事件详情": "打开 /etc/passwd",
    "完整日志": "log-0",
    "日志时间": "2024-04-30T10:00:00+08:00",
}


def base_frame():
    """覆盖威胁评分各分支的样本：频次四档、高危事件词、关键进程、安全关键词。"""
    rows = [
        dict(REQUIRED_ROW),
        {
            "异常事件序号": 1, "异常属性名": "proc.name not matched", "异常属性值": "curl",
            "异常频次": 120, "进程名": "systemd", "事件类型": "connect",
            "事件详情": "连接到 10.0.0.1:443", "完整日志": "log-1", "日志时间": "2024-04-30T10:01:00+08:00",
        },
        {
            "异常事件序号": 2, "异常属性名": "network attribute not matched", "异常属性值": "8.8.8.8:53",
            "异常频次": 60, "进程名": "kworker", "事件类型": "sendto",
            "事件详情": "疑似 malware 外联 attack", "完整日志": "log-2", "日志时间": "2024-04-30T10:02:00+08:00",
        },
        {
            "异常事件序号": 3, "异常属性名": "directory not matched", "异常属性值": "/root",
            "异常频次": 20, "进程名": "bash", "事件类型": "openat",
            "事件详情": "exception while opening", "完整日志": "log-3", "日志时间": "",
        },
        {
            "异常事件序号": 4, "异常属性名": "", "异常属性值": "",
            "异常频次": None, "进程名": "", "事件类型": "prctl",
            "事件详情": "", "完整日志": "", "日志时间": "不是时间",
        },
        {
            "异常事件序号": 5, "异常属性名": "filename not matched", "异常属性值": "shadow",
            "异常频次": 1, "进程名": "sshd", "事件类型": "open",
            "事件详情": "读取 /etc/shadow", "完整日志": "log-5", "日志时间": "2024-04-30T10:05:00+08:00",
        },
    ]
    return pd.DataFrame(rows)


def frame_records(df):
    """把 DataFrame 转成可比较的结构（列顺序 + 逐行值）。"""
    return {
        "columns": list(df.columns),
        "rows": json.loads(df.to_json(orient="records", force_ascii=False, date_format="iso")),
    }


RESULTS = []


def jsonable(value):
    if isinstance(value, pd.DataFrame):
        return frame_records(value)
    if isinstance(value, np.ndarray):
        return {"shape": list(value.shape), "values": np.round(value.astype(float), 6).tolist()}
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, BaseException):
        return "%s: %s" % (type(value).__name__, value)
    return value


def scenario(name, fn, tick=0.0):
    CALLS.clear()
    LOG_RECORDS.clear()
    CLOCK.update({"calls": 0, "step": tick, "sleeps": []})
    out, err = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            value = fn()
        error = None
    except BaseException as exc:
        value = None
        error = "%s: %s" % (type(exc).__name__, exc)
    RESULTS.append(
        {
            "case": name,
            "value": jsonable(value),
            "error": error,
            "stdout": out.getvalue(),
            "stderr": err.getvalue(),
            "calls": list(CALLS),
            "logs": list(LOG_RECORDS),
            "sleeps": list(CLOCK["sleeps"]),
        }
    )


def run():
    # ----------------------------------------------------------- 构造与预处理
    scenario("reducer.init_defaults", lambda: _init_state())

    def preprocess_ok():
        reducer = AlertReducer()
        df = reducer._preprocess_data(base_frame())
        return {
            "frame": frame_records(df)[ "rows"],
            "columns": list(df.columns),
            "frequency": df["异常频次"].tolist(),
            "sequence": df["异常事件序号"].tolist(),
            "time_is_null": bool(df["日志时间"].isna().sum()),
        }

    scenario("reducer.preprocess_ok", preprocess_ok)

    def preprocess_missing():
        reducer = AlertReducer()
        return reducer._preprocess_data(pd.DataFrame([{"异常事件序号": 0}]))

    scenario("reducer.preprocess_missing_fields", preprocess_missing)

    # ------------------------------------------------------------- 嵌入向量
    def embeddings_tfidf():
        reducer = AlertReducer()
        texts = ["进程 bash 打开文件", "进程 curl 建立连接", "进程 bash 打开文件"]
        return {"embeddings": reducer.get_embeddings(texts), "time_stats": dict(reducer.time_stats)}

    scenario("reducer.embeddings_tfidf", embeddings_tfidf)

    def embeddings_fallback():
        reducer = AlertReducer()
        return reducer._fallback_embeddings(["error failed", "warning", ""])

    scenario("reducer.embeddings_fallback", embeddings_fallback)

    # ---------------------------------------------------------------- 聚类
    def clustering():
        matrix = np.array(
            [
                [1.0, 0.9, 0.1, 0.1],
                [0.9, 1.0, 0.1, 0.2],
                [0.1, 0.1, 1.0, 0.95],
                [0.1, 0.2, 0.95, 1.0],
            ]
        )
        reducer = AlertReducer()
        return {
            "threshold_0_8": reducer._similarity_clustering(matrix, 0.8),
            "threshold_0_95": reducer._similarity_clustering(matrix, 0.95),
            "threshold_1_0": reducer._similarity_clustering(matrix, 1.0),
        }

    scenario("reducer.similarity_clustering", clustering)

    def representatives():
        matrix = np.array(
            [
                [1.0, 0.9, 0.8, 0.1],
                [0.9, 1.0, 0.85, 0.1],
                [0.8, 0.85, 1.0, 0.1],
                [0.1, 0.1, 0.1, 1.0],
            ]
        )
        reducer = AlertReducer()
        df = pd.DataFrame({"异常内容": ["a", "b", "c", "d"]})
        return reducer._select_cluster_representatives(df, [0, 0, 0, 1], matrix)

    scenario("reducer.select_representatives", representatives)

    def cluster_alerts():
        reducer = AlertReducer()
        df = reducer._preprocess_data(base_frame())
        result = reducer.cluster_alerts(df, similarity_threshold=0.6)
        return {
            "clusters": result["clusters"],
            "cluster_count": result["cluster_count"],
            "original_count": result["original_count"],
            "representatives": result["representatives"],
            "embedding_shape": list(result["embeddings"].shape),
        }

    scenario("reducer.cluster_alerts", cluster_alerts)

    # ------------------------------------------------------------- 威胁评分
    def threat_scoring():
        reducer = AlertReducer()
        df = reducer._preprocess_data(base_frame())
        return {"scores": reducer._simulate_threat_scoring(df)}

    scenario("reducer.threat_scoring", threat_scoring)

    def rule_based():
        np.random.seed(42)
        reducer = AlertReducer()
        df = reducer._preprocess_data(base_frame())
        return {"scores": reducer._rule_based_scoring(df)}

    scenario("reducer.rule_based_scoring", rule_based)

    def score_threats_fallback():
        reducer = AlertReducer()
        df = reducer._preprocess_data(base_frame())

        def explode(_df):
            raise RuntimeError("scoring backend down")

        reducer._simulate_threat_scoring = explode
        np.random.seed(7)
        return {"scores": reducer.score_threats(df)}

    scenario("reducer.score_threats_fallback", score_threats_fallback)

    # --------------------------------------------------------- 完整消减流程
    def reduce_clustered():
        reducer = AlertReducer()
        df = reducer._preprocess_data(base_frame())
        reduced = reducer.reduce_alerts(
            df, cluster_reduction=True, threat_threshold=60.0,
            max_alerts_per_cluster=1, similarity_threshold=0.6,
        )
        return {
            "reduced": frame_records(reduced),
            "processed_alerts_is_same": reducer.processed_alerts is reduced,
            "original_rows": len(reducer.original_alerts) if reducer.original_alerts is not None else None,
        }

    def reduce_no_cluster():
        reducer = AlertReducer()
        df = reducer._preprocess_data(base_frame())
        reduced = reducer.reduce_alerts(
            df, cluster_reduction=False, threat_threshold=50.0,
            max_alerts_per_cluster=2, similarity_threshold=0.6,
        )
        return {"reduced": frame_records(reduced)}

    def reduce_all_filtered():
        reducer = AlertReducer()
        df = reducer._preprocess_data(base_frame())
        reduced = reducer.reduce_alerts(
            df, cluster_reduction=True, threat_threshold=500.0,
            max_alerts_per_cluster=1, similarity_threshold=0.6,
        )
        return {"reduced": frame_records(reduced), "columns": list(reduced.columns)}

    scenario("reducer.reduce_clustered", reduce_clustered)
    scenario("reducer.reduce_no_cluster", reduce_no_cluster)
    scenario("reducer.reduce_all_filtered", reduce_all_filtered)

    # --------------------------------------------------------------- 报告
    def report_before_reduce():
        reducer = AlertReducer()
        return reducer.generate_report()

    scenario("reducer.report_before_reduce", report_before_reduce)

    def build_reduced(tick=0.0):
        reducer = AlertReducer()
        df = reducer.load_alerts(_write_csv())
        reducer.reduce_alerts(df, cluster_reduction=True, threat_threshold=60.0,
                              max_alerts_per_cluster=1, similarity_threshold=0.6)
        return reducer

    def report_after():
        return build_reduced().generate_report()

    scenario("reducer.report_after_zero_time", report_after)
    scenario("reducer.report_after_ticking_time", report_after, tick=0.5)

    def performance_stats():
        return build_reduced()._generate_performance_stats()

    scenario("reducer.performance_stats", performance_stats, tick=0.5)

    # --------------------------------------------------------------- 落盘
    def save_results():
        reducer = build_reduced()
        output_path = os.path.join(TMP, "saved_reduced.csv")
        reducer.save_results(output_path)
        report_path = output_path.replace('.csv', '_report.json')
        with open(output_path, encoding="utf-8") as handle:
            csv_text = handle.read()
        with open(report_path, encoding="utf-8") as handle:
            report = json.load(handle)
        return {
            "csv_lines": csv_text.splitlines(),
            "report_keys": sorted(report),
            "report_summary": report["summary"],
            "cluster_info": report["cluster_info"],
            "threat_distribution": report["threat_distribution"],
        }

    scenario("reducer.save_results", save_results)

    def save_without_reduce():
        return AlertReducer().save_results(os.path.join(TMP, "nothing.csv"))

    scenario("reducer.save_without_reduce", save_without_reduce)

    def load_alerts_ok():
        reducer = AlertReducer()
        df = reducer.load_alerts(_write_csv())
        return {
            "columns": list(df.columns),
            "rows": len(df),
            "original_is_df": isinstance(reducer.original_alerts, pd.DataFrame),
            "time_stats": dict(reducer.time_stats),
        }

    scenario("reducer.load_alerts", load_alerts_ok)

    def load_alerts_bad():
        reducer = AlertReducer()
        return reducer.load_alerts(os.path.join(TMP, "missing.csv"))

    scenario("reducer.load_alerts_missing", load_alerts_bad)

    # ------------------------------------------------------------- 命令行
    def cli_missing_file():
        argv = sys.argv
        sys.argv = ["reducer", os.path.join(TMP, "nope.csv")]
        try:
            return reducer_module.main()
        finally:
            sys.argv = argv

    def cli_success(extra=None):
        argv = sys.argv
        sys.argv = ["reducer", _write_csv("cli_in.csv")] + (extra or [])
        try:
            return {
                "returned": reducer_module.main(),
                "files": sorted(os.listdir(TMP)),
            }
        finally:
            sys.argv = argv

    def cli_verbose():
        return cli_success(["-v", "-t", "50", "-m", "2", "-s", "0.5"])

    def cli_no_cluster():
        return cli_success(["--no-cluster"])

    scenario("reducer.cli_missing_file", cli_missing_file)
    scenario("reducer.cli_success", cli_success)
    scenario("reducer.cli_verbose", cli_verbose)
    scenario("reducer.cli_no_cluster", cli_no_cluster)

    payload = json.dumps(RESULTS, ensure_ascii=False, indent=2)
    if len(sys.argv) > 1:
        with open(sys.argv[1], "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload + "\n")
    else:
        print(payload)


def _init_state():
    reducer = AlertReducer()
    return {
        "model_endpoint": reducer.model_endpoint,
        "api_key": reducer.api_key,
        "original_alerts": reducer.original_alerts,
        "processed_alerts": reducer.processed_alerts,
        "cluster_results": reducer.cluster_results,
        "threat_scores": reducer.threat_scores,
        "time_stats_keys": sorted(reducer.time_stats),
        "time_stats_values": sorted(set(reducer.time_stats.values())),
    }


def _write_csv(name="alerts.csv"):
    path = os.path.join(TMP, name)
    base_frame().to_csv(path, index=False, encoding="utf-8")
    return path


run()
