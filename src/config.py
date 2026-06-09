"""配置管理 — YAML 文件 + 环境变量覆盖"""

import os
import logging
from pathlib import Path
from dataclasses import dataclass, field

import yaml

logger = logging.getLogger(__name__)


@dataclass
class Config:
    claude_api_key: str = ""
    dingtalk_webhook: str = ""
    audit_db_path: str = "data/healing_audit.db"
    log_level: str = "INFO"
    allowed_namespaces: list[str] = field(default_factory=lambda: [
        "default", "staging", "production",
    ])
    confidence_auto_exec: float = 0.8
    confidence_approval: float = 0.5
    verification_timeout: int = 120
    alert_dedup_window_seconds: int = 300
    healing_loop_max_per_hour: int = 2

    @classmethod
    def from_yaml(cls, path: str = "config/config.yaml") -> "Config":
        """从 YAML 文件加载配置，环境变量覆盖敏感项"""

        config_path = Path(path)
        if not config_path.exists():
            # 回退到示例配置
            example_path = Path("config/config.example.yaml")
            if example_path.exists():
                logger.warning(
                    "%s 不存在，使用 %s 作为默认配置",
                    path, example_path,
                )
                config_path = example_path
            else:
                logger.warning("无配置文件，使用默认值")
                return cls._apply_env_overrides(cls())

        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # 嵌套配置展平
        confidence = data.get("confidence", {})
        loop_guard = data.get("loop_guard", {})

        config = cls(
            claude_api_key=data.get("claude_api_key", ""),
            dingtalk_webhook=data.get("dingtalk_webhook", ""),
            audit_db_path=data.get("audit_db_path", "data/healing_audit.db"),
            log_level=data.get("log_level", "INFO"),
            allowed_namespaces=data.get(
                "allowed_namespaces",
                ["default", "staging", "production"],
            ),
            confidence_auto_exec=confidence.get("auto_exec", 0.8),
            confidence_approval=confidence.get("approval", 0.5),
            verification_timeout=data.get("verification_timeout", 120),
            alert_dedup_window_seconds=data.get(
                "alert_dedup_window_seconds", 300,
            ),
            healing_loop_max_per_hour=loop_guard.get(
                "max_healings_per_hour", 2,
            ),
        )

        return cls._apply_env_overrides(config)

    @classmethod
    def _apply_env_overrides(cls, config: "Config") -> "Config":
        """环境变量覆盖敏感配置"""
        if os.getenv("CLAUDE_API_KEY"):
            config.claude_api_key = os.getenv("CLAUDE_API_KEY")
        if os.getenv("DINGTALK_WEBHOOK"):
            config.dingtalk_webhook = os.getenv("DINGTALK_WEBHOOK")
        if os.getenv("LOG_LEVEL"):
            config.log_level = os.getenv("LOG_LEVEL")
        return config
