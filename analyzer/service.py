"""安全事件分析服务：轮询未分析的事件，交给大模型补一段中文结论。

大模型配置优先取数据库里的运行期配置，其次取环境变量——前端"设置"页写的就是数据库
那一份，容器重启后仍然生效。分析结果回填到 incidents.analysis，前端据此展示。
"""

import logging
import os
import time

from openai import OpenAI

from api.app.services.log_storage import log_storage

DEFAULT_ENDPOINT = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"

# 没有新事件时的轮询间隔
POLL_INTERVAL = int(os.getenv("ANALYZER_POLL_INTERVAL", "10"))

# 配置项的取值顺序：数据库键 == 环境变量名
_LLM_SETTINGS = (
    ("DEEPSEEK_API_KEY", ""),
    ("DEEPSEEK_ENDPOINT", DEFAULT_ENDPOINT),
    ("DEEPSEEK_MODEL", DEFAULT_MODEL),
)

# 每轮最多分析多少条、回看多长时间（秒）
_MAX_INCIDENTS_PER_ROUND = 50
_LOOKBACK_SECONDS = 3600

# 未配置 key 时的等待时间：配置好之后无需重启容器
_NO_KEY_PAUSE_SECONDS = 60

# 单条事件分析之间的间隔，避免触发模型侧速率限制
_RATE_LIMIT_PAUSE_SECONDS = 1

# 启动时等数据库就绪
_STARTUP_DELAY_SECONDS = 30

_SYSTEM_PROMPT = "You are a cybersecurity expert specializing in container security."

_PROMPT_TEMPLATE = """
        你是一个云原生安全专家。请分析以下Falco安全事件，并用简洁的中文给出分析结果。
        
        **事件上下文**:
        - 进程名: {process_name}
        - 事件类型: {event_type}
        - 威胁评分: {threat_score}
        - 异常属性: {attribute_name} ({attribute_value})
        - 详细日志: {details}
        
        **请回答**:
        1. **风险分析**: 这个行为为什么危险？可能是哪种攻击？
        
        请保持回答在50字以内，重点突出。
        """

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AnalyzerService")


def get_llm_settings():
    """取大模型配置：数据库优先，其次环境变量。返回 (key, endpoint, model)。"""
    return tuple(
        log_storage.get_config(storage_key) or os.getenv(storage_key, default)
        for storage_key, default in _LLM_SETTINGS
    )


def analyze_incident(client: OpenAI, incident, model):
    """把事件上下文交给模型，返回一段中文结论；失败时返回固定提示。"""
    try:
        prompt = _PROMPT_TEMPLATE.format(
            process_name=incident["process_name"],
            event_type=incident["event_type"],
            threat_score=incident["threat_score"],
            attribute_name=incident["attribute_name"],
            attribute_value=incident["attribute_value"],
            details=incident["details"],
        )

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=500,
        )
        return response.choices[0].message.content
    except Exception as error:
        logger.error(f"LLM analysis failed: {error}")
        return "分析服务暂时不可用。"


def _analyze_pending_incidents(client: OpenAI, model: str) -> None:
    """取最近一段时间的事件，逐条补结论。

    过滤在内存里做：事件量本身很小（聚类后的结果），不值得为 analysis IS NULL 再开
    一个查询接口。
    """
    recent = log_storage.get_incidents(limit=_MAX_INCIDENTS_PER_ROUND, window_seconds=_LOOKBACK_SECONDS)
    pending = [incident for incident in recent if not incident.get("analysis")]

    if pending:
        logger.info(f"Found {len(pending)} pending incidents.")

    for incident in pending:
        logger.info(f"Analyzing incident {incident['id']} with model {model}...")
        analysis_result = analyze_incident(client, incident, model)
        log_storage.update_incident_analysis(incident["id"], analysis_result)
        logger.info(f"Incident {incident['id']} analyzed.")
        time.sleep(_RATE_LIMIT_PAUSE_SECONDS)


def run_loop():
    """主循环：取配置 → 建客户端 → 补结论 → 休眠。"""
    logger.info("Analyzer started.")

    while True:
        try:
            api_key, endpoint, model = get_llm_settings()

            if not api_key:
                logger.warning("DEEPSEEK_API_KEY not set in DB or env. Sleeping...")
                time.sleep(_NO_KEY_PAUSE_SECONDS)
                continue

            client = OpenAI(api_key=api_key, base_url=endpoint)
            _analyze_pending_incidents(client, model)

        except Exception as error:
            logger.error(f"Analyzer loop error: {error}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    # 等数据库就绪后再开始轮询
    time.sleep(_STARTUP_DELAY_SECONDS)
    run_loop()
