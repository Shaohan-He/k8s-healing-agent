"""诊断数据模型"""
from pydantic import BaseModel
from typing import Optional
from dataclasses import dataclass, field


class ContainerStatus:
    name: str = ""
    state: str = ""
    reason: str = ""
    exit_code: Optional[int] = None
    restart_count: int = 0


class K8sEvent:
    type: str = ""
    reason: str = ""
    message: str = ""
    timestamp: str = ""


class NodeCondition:
    type: str = ""
    status: str = ""
    reason: str = ""


@dataclass
class DiagnosisReport:
    # Pod 层
    pod_name: str = ""
    namespace: str = ""
    phase: str = ""  # Running | Pending | Failed
    container_statuses: list[ContainerStatus] = field(default_factory=list)
    restart_count: int = 0
    node_name: str = ""

    # 事件层
    recent_events: list[K8sEvent] = field(default_factory=list)

    # 日志层
    previous_logs: str = ""
    current_logs: str = ""

    # 资源层
    resource_limits: dict = field(default_factory=dict)
    resource_requests: dict = field(default_factory=dict)
    node_conditions: list[NodeCondition] = field(default_factory=list)

    # 上下文
    owner_kind: str = ""   # Deployment | StatefulSet | DaemonSet | Job
    owner_name: str = ""
    service_account: str = ""
    image_pull_secrets: list[str] = field(default_factory=list)
