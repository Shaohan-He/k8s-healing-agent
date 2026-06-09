"""
钉钉通知 —— 发送结构化的自愈通知消息
"""

import httpx
import logging

logger = logging.getLogger(__name__)


class DingTalkNotifier:
    """钉钉 Webhook 通知"""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send_healing_success(
        self, alert, ai_response, heal_result, verify_result,
        total_time: float, diagnosis_time: float, heal_time: float,
    ):
        """发送自愈成功通知"""
        # TODO: Send Markdown message via DingTalk webhook
        pass

    async def send_approval_request(self, alert, ai_response):
        """发送人工审批请求"""
        # TODO
        pass

    async def send_diagnosis_only(self, alert, ai_response):
        """仅发送诊断结果（不执行修复）"""
        # TODO
        pass

    async def send_error(self, alert, error_msg: str):
        """发送错误通知"""
        # TODO
        pass

    async def send_safety_block(self, alert, reason: str):
        """发送安全检查拦截通知"""
        # TODO
        pass

    async def send_loop_guard_block(self, alert, reason: str):
        """发送循环保护拦截通知"""
        # TODO
        pass
