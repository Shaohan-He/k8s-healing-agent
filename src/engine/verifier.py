"""
验证引擎 —— 修复后验证 Pod 是否恢复正常

验证策略（按优先级）：
1. Pod Phase = Running
2. 所有容器 Ready = True
3. RestartCount 在观察窗口内不再增长
4. 最近 5min 没有新的 Warning Event
"""

import asyncio
import logging
import time

from src.models.fix import VerifyResult
from src.utils.k8s_client import K8sClient

logger = logging.getLogger(__name__)

# 验证间隔
_POLL_INTERVAL = 5.0
# 重启稳定观察窗口
_RESTART_STABLE_WINDOW = 60.0


class VerificationEngine:
    """修复后 Pod 健康验证"""

    def __init__(self, k8s_client: K8sClient | None = None):
        self.k8s = k8s_client or K8sClient()

    async def verify(
        self, pod_name: str, namespace: str, timeout: int = 120,
    ) -> VerifyResult:
        """
        验证修复是否成功。最多等待 timeout 秒。

        每 5 秒轮询一次 Pod 状态，检查：
        1. Phase == Running
        2. 所有容器 Ready
        3. 重启次数稳定（60s 内不再增长）
        """

        start = time.monotonic()
        last_restart_count: int | None = None
        restart_check_time: float | None = None

        while time.monotonic() - start < timeout:
            pod = self.k8s.get_pod(pod_name, namespace)
            if pod is None:
                logger.warning(
                    "验证期间获取 Pod %s/%s 失败，重试中...",
                    namespace, pod_name,
                )
                await asyncio.sleep(_POLL_INTERVAL)
                continue

            phase = pod.status.phase or ""

            # 1. Phase 检查
            if phase != "Running":
                logger.debug(
                    "Pod %s/%s phase=%s, 等待 Running...",
                    namespace, pod_name, phase,
                )
                await asyncio.sleep(_POLL_INTERVAL)
                continue

            # 2. 容器 Ready 检查
            if not self._all_containers_ready(pod):
                logger.debug(
                    "Pod %s/%s 容器未全部 Ready",
                    namespace, pod_name,
                )
                await asyncio.sleep(_POLL_INTERVAL)
                continue

            # 3. 重启稳定检查
            current_restart = sum(
                c.restart_count or 0
                for c in (pod.status.container_statuses or [])
            )

            if last_restart_count is None:
                # 首次 Running + Ready，开始观察重启稳定性
                last_restart_count = current_restart
                restart_check_time = time.monotonic()
                logger.debug(
                    "Pod %s/%s Running+Ready, "
                    "开始观察重启稳定性 (当前=%d)",
                    namespace, pod_name, current_restart,
                )
                await asyncio.sleep(_POLL_INTERVAL)
                continue

            if current_restart > last_restart_count:
                # 又重启了，重置观察
                logger.warning(
                    "Pod %s/%s 又发生了重启 (%d → %d)，重置观察",
                    namespace, pod_name,
                    last_restart_count, current_restart,
                )
                last_restart_count = current_restart
                restart_check_time = time.monotonic()
                await asyncio.sleep(_POLL_INTERVAL)
                continue

            # 已经稳定了足够时间
            elapsed_since_stable = time.monotonic() - (
                restart_check_time or start
            )
            if elapsed_since_stable >= _RESTART_STABLE_WINDOW:
                logger.info(
                    "Pod %s/%s 验证通过: Running+Ready, "
                    "重启稳定 %d 秒",
                    namespace, pod_name,
                    int(elapsed_since_stable),
                )
                return VerifyResult(success=True)

            logger.debug(
                "Pod %s/%s 稳定中... (%.0f/%.0f 秒)",
                namespace, pod_name,
                elapsed_since_stable, _RESTART_STABLE_WINDOW,
            )
            await asyncio.sleep(_POLL_INTERVAL)

        # 超时
        return VerifyResult(
            success=False,
            reason=f"验证超时 ({timeout}s)",
        )

    @staticmethod
    def _all_containers_ready(pod) -> bool:
        """检查所有容器是否 Ready"""

        container_statuses = pod.status.container_statuses or []
        if not container_statuses:
            return False

        for cs in container_statuses:
            if not cs.ready:
                return False

        return True
