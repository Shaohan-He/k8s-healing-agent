"""
Prometheus 指标暴露 —— 监控 Agent 自身的运行状态
"""

from prometheus_client import Counter, Histogram, generate_latest, REGISTRY


class Metrics:
    """Prometheus 指标收集器"""

    def __init__(self):
        # ── Counters ─────────────────────────────────
        self.healings_total = Counter(
            "healing_agent_healings_total",
            "Total healing operations attempted",
            ["result"],  # success | failure
        )
        self.errors_total = Counter(
            "healing_agent_errors_total",
            "Total pipeline errors",
            ["error_type"],
        )
        self.decisions_total = Counter(
            "healing_agent_decisions_total",
            "Total decisions made",
            ["decision"],  # AUTO_EXEC | APPROVAL | ONLY_NOTIFY
        )
        self.alerts_received = Counter(
            "healing_agent_alerts_received_total",
            "Total AlertManager webhooks received",
        )
        self.alerts_deduped = Counter(
            "healing_agent_alerts_deduped_total",
            "Total alerts skipped due to dedup",
        )

        # ── Histograms ───────────────────────────────
        self.diagnosis_duration = Histogram(
            "healing_agent_diagnosis_duration_seconds",
            "Time spent collecting diagnosis data",
            buckets=[0.5, 1.0, 2.0, 3.0, 5.0, 10.0],
        )
        self.analysis_duration = Histogram(
            "healing_agent_analysis_duration_seconds",
            "Time spent waiting for Claude API",
            buckets=[1.0, 2.0, 5.0, 8.0, 15.0, 30.0],
        )
        self.healing_duration = Histogram(
            "healing_agent_healing_duration_seconds",
            "Time spent executing fixes",
            buckets=[0.5, 1.0, 2.0, 5.0, 10.0],
        )
        self.pipeline_duration = Histogram(
            "healing_agent_pipeline_duration_seconds",
            "Total pipeline execution time",
            buckets=[5.0, 10.0, 15.0, 30.0, 60.0],
        )

    # ── Recording methods ───────────────────────────

    def record_diagnosis(self, duration_s: float):
        self.diagnosis_duration.observe(duration_s)

    def record_analysis(self, duration_s: float):
        self.analysis_duration.observe(duration_s)

    def record_decision(self, decision: str):
        self.decisions_total.labels(decision=decision).inc()

    def record_healing(self, duration_s: float, success: bool):
        result = "success" if success else "failure"
        self.healings_total.labels(result=result).inc()
        self.healing_duration.observe(duration_s)

    def record_verification(self, success: bool):
        pass  # TODO: add verification counter if needed

    def record_error(self, error_type: str):
        self.errors_total.labels(error_type=error_type).inc()

    def record_alert_received(self):
        self.alerts_received.inc()

    def record_alert_deduped(self):
        self.alerts_deduped.inc()

    def record_pipeline(self, duration_s: float):
        self.pipeline_duration.observe(duration_s)

    def get_latest(self) -> str:
        """返回最新指标（Prometheus text format）"""
        return generate_latest(REGISTRY).decode("utf-8")
