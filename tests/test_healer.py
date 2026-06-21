"""Healing executor safety tests."""

import asyncio
from types import SimpleNamespace

from src.engine.healer import HealingExecutor


class FakeApiClient:
    @staticmethod
    def sanitize_for_serialization(resource):
        return {"snapshot": resource.metadata.name}


class FakeAppsV1:
    def __init__(self):
        self.api_client = FakeApiClient()
        self.patch_calls = []

    def patch_namespaced_deployment(self, name, namespace, body):
        self.patch_calls.append((name, namespace, body))
        if not isinstance(body, dict):
            raise RuntimeError("patch failed")

    def read_namespaced_replica_set(self, name, namespace):
        raise RuntimeError("replicaset lookup failed")


class FakeK8sClient:
    def __init__(self, owner_kind="Deployment"):
        self.apps_v1 = FakeAppsV1()
        self.owner_kind = owner_kind
        self.deployment = SimpleNamespace(
            metadata=SimpleNamespace(name="demo-deploy"),
            spec=SimpleNamespace(
                template=SimpleNamespace(
                    spec=SimpleNamespace(
                        containers=[
                            SimpleNamespace(
                                name="app",
                                resources=SimpleNamespace(limits={"memory": "256Mi"}),
                            )
                        ]
                    )
                )
            ),
        )

    def get_pod(self, name, namespace):
        return SimpleNamespace(
            metadata=SimpleNamespace(
                owner_references=[
                    SimpleNamespace(kind=self.owner_kind, name="demo-owner"),
                ]
            )
        )

    def get_deployment(self, name, namespace):
        return self.deployment


def test_execute_rolls_back_when_plain_exception_has_no_reason():
    k8s = FakeK8sClient()
    executor = HealingExecutor(k8s_client=k8s)

    async def run_execute():
        return await executor.execute(
            "demo-pod",
            "default",
            {
                "fix_type": "memory",
                "fix_params": {
                    "container_name": "app",
                    "new_memory_limit": "512Mi",
                },
            },
        )

    result = asyncio.run(run_execute())

    assert not result.success
    assert result.rollback_applied
    assert "patch failed" in result.error
    assert k8s.apps_v1.patch_calls[-1] == (
        "demo-owner",
        "default",
        {"snapshot": "demo-deploy"},
    )


def test_find_owner_handles_plain_replicaset_lookup_exception():
    k8s = FakeK8sClient(owner_kind="ReplicaSet")
    executor = HealingExecutor(k8s_client=k8s)

    assert executor._find_owner("demo-pod", "default") is None
