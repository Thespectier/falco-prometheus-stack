import os
import time
import logging
from openai import OpenAI
from api.app.services.log_storage import log_storage

# Configuration
DEFAULT_ENDPOINT = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"
POLL_INTERVAL = int(os.getenv("ANALYZER_POLL_INTERVAL", "10"))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AnalyzerService")

def get_llm_settings():
    """Fetch LLM settings from DB, falling back to env vars."""
    api_key = log_storage.get_config("DEEPSEEK_API_KEY") or os.getenv("DEEPSEEK_API_KEY", "")
    endpoint = log_storage.get_config("DEEPSEEK_ENDPOINT") or os.getenv("DEEPSEEK_ENDPOINT", DEFAULT_ENDPOINT)
    model = log_storage.get_config("DEEPSEEK_MODEL") or os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL)
    return api_key, endpoint, model

def analyze_incident(client: OpenAI, incident, model):
    """Send incident details to LLM for analysis."""
    try:
        # Construct a detailed prompt
        prompt = f"""
        你是一个云原生安全专家。请分析以下Falco安全事件，并用简洁的中文给出分析结果。
        
        **事件上下文**:
        - 进程名: {incident['process_name']}
        - 事件类型: {incident['event_type']}
        - 威胁评分: {incident['threat_score']}
        - 异常属性: {incident['attribute_name']} ({incident['attribute_value']})
        - 详细日志: {incident['details']}
        
        **请回答**:
        1. **风险分析**: 这个行为为什么危险？可能是哪种攻击？
        
        请保持回答在50字以内，重点突出。
        """

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a cybersecurity expert specializing in container security."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"LLM analysis failed: {e}")
        return "分析服务暂时不可用。"

def run_loop():
    logger.info("Analyzer started.")

    while True:
        try:
            api_key, endpoint, model = get_llm_settings()
            
            if not api_key:
                logger.warning("DEEPSEEK_API_KEY not set in DB or env. Sleeping...")
                time.sleep(60)
                continue

            client = OpenAI(api_key=api_key, base_url=endpoint)
            
            # 1. Fetch recent incidents (last 1 hour) that have no analysis
            # Note: get_incidents returns a list of dicts. We filter locally for simplicity 
            # as adding complex filters to SQLite helper might be overkill for now.
            # Ideally, get_incidents should support 'analysis_is_null=True'
            all_incidents = log_storage.get_incidents(limit=50, window_seconds=3600)
            
            pending_incidents = [i for i in all_incidents if not i.get('analysis')]
            
            if pending_incidents:
                logger.info(f"Found {len(pending_incidents)} pending incidents.")
            
            for inc in pending_incidents:
                logger.info(f"Analyzing incident {inc['id']} with model {model}...")
                analysis_result = analyze_incident(client, inc, model)
                log_storage.update_incident_analysis(inc['id'], analysis_result)
                logger.info(f"Incident {inc['id']} analyzed.")
                time.sleep(1) # Rate limit protection
                
        except Exception as e:
            logger.error(f"Analyzer loop error: {e}")
        
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    # Wait for DB to be ready
    time.sleep(30) 
    run_loop()
