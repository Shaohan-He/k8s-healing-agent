"""
修复循环保护 —— 防止 Agent 对同一个 Pod 反复修复

规则：
- 1 小时内最多修复 2 次
- 相同类型修复 24 小时内最多 1 次
"""

from datetime import datetime, timedelta
from dataclasses import dataclass, field


@dataclass
class HealingRecord:
    pod_key: str = ""
    fix_type: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


class HealingLoopGuard:
    """修复循环检测与保护"""

    def __init__(self):
        self._healing_history: dict[str, list[HealingRecord]] = {}

    def should_allow(self, pod_key: str, fix_plan: dict) -> tuple[bool, str]:
        """检查是否允许对同一个 Pod 执行修复"""

        history = self._healing_history.get(pod_key, [])
        now = datetime.now()

        # 1 小时内最多修复 2 次
        recent = [h for h in history
                  if now - h.timestamp < timedelta(hours=1)]
        if len(recent) >= 2:
            return False, "1 小时内已修复 2 次，停止自动修复，需人工介入"

        # 相同类型修复 24 小时内最多 1 次
        fix_type = fix_plan.get("fix_type", "")
        same_type = [h for h in history
                     if h.fix_type == fix_type
                     and now - h.timestamp < timedelta(hours=24)]
        if same_type:
            return False, f"24 小时内已执行过相同类型修复 ({fix_type})"

        return True, "允许修复"

    def record(self, pod_key: str, fix_plan: dict):
        """记录一次修复"""
        if pod_key not in self._healing_history:
            self._healing_history[pod_key] = []
        self._healing_history[pod_key].append(HealingRecord(
            pod_key=pod_key,
            fix_type=fix_plan.get("fix_type", "unknown"),
        ))
