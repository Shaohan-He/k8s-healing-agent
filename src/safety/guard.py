"""
安全护栏 —— 五层防护模型的核心实现

Layer 2: Namespace 白名单
Layer 3: 动作白名单
Layer 4: 置信度门槛（在 decision engine 中实现）
"""

from src.models.alert import AlertPayload
from src.models.fix import FixPlan


class SafetyGuard:
    """Namespace + 动作白名单检查"""

    # 允许处理的 namespace
    ALLOWED_NAMESPACES = ["default", "staging", "production"]

    # 允许的修复动作及其约束
    ALLOWED_ACTIONS = {
        "memory": {
            "resource_types": ["deployments", "statefulsets"],
            "max_multiplier": 2.0,       # 内存最多翻倍
            "max_absolute": "4Gi",       # 单容器内存上限
        },
        "cpu": {
            "resource_types": ["deployments", "statefulsets"],
            "max_multiplier": 2.0,
            "max_absolute": "4",
        },
        "probe": {
            "allowed_fields": [
                "initialDelaySeconds",
                "periodSeconds",
                "failureThreshold",
            ],
            "min_initial_delay": 10,
            "max_failure_threshold": 10,
        },
    }

    def check(self, alert: AlertPayload, fix_plan: dict) -> tuple[bool, str]:
        """两层检查：namespace 白名单 + 动作白名单"""

        # Namespace 白名单
        if alert.namespace not in self.ALLOWED_NAMESPACES:
            return False, f"namespace {alert.namespace} 不在白名单中"

        # 动作白名单
        fix_type = fix_plan.get("fix_type", "unknown")
        if fix_type not in self.ALLOWED_ACTIONS:
            return False, f"fix_type {fix_type} 不在白名单中"

        return True, "安全检查通过"
