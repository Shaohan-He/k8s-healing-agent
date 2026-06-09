"""AI 分析引擎单元测试"""
import json
import pytest
from src.engine.analyzer import AIAnalyzer


class TestJSONExtraction:
    """测试从 Claude 回复中提取 JSON"""

    def test_extract_bare_json(self):
        """裸 JSON 对象"""
        text = '{"root_cause": "OOM", "fix_type": "memory", "confidence": 0.95}'
        result = AIAnalyzer._extract_json(text)
        assert result["root_cause"] == "OOM"

    def test_extract_json_in_code_block(self):
        """JSON 在 ```json 代码块中"""
        text = '''```json
{"root_cause": "OOM", "fix_type": "memory", "confidence": 0.95}
```'''
        result = AIAnalyzer._extract_json(text)
        assert result["fix_type"] == "memory"

    def test_extract_json_with_surrounding_text(self):
        """JSON 周围有说明文字"""
        text = '''分析结果如下：
{"root_cause": "OOM", "fix_type": "memory", "confidence": 0.95}
以上是我的诊断。'''
        result = AIAnalyzer._extract_json(text)
        assert result["confidence"] == 0.95

    def test_extract_invalid_json_raises(self):
        """无效 JSON 应抛出异常"""
        text = "这不是 JSON"
        with pytest.raises(json.JSONDecodeError):
            AIAnalyzer._extract_json(text)
