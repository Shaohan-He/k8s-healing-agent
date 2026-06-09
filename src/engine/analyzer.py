"""
AI 分析引擎 —— 与 Claude API 交互的核心模块

将诊断数据发送给 Claude，获取结构化的根因分析和修复方案。

关键设计：
- System Prompt 锚定 SRE 专家角色 + 故障模式速查表
- User Prompt 格式化诊断数据为结构化文本
- JSON Schema 约束输出格式
- 验证失败时带纠错提示重试一次
- API 异常时降级：不冒险做修复，通知人工
"""

import asyncio
import json
import logging
import re
from pathlib import Path

import yaml

from src.models.diagnosis import DiagnosisReport
from src.safety.validator import AIResponseValidator

logger = logging.getLogger(__name__)


class AIAnalyzer:
    """Claude API 驱动的诊断分析器"""

    def __init__(
        self,
        api_key: str,
        prompt_config_path: str = "config/prompt.yaml",
        model: str = "claude-sonnet-4-6",
    ):
        self.api_key = api_key
        self.model = model
        self.validator = AIResponseValidator()

        prompt_path = Path(prompt_config_path)
        if prompt_path.exists():
            with open(prompt_path, encoding="utf-8") as f:
                self.prompt_config = yaml.safe_load(f) or {}
        else:
            logger.warning("Prompt 配置文件 %s 不存在", prompt_config_path)
            self.prompt_config = {}

    async def analyze(self, diagnosis: DiagnosisReport) -> dict:
        """发送诊断数据给 Claude，获取结构化分析结果"""

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(diagnosis)

        try:
            raw_text = await self._call_claude(system_prompt, user_prompt)
            if raw_text is None:
                return self._error_response(diagnosis, "Claude API 返回为空")

            result = self._extract_json(raw_text)

            # 验证
            valid, error = self.validator.validate(result, diagnosis)
            if not valid:
                # 第一次验证失败 → 带纠错提示重试一次
                logger.warning("AI 响应验证失败: %s，尝试重试", error)
                result = await self._retry_with_correction(
                    diagnosis, raw_text, error,
                )
                if result is None:
                    return self._fallback_response(diagnosis, raw_text)

            return result

        except Exception as exc:
            logger.error("Claude API 调用失败: %s", exc)
            return self._error_response(diagnosis, str(exc))

    # ── Prompt 构建 ──────────────────────────────────

    def _build_system_prompt(self) -> str:
        """从 prompt.yaml 加载 System Prompt"""
        return self.prompt_config.get("system_prompt", "")

    def _build_user_prompt(self, diagnosis: DiagnosisReport) -> str:
        """将诊断数据格式化为结构化 User Prompt"""

        lines = ["## 当前诊断数据\n"]

        # Pod 概要
        lines.append("### Pod 概要")
        lines.append(
            f"- Pod: {diagnosis.namespace}/{diagnosis.pod_name}"
        )
        lines.append(f"- Phase: {diagnosis.phase}")
        lines.append(f"- Node: {diagnosis.node_name}")
        lines.append(
            f"- Owner: {diagnosis.owner_kind}/{diagnosis.owner_name}"
        )
        lines.append(f"- 重启次数: {diagnosis.restart_count}")
        lines.append(f"- Image: {diagnosis.image}")
        lines.append("")

        # 容器状态
        if diagnosis.container_statuses:
            lines.append("### 容器状态")
            for cs in diagnosis.container_statuses:
                lines.append(f"- {cs.name}:")
                lines.append(f"  - State: {cs.state}")
                lines.append(f"  - Reason: {cs.reason}")
                lines.append(f"  - Exit Code: {cs.exit_code}")
                lines.append(f"  - Restart Count: {cs.restart_count}")
            lines.append("")

        # 资源限制
        limits = diagnosis.resource_limits
        requests = diagnosis.resource_requests
        lines.append("### 资源限制")
        lines.append(
            f"- Limits:   CPU={limits.get('cpu', '未设置')}, "
            f"Memory={limits.get('memory', '未设置')}"
        )
        lines.append(
            f"- Requests: CPU={requests.get('cpu', '未设置')}, "
            f"Memory={requests.get('memory', '未设置')}"
        )
        lines.append("")

        # Events
        if diagnosis.recent_events:
            lines.append("### 最近 Events (按时间倒序)")
            for event in diagnosis.recent_events[:20]:
                lines.append(
                    f"- [{event.type}] {event.reason}: {event.message}"
                )
            lines.append("")

        # 日志
        if diagnosis.previous_logs:
            lines.append("### 上一次崩溃日志 (最后 200 行)")
            lines.append("```")
            lines.append(diagnosis.previous_logs[-200:])
            lines.append("```")
            lines.append("")

        if diagnosis.current_logs:
            lines.append("### 当前运行日志 (最后 100 行)")
            lines.append("```")
            lines.append(diagnosis.current_logs[-100:])
            lines.append("```")

        return "\n".join(lines)

    # ── Claude API 调用 ──────────────────────────────

    async def _call_claude(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
    ) -> str | None:
        """
        异步调用 Claude API。
        使用 asyncio.to_thread 包装同步 SDK 调用。
        """
        import anthropic

        def _sync_call() -> str:
            client = anthropic.Anthropic(api_key=self.api_key)
            response = client.messages.create(
                model=self.model,
                max_tokens=1024,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return response.content[0].text

        try:
            return await asyncio.wait_for(
                asyncio.to_thread(_sync_call),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            logger.error("Claude API 调用超时")
            return None

    # ── JSON 提取 ────────────────────────────────────

    @staticmethod
    def _extract_json(text: str) -> dict:
        """从 Claude 回复中提取 JSON（处理 Markdown 代码块包裹）"""

        # 尝试匹配 ```json ... ``` 或 ``` ... ```
        match = re.search(
            r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL,
        )
        if match:
            text = match.group(1)

        # 尝试匹配裸 JSON
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            text = match.group(0)

        return json.loads(text)

    # ── 重试与降级 ──────────────────────────────────

    async def _retry_with_correction(
        self,
        diagnosis: DiagnosisReport,
        previous_response: str,
        error: str,
    ) -> dict | None:
        """验证失败时，带纠错提示重试一次"""
        correction_prompt = (
            f"你之前的回复验证未通过，错误原因：{error}\n\n"
            "请修正后重新返回严格符合 JSON Schema 的诊断结果。注意：\n"
            "1. 所有必填字段必须存在\n"
            "2. fix_type 只能从白名单中选择\n"
            "3. confidence 必须在 0.0-1.0 之间\n"
            "4. 不要建议删除任何资源\n\n"
            f"原始诊断数据：\n{self._build_user_prompt(diagnosis)}"
        )

        try:
            raw_text = await self._call_claude(
                system_prompt="",  # 不带 system prompt，直接纠错
                user_prompt=correction_prompt,
                temperature=0.0,
            )
            if raw_text is None:
                return None

            result = self._extract_json(raw_text)
            valid, error2 = self.validator.validate(result, diagnosis)
            if valid:
                return result

            logger.error("重试后验证仍失败: %s", error2)
            return None

        except Exception:
            return None

    def _fallback_response(
        self, diagnosis: DiagnosisReport, raw_text: str,
    ) -> dict:
        """重试失败后的降级响应——不冒险做修复，通知人工"""
        logger.warning("AI 分析降级：返回 unknown，通知人工")
        return {
            "root_cause": (
                f"AI 分析未产生有效结果，"
                f"原始回复: {raw_text[:200]}"
            ),
            "fix_type": "unknown",
            "fix_action": "人工排查",
            "confidence": 0.0,
            "evidence": ["AI 响应格式验证失败"],
            "alternative_causes": [],
            "severity_assessment": "未知",
            "fix_params": {},
        }

    def _error_response(
        self, diagnosis: DiagnosisReport, error: str,
    ) -> dict:
        """API 调用异常时的降级响应"""
        return {
            "root_cause": f"Claude API 调用异常: {error}",
            "fix_type": "unknown",
            "fix_action": "人工排查",
            "confidence": 0.0,
            "evidence": ["API 异常"],
            "alternative_causes": [],
            "severity_assessment": "未知",
            "fix_params": {},
        }
