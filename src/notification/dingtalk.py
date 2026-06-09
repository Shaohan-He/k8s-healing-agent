"""
钉钉通知 —— 发送结构化的自愈通知消息
"""

import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

# 通知模板
MARKDOWN_TEMPLATE = """## 🤖 K8s 自愈 Agent 通知

**告警**: {alert_name}
**Pod**: {namespace}/{pod_name}
**严重级别**: {severity}
**触发时间**: {starts_at}

---

### 🔍 AI 诊断结果
- **根因**: {root_cause}
- **修复类型**: {fix_type}
- **置信度**: {confidence:.0%}

### 🔧 执行动作
- **决策**: {decision}
- **修复操作**: {fix_action}
- **执行结果**: {result}

### ⏱️ 耗时
- 诊断: {diagnosis_time:.1f}s
- 修复: {heal_time:.1f}s
- 总计: {total_time:.1f}s

---
[查看审计日志]({audit_url}) | [K8s Dashboard]({dashboard_url})
"""

APPROVAL_TEMPLATE = """## 🔔 K8s 自愈 Agent — 需要人工审批

**告警**: {alert_name}
**Pod**: {namespace}/{pod_name}
**严重级别**: {severity}

---

### 🔍 AI 诊断结果
- **根因**: {root_cause}
- **修复类型**: {fix_type}
- **置信度**: {confidence:.0%}（低于自动执行阈值 80%）

### 📋 建议修复操作
{fix_action}

### 📊 证据
{evidence}

---

> ⚠️ 请人工确认后执行修复
"""

ERROR_TEMPLATE = """## ❌ K8s 自愈 Agent — 异常通知

**告警**: {alert_name}
**Pod**: {namespace}/{pod_name}

**错误**: {error}

---

> 自动修复管道异常，请人工排查
"""


class DingTalkNotifier:
    """钉钉 Webhook 通知"""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self._enabled = bool(webhook_url)

    async def send_healing_success(
        self,
        alert,
        ai_response: dict,
        heal_result,
        verify_result,
        total_time: float,
        diagnosis_time: float,
        heal_time: float,
    ):
        """发送自愈成功通知"""
        result_text = (
            "✅ 修复成功，验证通过"
            if (hasattr(verify_result, "success") and verify_result.success)
            else "⚠️ 修复已执行但验证未通过"
        )

        markdown = MARKDOWN_TEMPLATE.format(
            alert_name=getattr(alert, "alert_name", "未知"),
            namespace=getattr(alert, "namespace", ""),
            pod_name=getattr(alert, "pod_name", ""),
            severity=getattr(alert, "severity", "warning"),
            starts_at=getattr(alert, "starts_at", datetime.now(timezone.utc)),
            root_cause=ai_response.get("root_cause", "未知"),
            fix_type=ai_response.get("fix_type", "unknown"),
            confidence=ai_response.get("confidence", 0.0),
            decision="AUTO_EXEC（自动执行）",
            fix_action=ai_response.get("fix_action", ""),
            result=result_text,
            diagnosis_time=diagnosis_time,
            heal_time=heal_time,
            total_time=total_time,
            audit_url="",
            dashboard_url="",
        )

        await self._send(markdown, "自愈成功")

    async def send_approval_request(self, alert, ai_response: dict):
        """发送人工审批请求"""
        evidence = "\n".join(
            f"- {e}" for e in ai_response.get("evidence", [])
        )

        markdown = APPROVAL_TEMPLATE.format(
            alert_name=getattr(alert, "alert_name", "未知"),
            namespace=getattr(alert, "namespace", ""),
            pod_name=getattr(alert, "pod_name", ""),
            severity=getattr(alert, "severity", "warning"),
            root_cause=ai_response.get("root_cause", "未知"),
            fix_type=ai_response.get("fix_type", "unknown"),
            confidence=ai_response.get("confidence", 0.0),
            fix_action=ai_response.get("fix_action", ""),
            evidence=evidence or "无",
        )

        await self._send(markdown, "人工审批请求")

    async def send_diagnosis_only(self, alert, ai_response: dict):
        """仅发送诊断结果（不执行修复）"""
        markdown = (
            f"## 🔍 K8s 自愈 Agent — 诊断通知\n\n"
            f"**告警**: {getattr(alert, 'alert_name', '未知')}\n"
            f"**Pod**: {getattr(alert, 'namespace', '')}/"
            f"{getattr(alert, 'pod_name', '')}\n\n"
            f"---\n\n"
            f"### 诊断结果\n"
            f"- **根因**: {ai_response.get('root_cause', '未知')}\n"
            f"- **置信度**: {ai_response.get('confidence', 0):.0%}"
            f"（低于阈值 {0.5:.0%}，不做自动修复）\n\n"
            f"> 仅通知，需人工排查"
        )

        await self._send(markdown, "诊断通知")

    async def send_error(self, alert, error_msg: str):
        """发送错误通知"""
        markdown = ERROR_TEMPLATE.format(
            alert_name=getattr(alert, "alert_name", "未知"),
            namespace=getattr(alert, "namespace", ""),
            pod_name=getattr(alert, "pod_name", ""),
            error=error_msg,
        )

        await self._send(markdown, "异常")

    async def send_safety_block(self, alert, reason: str):
        """发送安全检查拦截通知"""
        markdown = (
            f"## 🛡️ K8s 自愈 Agent — 安全拦截\n\n"
            f"**Pod**: {getattr(alert, 'namespace', '')}/"
            f"{getattr(alert, 'pod_name', '')}\n\n"
            f"**拦截原因**: {reason}\n\n"
            f"> 修复操作被安全策略拦截"
        )

        await self._send(markdown, "安全拦截")

    async def send_loop_guard_block(self, alert, reason: str):
        """发送循环保护拦截通知"""
        markdown = (
            f"## 🔄 K8s 自愈 Agent — 循环保护拦截\n\n"
            f"**Pod**: {getattr(alert, 'namespace', '')}/"
            f"{getattr(alert, 'pod_name', '')}\n\n"
            f"**拦截原因**: {reason}\n\n"
            f"> 短时间内修复次数过多，需人工排查是否存在更深层问题"
        )

        await self._send(markdown, "循环保护")

    async def send_healing_failure(self, alert, heal_result):
        """发送修复失败通知"""
        error = (
            heal_result.error
            if hasattr(heal_result, "error")
            else str(heal_result)
        )
        markdown = (
            f"## ⚠️ K8s 自愈 Agent — 修复失败\n\n"
            f"**Pod**: {getattr(alert, 'namespace', '')}/"
            f"{getattr(alert, 'pod_name', '')}\n\n"
            f"**错误**: {error}\n\n"
            f"> 已自动回滚到修复前状态"
        )

        await self._send(markdown, "修复失败")

    async def _send(self, markdown: str, title: str):
        """发送钉钉 Markdown 消息"""
        if not self._enabled:
            logger.debug("钉钉通知未配置，跳过: %s", title)
            return

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": markdown,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self.webhook_url, json=payload)
                if resp.status_code != 200:
                    logger.error(
                        "钉钉通知发送失败: HTTP %d, %s",
                        resp.status_code, resp.text,
                    )
        except Exception as e:
            logger.error("钉钉通知发送异常: %s", e)
