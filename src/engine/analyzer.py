"""
AI 分析引擎 —— 与 Claude API 交互的核心模块

将诊断数据发送给 Claude，获取结构化的根因分析和修复方案。
"""

import json
import re
import yaml
from pathlib import Path

from src.models.diagnosis import DiagnosisReport
from src.models.fix import FixPlan


class AIAnalyzer:
    """Claude API 驱动的诊断分析器"""

    def __init__(self, api_key: str, prompt_config_path: str = "config/prompt.yaml"):
        self.api_key = api_key
        with open(prompt_config_path) as f:
            self.prompt_config = yaml.safe_load(f)

    async def analyze(self, diagnosis: DiagnosisReport) -> dict:
        """发送诊断数据给 Claude，获取结构化分析结果"""
        # TODO: Implement Claude API call with system prompt + user prompt
        return {
            "root_cause": "",
            "fix_type": "unknown",
            "fix_action": "",
            "confidence": 0.0,
            "evidence": [],
            "alternative_causes": [],
            "severity_assessment": "",
            "fix_params": {},
        }

    def _build_system_prompt(self) -> str:
        # TODO: Load from prompt.yaml and format
        return ""

    def _build_user_prompt(self, diagnosis: DiagnosisReport) -> str:
        # TODO: Format diagnosis data into structured text
        return ""

    @staticmethod
    def _extract_json(text: str) -> dict:
        """从 Claude 回复中提取 JSON"""
        match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if match:
            text = match.group(1)
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            text = match.group(0)
        return json.loads(text)
