"""
决策引擎 —— 根据 AI 返回的置信度和修复类型，决定执行策略

confidence >= 0.8  → AUTO_EXEC
0.5 <= c < 0.8    → NEED_APPROVAL
c < 0.5           → ONLY_NOTIFY
"""

from src.models.fix import Decision, FixType


# 阈值配置
CONFIDENCE_AUTO_EXEC = 0.8
CONFIDENCE_APPROVAL = 0.5

# 即使高置信度也必须人工审批的操作
ALWAYS_NEED_APPROVAL: set[FixType] = {
    FixType.PVC,
    FixType.RESOURCE_QUOTA,
}


class DecisionEngine:
    """置信度驱动的决策引擎"""

    def decide(self, confidence: float, fix_type: str) -> Decision:
        """根据置信度和修复类型决定执行策略"""

        # 特殊类型强制人工审批
        if fix_type in {ft.value for ft in ALWAYS_NEED_APPROVAL}:
            return Decision.NEED_APPROVAL

        if confidence >= CONFIDENCE_AUTO_EXEC:
            return Decision.AUTO_EXEC
        elif confidence >= CONFIDENCE_APPROVAL:
            return Decision.NEED_APPROVAL
        else:
            return Decision.ONLY_NOTIFY
