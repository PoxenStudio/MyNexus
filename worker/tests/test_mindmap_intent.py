import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tools.mindmap import wants_mindmap


class MindmapIntentTests(unittest.TestCase):
    def test_explicit_mindmap_requests_are_detected(self):
        for text in ("给出本书观点的思维导图", "画一张脑图", "生成知识图谱", "画个概念图", "mind map"):
            self.assertTrue(wants_mindmap(text), text)

    def test_unrelated_questions_are_not_detected(self):
        for text in ("这本书讲了什么", "分析作者的主张", ""):
            self.assertFalse(wants_mindmap(text), text)


if __name__ == "__main__":
    unittest.main()
