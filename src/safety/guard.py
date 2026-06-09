"""
安全护栏 —— 五层防护模型的核心实现

Layer 2: Namespace 白名单
Layer 3: 动作白名单 + 资源限制校验
Layer 4: 置信度门槛（在 decision engine 中实现）
Layer 5: 人工兜底（在 main.py pipeline 中实现）
"""

import re
import logging

from src.models.alert import AlertPayload

logger = logging.getLogger(__name__)


class SafetyGuard:
    """Namespace + 动作白名单 + 资源限制校验"""

    # 允许处理的 namespace
    ALLOWED_NAMESPACES = ["default", "staging", "production"]

    # 允许的修复动作及其约束
    ALLOWED_ACTIONS: dict[str, dict] = {
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
        "config": {
            "resource_types": [
                "deployments", "statefulsets",
            ],
        },
        "image": {
            "resource_types": [
                "deployments", "statefulsets",
            ],
        },
    }

    def check(
        self, alert: AlertPayload, fix_plan: dict,
    ) -> tuple[bool, str]:
        """
        安全审查入口。
        1. Namespace 白名单
        2. 动作白名单
        3. 资源限制校验
        """

        # Layer 2: Namespace 白名单
        if alert.namespace not in self.ALLOWED_NAMESPACES:
            return False, (
                f"namespace '{alert.namespace}' 不在白名单中 "
                f"(允许: {', '.join(self.ALLOWED_NAMESPACES)})"
            )

        # Layer 3: 动作白名单
        fix_type = fix_plan.get("fix_type", "unknown")
        if fix_type not in self.ALLOWED_ACTIONS:
            return False, f"fix_type '{fix_type}' 不在白名单中"

        # 资源限制校验
        if fix_type in ("memory", "cpu"):
            ok, msg = self._enforce_resource_limits(
                alert, fix_plan, fix_type,
            )
            if not ok:
                return False, msg

        # Probe 参数校验
        if fix_type == "probe":
            ok, msg = self._validate_probe_params(fix_plan)
            if not ok:
                return False, msg

        return True, "安全检查通过"

    # ── 资源限制校验 ────────────────────────────────

    def _enforce_resource_limits(
        self, alert: AlertPayload, fix_plan: dict, resource_type: str,
    ) -> tuple[bool, str]:
        """
        校验内存/CPU 修改不超出限制。
        - 最多翻倍（max_multiplier）
        - 不超过绝对上限（max_absolute）
        """

        action_config = self.ALLOWED_ACTIONS.get(resource_type, {})
        max_multiplier = action_config.get("max_multiplier", 2.0)
        max_absolute = action_config.get("max_absolute", "")

        params = fix_plan.get("fix_params", {})
        key = (
            "new_memory_limit" if resource_type == "memory"
            else "new_cpu_limit"
        )
        new_value = params.get(key)
        if new_value is None:
            return True, ""  # 没有具体值就不校验

        # 解析为可比较的数值
        new_bytes = self._parse_resource(new_value)
        max_bytes = self._parse_resource(max_absolute)

        if max_bytes and new_bytes:
            if new_bytes > int(max_bytes * max_multiplier):
                return False, (
                    f"资源修改超出限制: {new_value} > "
                    f"{max_absolute} × {max_multiplier}"
                )

        return True, ""

    def _validate_probe_params(
        self, fix_plan: dict,
    ) -> tuple[bool, str]:
        """校验 probe 参数修改"""

        action_config = self.ALLOWED_ACTIONS.get("probe", {})
        allowed_fields = action_config.get("allowed_fields", [])
        min_delay = action_config.get("min_initial_delay", 10)
        max_failure = action_config.get("max_failure_threshold", 10)

        params = fix_plan.get("fix_params", {})
        field = params.get("field", "")
        new_value = params.get("new_value")

        if field and field not in allowed_fields:
            return False, f"不允许修改 probe 字段: {field}"

        if field == "initialDelaySeconds" and new_value:
            if new_value < min_delay:
                return False, (
                    f"initialDelaySeconds 不能小于 {min_delay}"
                )
        if field == "failureThreshold" and new_value:
            if new_value > max_failure:
                return False, (
                    f"failureThreshold 不能大于 {max_failure}"
                )

        return True, ""

    # ── 资源解析工具 ────────────────────────────────

    @staticmethod
    def _parse_resource(value: str) -> int | None:
        """
        解析 K8s 资源值（如 "256Mi", "2Gi", "4"）为数值。
        返回 int（bytes），解析失败返回 None。
        """
        if not value or not isinstance(value, str):
            return None

        value = value.strip()

        # 纯数字 → CPU cores 的毫核表示不便，直接用 float
        match = re.match(r'^(\d+(?:\.\d+)?)$', value)
        if match:
            return int(float(match.group(1)) * 1000)  # 转换为近似毫单位

        # Memory: Ki, Mi, Gi, Ti
        match = re.match(r'^(\d+(?:\.\d+)?)\s*(Ki|Mi|Gi|Ti)$', value)
        if match:
            num = float(match.group(1))
            unit = match.group(2)
            multipliers = {"Ki": 1024, "Mi": 1024**2,
                           "Gi": 1024**3, "Ti": 1024**4}
            return int(num * multipliers[unit])

        # CPU: m (milliCPU)
        match = re.match(r'^(\d+)m$', value)
        if match:
            return int(match.group(1))

        return None
