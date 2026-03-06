"""
搜索引擎封装模块
仅支持 Sogou 搜索方式
"""

import time
from typing import List, Dict, Any

try:
    from sogou_search import sogou_search
except ImportError as exc:
    raise ImportError("未安装搜狗搜索依赖 k-sogou-search，请先安装后再使用。") from exc


class SearchEngine:
    """搜索引擎封装类（仅搜狗）"""

    def __init__(self, engine: str = "sogou"):
        """
        初始化搜索引擎

        Args:
            engine: 搜索引擎类型，仅支持 "sogou"
        """
        engine = engine.lower()
        if engine != "sogou":
            raise ValueError("仅支持搜狗搜索引擎: 'sogou'")
        self.engine = engine
        self.delay = 1.0  # 默认搜索延迟

    def search(self, keywords: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        统一搜索接口

        Args:
            keywords: 搜索关键词
            max_results: 最大结果数

        Returns:
            搜索结果列表，每个结果包含 title, url, description 字段
        """
        print(f"使用 {self.engine.upper()} 搜索引擎搜索: '{keywords}'")
        try:
            results = self._search_sogou(keywords, max_results)
            time.sleep(self.delay)
            return results
        except Exception as e:
            print(f"搜索失败 (sogou): {e}")
            return []

    def _search_sogou(self, keywords: str, max_results: int) -> List[Dict[str, Any]]:
        """搜狗搜索"""
        return sogou_search(keywords, num_results=max_results)


if __name__ == "__main__":
    # 测试代码
    print("测试搜索引擎封装...")

    print("\n=== 测试搜狗搜索 ===")
    sogou_engine = SearchEngine(engine="sogou")
    sogou_results = sogou_engine.search("商汤科技", max_results=2)
    for i, result in enumerate(sogou_results, 1):
        print(f"{i}. {result['title']}")
        print(f"   URL: {result['url']}")
        print(f"   描述: {result['description'][:100]}...")
