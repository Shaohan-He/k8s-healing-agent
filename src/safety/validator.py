"""
AI 响应校验器 —— 防止 AI 幻觉导致错误修复

五道防线：
1. JSON 结构校验（必填字段）
2. fix_type 白名单校验
3. confidence 范围校验
4. Pod 名称一致性校验（防幻觉）
5. 禁止操作模式检测
"""

import re
import logging

from src.models.diagnosis import DiagnosisReport

logger = logging.getLogger(__name__)

# 合法修复类型
VALID_FIX_TYPES = [
    "memory", "cpu", "image", "config",
    "resource_quota", "probe", "pvc", "unknown",
]

# 禁止操作的正则模式
FORBIDDEN_PATTERNS = [
    r"删除.*(pod|pvc|configmap|secret|deployment)",
    r"重启.*(集群|节点|node)",
    r"kubectl delete",
    r"force delete",
]


class AIResponseValidator:
    """验证 Claude 返回的结构化诊断结果"""

    def validate(self, response: dict, diagnosis: DiagnosisReport) -> tuple[bool, str]:
        """五道防线逐一校验"""

        # 1. JSON 结构校验
        required_fields = [
            "root_cause", "fix_type", "confidence", "fix_action",
        ]
        for field in required_fields:
            if field not in response:
                return False, f"缺少必要字段: {field}"

        # 2. fix_type 白名单校验
        if response["fix_type"] not in VALID_FIX_TYPES:
            return False, f"无效的 fix_type: {response['fix_type']}"

        # 3. confidence 范围校验
        confidence = response["confidence"]
        if not isinstance(confidence, (int, float)) or not (0.0 <= confidence <= 1.0):
            return False, f"confidence 超出范围: {confidence}"

        # 4. 逻辑校验——Pod 名称一致性
        if diagnosis.pod_name.lower() not in response["root_cause"].lower():
            logger.warning("AI 回复中未提及目标 Pod，可能存在幻觉")

        # 5. 禁止操作检测
        fix_action = response.get("fix_action", "")
        for pattern in FORBIDDEN_PATTERNS:
            if re.search(pattern, fix_action, re.IGNORECASE):
                return False, f"修复方案包含禁止操作: {pattern}"

        return True, "验证通过"
