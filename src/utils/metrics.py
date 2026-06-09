"""
Prometheus 指标暴露 —— 监控 Agent 自身的运行状态
"""


class Metrics:
    """Prometheus 指标收集器"""

    def __init__(self):
        # TODO: Initialize prometheus_client counters/gauges
        pass

    def record_diagnosis(self, duration_s: float):
        pass

    def record_analysis(self, duration_s: float):
        pass

    def record_decision(self, decision: str):
        pass

    def record_healing(self, duration_s: float, success: bool):
        pass

    def record_verification(self, success: bool):
        pass

    def record_error(self, error_type: str):
        pass

    def get_latest(self) -> str:
        """返回最新指标（Prometheus text format）"""
        return ""
