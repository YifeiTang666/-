"""
统一数据采集器 - 提供完整的数据采集功能
"""

import os
import time
import json
import akshare as ak
import pandas as pd
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Tuple
import yaml
import openai

# 导入搜索引擎
try:
    from .search_engine import SearchEngine
except Exception:
    SearchEngine = None

if SearchEngine is None:
    import sys

    parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    utils_path = os.path.join(parent_dir, "financial_research_report-main", "utils")
    if os.path.exists(utils_path):
        sys.path.append(utils_path)
        try:
            from search_engine import SearchEngine
        except ImportError:
            SearchEngine = None

if SearchEngine is None:

    class SearchEngine:
        def __init__(self, engine="sogou"):
            self.engine = engine
            self.delay = 1.0

        def search(self, keywords, max_results=10):
            print(f"警告: 搜索引擎模块不可用，返回空结果")
            return []


class DataCollector:
    """统一数据采集器"""

    def __init__(self, config):
        """
        初始化数据采集器

        Args:
            config: Config对象
        """
        self.config = config
        self.search_engine = SearchEngine(config.search_engine)

    def get_financial_statements(
        self, stock_code: str, market: str, company_name: str = None
    ) -> Dict[str, Optional[pd.DataFrame]]:
        """
        获取财务报表

        Args:
            stock_code: 股票代码
            market: 市场类型 (HK/A)
            company_name: 公司名称（可选）

        Returns:
            包含三大报表的字典
        """
        print(f"📊 获取 {company_name or stock_code} 的财务报表...")

        try:
            if market == "HK":
                balance = ak.stock_financial_hk_report_em(
                    stock=stock_code, symbol="资产负债表", indicator="年度"
                )
                income = ak.stock_financial_hk_report_em(
                    stock=stock_code, symbol="利润表", indicator="年度"
                )
                cashflow = ak.stock_financial_hk_report_em(
                    stock=stock_code, symbol="现金流量表", indicator="年度"
                )
            else:  # A股
                balance = ak.stock_balance_sheet_by_yearly_em(symbol=stock_code)
                income = ak.stock_profit_sheet_by_yearly_em(symbol=stock_code)
                cashflow = ak.stock_cash_flow_sheet_by_yearly_em(symbol=stock_code)

            statements = {
                "balance_sheet": balance,
                "income_statement": income,
                "cash_flow_statement": cashflow,
            }

            # 保存到CSV
            if company_name:
                for stype, df in statements.items():
                    if df is not None:
                        filename = (
                            f"{company_name}_{market}_{stock_code}_{stype}_年度.csv"
                        )
                        filepath = os.path.join(self.config.financial_dir, filename)
                        df.to_csv(filepath, index=False, encoding="utf-8-sig")

            print(f"✅ 财务报表获取完成")
            return statements

        except Exception as e:
            print(f"❌ 获取财务报表失败: {e}")
            return {
                "balance_sheet": None,
                "income_statement": None,
                "cash_flow_statement": None,
            }

    def get_company_info(
        self, stock_code: str, market: str, company_name: str = None
    ) -> Optional[str]:
        """
        获取公司基本信息

        Args:
            stock_code: 股票代码
            market: 市场类型
            company_name: 公司名称

        Returns:
            公司信息字符串
        """
        print(f"🏢 获取 {company_name or stock_code} 的公司信息...")

        try:
            clean_code = (
                stock_code.replace("SH", "").replace("SZ", "").replace("HK", "")
            )

            if market == "HK":
                df = ak.stock_hk_company_profile_em(symbol=clean_code)
            else:
                df = ak.stock_zyjs_ths(symbol=clean_code)

            if df is not None and not df.empty:
                info_str = df.to_string(index=False)

                # 保存到文件
                if company_name:
                    filename = f"{company_name}_{market}_{stock_code}_info.txt"
                    filepath = os.path.join(self.config.company_dir, filename)
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(info_str)

                print(f"✅ 公司信息获取完成")
                return info_str
            return None

        except Exception as e:
            print(f"❌ 获取公司信息失败: {e}")
            return None

    def identify_competitors(self, company_name: str) -> List[Dict[str, str]]:
        """
        识别竞争对手

        Args:
            company_name: 公司名称

        Returns:
            竞争对手列表
        """
        print(f"🔍 识别 {company_name} 的竞争对手...")

        prompt = f"""
        请分析以下公司的竞争对手：
        公司名称: {company_name}
        
        请根据以下标准识别该公司的主要竞争对手：
        1. 同行业内的主要上市公司
        2. 业务模式相似的公司
        3. 市值规模相近的公司
        4. 主要业务重叠度高的公司
        
        请返回3-5个主要竞争对手，按竞争程度排序，以YAML格式输出。
        格式要求：包含公司名称、股票代码和上市区域信息。
        
        **股票代码格式要求**：
        - A股：6位数字（如 000001、688327）
        - 港股：5位数字，不足5位前面补0（如 00700、09888）
        - 未上市公司：留空""
        
        **重要说明**：只关注A股和港股市场的竞争对手，不包括美股市场。
        
        请用```yaml包围你的输出内容。
        """

        try:
            client = openai.OpenAI(
                api_key=self.config.llm.api_key, base_url=self.config.llm.base_url
            )
            response = client.chat.completions.create(
                model=self.config.llm.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个专业的金融分析师，擅长识别公司的竞争对手。请严格按照YAML格式返回结果。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
            )

            competitors_text = response.choices[0].message.content.strip()

            if "```yaml" in competitors_text:
                competitors_text = (
                    competitors_text.split("```yaml")[1].split("```")[0].strip()
                )
            elif "```" in competitors_text:
                competitors_text = (
                    competitors_text.split("```")[1].split("```")[0].strip()
                )

            data = yaml.safe_load(competitors_text)
            competitors = data.get("competitors", [])
            print(f"✅ 识别到 {len(competitors)} 个竞争对手")
            return competitors[:5]

        except Exception as e:
            print(f"❌ 识别竞争对手失败: {e}")
            return []

    def search_industry_info(
        self, keywords: str, max_retries: int = 3, delay: int = 20
    ) -> List[Dict]:
        """
        搜索行业信息（带重试机制）

        Args:
            keywords: 搜索关键词
            max_retries: 最大重试次数
            delay: 重试延迟（秒）

        Returns:
            搜索结果列表
        """
        for attempt in range(max_retries):
            try:
                results = self.search_engine.search(keywords, max_results=10)
                if results:
                    return results
                else:
                    print(f"  警告: 搜索返回空结果，尝试 {attempt + 1}/{max_retries}")
            except Exception as e:
                print(f"  搜索失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    print(f"  等待 {delay} 秒后重试...")
                    time.sleep(delay)
                else:
                    print(f"  搜索最终失败，跳过此关键词")
                    return []
        return []

    def collect_all_data(self) -> Dict:
        """
        采集所有数据

        Returns:
            包含所有采集数据的字典
        """
        print("\n" + "=" * 80)
        print("🚀 开始数据采集")
        print("=" * 80)

        # 1. 识别竞争对手
        competitors = self.identify_competitors(self.config.target_company)
        listed_competitors = [c for c in competitors if c.get("market") != "未上市"]

        # 2. 获取目标公司数据
        target_financials = self.get_financial_statements(
            self.config.target_company_code,
            self.config.target_company_market,
            self.config.target_company,
        )
        target_company_info = self.get_company_info(
            self.config.target_company_code,
            self.config.target_company_market,
            self.config.target_company,
        )

        # 3. 获取竞争对手数据
        competitors_financials = {}
        competitors_info = {}

        for idx, comp in enumerate(listed_competitors, 1):
            comp_name = comp.get("name")
            comp_code = comp.get("code")
            comp_market_str = comp.get("market", "")

            # 处理市场代码
            if "A" in comp_market_str:
                comp_market = "A"
                if not (comp_code.startswith("SH") or comp_code.startswith("SZ")):
                    if comp_code.startswith("6"):
                        comp_code = f"SH{comp_code}"
                    else:
                        comp_code = f"SZ{comp_code}"
            elif "港" in comp_market_str:
                comp_market = "HK"
            else:
                continue

            print(f"\n[{idx}/{len(listed_competitors)}] 处理竞争对手: {comp_name}")

            comp_financials = self.get_financial_statements(
                comp_code, comp_market, comp_name
            )
            comp_info = self.get_company_info(comp_code, comp_market, comp_name)

            competitors_financials[comp_name] = comp_financials
            if comp_info:
                competitors_info[comp_name] = comp_info

            time.sleep(2)  # 避免请求过快

        # 4. 搜索行业信息
        print("\n🔍 搜索行业信息...")
        all_search_results = {}

        # 搜索目标公司
        target_keywords = (
            f"{self.config.target_company} 行业地位 市场份额 竞争分析 业务模式"
        )
        target_results = self.search_industry_info(target_keywords)
        all_search_results[self.config.target_company] = target_results

        # 搜索竞争对手
        for comp in listed_competitors:
            comp_name = comp.get("name")
            comp_keywords = f"{comp_name} 行业地位 市场份额 业务模式 发展战略"
            comp_results = self.search_industry_info(comp_keywords, delay=25)
            all_search_results[comp_name] = comp_results
            time.sleep(self.config.search_delay)

        # 保存搜索结果
        search_file = os.path.join(self.config.industry_dir, "all_search_results.json")
        with open(search_file, "w", encoding="utf-8") as f:
            json.dump(all_search_results, f, ensure_ascii=False, indent=2)

        print("\n✅ 数据采集完成")

        return {
            "target_company": self.config.target_company,
            "target_financials": target_financials,
            "target_company_info": target_company_info,
            "competitors": listed_competitors,
            "competitors_financials": competitors_financials,
            "competitors_info": competitors_info,
            "industry_search_results": all_search_results,
        }
