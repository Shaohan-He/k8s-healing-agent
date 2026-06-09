"""诊断引擎单元测试"""
import pytest
from unittest.mock import AsyncMock, patch

from src.engine.diagnosis import DiagnosisEngine
from src.models.diagnosis import DiagnosisReport


class TestDiagnosisEngine:
    """测试诊断数据收集"""

    @pytest.mark.asyncio
    async def test_collect_returns_report(self):
        """诊断引擎应返回 DiagnosisReport"""
        engine = DiagnosisEngine()
        report = await engine.collect("test-pod", "default")
        assert isinstance(report, DiagnosisReport)
        assert report.pod_name == "test-pod"
        assert report.namespace == "default"

    @pytest.mark.asyncio
    async def test_collect_handles_missing_pod(self):
        """Pod 不存在时应优雅降级"""
        engine = DiagnosisEngine()
        report = await engine.collect("nonexistent-pod", "default")
        assert report.pod_name == "nonexistent-pod"
        # 不应抛异常
