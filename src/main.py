"""
K8s Healing Agent — FastAPI 入口
接收 Prometheus AlertManager Webhook，编排自愈流程
"""

from fastapi import FastAPI
from datetime import datetime

app = FastAPI(
    title="K8s Healing Agent",
    description="AI-driven Kubernetes self-healing agent",
    version="0.1.0",
)


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return {"status": "not yet implemented"}  # TODO


@app.post("/webhook/alertmanager")
async def handle_alert():
    """AlertManager Webhook entry point"""
    return {"status": "not yet implemented"}  # TODO
