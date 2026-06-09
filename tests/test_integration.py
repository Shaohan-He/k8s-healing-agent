"""端到端集成测试 —— 验证诊断→分析→决策→修复全流程"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.models.alert import AlertPayload
from src.models.diagnosis import DiagnosisReport
from src.models.fix import Decision, FixType
from src.engine.decision import DecisionEngine
from src.safety.validator import AIResponseValidator


class TestDecisionEngine:
    """决策引擎测试"""

    @pytest.fixture
    def engine(self):
        return DecisionEngine()

    def test_high_confidence_auto_exec(self, engine):
        """confidence >= 0.8 → AUTO_EXEC"""
        assert engine.decide(0.9, "memory") == Decision.AUTO_EXEC
        assert engine.decide(0.8, "cpu") == Decision.AUTO_EXEC

    def test_medium_confidence_approval(self, engine):
        """0.5 <= confidence < 0.8 → NEED_APPROVAL"""
        assert engine.decide(0.7, "config") == Decision.NEED_APPROVAL
        assert engine.decide(0.5, "probe") == Decision.NEED_APPROVAL

    def test_low_confidence_notify(self, engine):
        """confidence < 0.5 → ONLY_NOTIFY"""
        assert engine.decide(0.4, "memory") == Decision.ONLY_NOTIFY
        assert engine.decide(0.0, "unknown") == Decision.ONLY_NOTIFY

    def test_pvc_always_needs_approval(self, engine):
        """PVC 操作即使高置信度也要审批"""
        assert engine.decide(0.95, "pvc") == Decision.NEED_APPROVAL

    def test_resource_quota_always_needs_approval(self, engine):
        """ResourceQuota 操作即使高置信度也要审批"""
        assert engine.decide(0.99, "resource_quota") == Decision.NEED_APPROVAL


class TestAIResponseValidator:
    """AI 响应校验器测试"""

    @pytest.fixture
    def validator(self):
        return AIResponseValidator()

    @pytest.fixture
    def valid_response(self):
        return {
            "root_cause": "Pod test-pod 内存不足 OOMKilled",
            "fix_type": "memory",
            "fix_action": "增加 memory limit 到 1Gi",
            "confidence": 0.95,
            "evidence": ["Exit Code 137", "Events 显示 OOMKilled"],
            "alternative_causes": ["内存泄漏"],
            "severity_assessment": "服务不可用",
            "fix_params": {"new_memory_limit": "1Gi"},
        }

    @pytest.fixture
    def diagnosis(self):
        return DiagnosisReport(pod_name="test-pod", namespace="default")

    def test_valid_response_passes(self, validator, valid_response, diagnosis):
        valid, msg = validator.validate(valid_response, diagnosis)
        assert valid, f"Expected valid but got: {msg}"

    def test_missing_field_fails(self, validator, diagnosis):
        response = {"fix_type": "memory", "confidence": 0.9}
        valid, msg = validator.validate(response, diagnosis)
        assert not valid
        assert "root_cause" in msg

    def test_invalid_fix_type_fails(self, validator, valid_response):
        valid_response["fix_type"] = "delete_pod"
        valid, msg = validator.validate(valid_response, DiagnosisReport(pod_name="test-pod"))
        assert not valid
        assert "fix_type" in msg

    def test_confidence_out_of_range_fails(self, validator, valid_response):
        valid_response["confidence"] = 1.5
        valid, msg = validator.validate(valid_response, DiagnosisReport(pod_name="test-pod"))
        assert not valid

    def test_forbidden_action_fails(self, validator, valid_response):
        valid_response["fix_action"] = "kubectl delete pod test-pod --force"
        valid, msg = validator.validate(valid_response, DiagnosisReport(pod_name="test-pod"))
        assert not valid
        assert "禁止" in msg
