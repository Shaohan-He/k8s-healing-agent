"""配置管理"""

from pathlib import Path
from dataclasses import dataclass


@dataclass
class Config:
    claude_api_key: str = ""
    dingtalk_webhook: str = ""
    audit_db_path: str = "data/healing_audit.db"
    log_level: str = "INFO"

    @classmethod
    def from_yaml(cls, path: str = "config/config.yaml") -> "Config":
        # TODO: Load from YAML file
        return cls()
