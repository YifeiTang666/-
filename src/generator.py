"""
统一研报生成器 - 提供完整的报告生成功能
"""

import os
import glob
import json
from datetime import datetime
from typing import Dict, List, Optional

# 导入数据分析智能体（内置精简版）
try:
    from .analysis_agent import quick_analysis, LLMConfig, LLMHelper
except Exception as e:
    print("警告: 无法导入内置数据分析模块，部分功能可能不可用")
    print(f"导入错误详情: {e}")
    import traceback
    traceback.print_exc()
    quick_analysis = None
    LLMConfig = None
    LLMHelper = None


class ReportGenerator:
    """统一研报生成器"""
    
    def __init__(self, config, collector):
        """
        初始化生成器
        
        Args:
            config: Config对象
            collector: DataCollector对象
        """
        self.config = config
        self.collector = collector
        
        # 初始化LLM
        if LLMHelper:
            llm_config = LLMConfig(
                api_key=config.llm.api_key,
                base_url=config.llm.base_url,
                model=config.llm.model,
                temperature=config.llm.temperature,
                max_tokens=config.llm.max_tokens
            )
            self.llm = LLMHelper(llm_config)
        else:
            self.llm = None
    
    def analyze_financial_data(self, data: Dict) -> Dict:
        """
        分析财务数据
        
        Args:
            data: 采集的数据字典
            
        Returns:
            分析结果字典
        """
        print("\n" + "="*80)
        print("📈 开始财务数据分析")
        print("="*80)
        
        if not quick_analysis:
            print("❌ 数据分析智能体不可用")
            return {}
        
        llm_config = LLMConfig(
            api_key=self.config.llm.api_key,
            base_url=self.config.llm.base_url,
            model=self.config.llm.model,
            temperature=self.config.llm.temperature,
            max_tokens=self.config.llm.max_tokens
        )
        
        # 获取所有财务文件
        all_files = glob.glob(f"{self.config.financial_dir}/*.csv")
        if not all_files:
            print("❌ 未找到财务数据文件")
            return {}
        
        # 按公司分组
        company_files = {}
        for file in all_files:
            filename = os.path.basename(file)
            company_name = filename.split("_")[0]
            company_files.setdefault(company_name, []).append(file)
        
        # 单公司分析
        print("\n📊 单公司财务分析...")
        individual_reports = {}
        for company_name, files in company_files.items():
            print(f"  分析 {company_name}...")
            try:
                report = quick_analysis(
                    query="基于表格的数据，分析有价值的内容，并绘制相关图表。最后生成汇报给我。",
                    files=files,
                    llm_config=llm_config,
                    absolute_path=True,
                    max_rounds=self.config.max_analysis_rounds
                )
                if report:
                    individual_reports[company_name] = report
            except Exception as e:
                print(f"  ❌ 分析 {company_name} 失败: {e}")
        
        # 对比分析
        print("\n📊 对比分析...")
        comparison_reports = {}
        target_name = self.config.target_company
        if target_name in company_files:
            competitors = [c for c in company_files.keys() if c != target_name]
            for competitor in competitors:
                print(f"  对比 {target_name} vs {competitor}...")
                try:
                    all_files = company_files[target_name] + company_files[competitor]
                    report = quick_analysis(
                        query="基于两个公司的表格的数据，分析有共同点的部分，绘制对比分析的表格，并绘制相关图表。最后生成汇报给我。",
                        files=all_files,
                        llm_config=llm_config,
                        absolute_path=True,
                        max_rounds=self.config.max_analysis_rounds
                    )
                    if report:
                        comparison_reports[f"{target_name}_vs_{competitor}"] = report
                except Exception as e:
                    print(f"  ❌ 对比分析失败: {e}")
        
        return {
            'individual_reports': individual_reports,
            'comparison_reports': comparison_reports
        }
    
    def format_company_info(self, data: Dict) -> str:
        """整理公司信息"""
        if not self.llm:
            return "LLM不可用，无法整理公司信息"
        
        company_infos = ""
        # 读取所有公司信息文件
        for filename in os.listdir(self.config.company_dir):
            if filename.endswith(".txt"):
                filepath = os.path.join(self.config.company_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                company_name = filename.split("_")[0]
                company_infos += f"【{company_name}信息开始】\n{content}\n【{company_name}信息结束】\n\n"
        
        if company_infos:
            formatted = self.llm.call(
                f"请整理以下公司信息内容，确保格式清晰易读，并保留关键信息：\n{company_infos}",
                system_prompt="你是一个专业的公司信息整理师。",
                max_tokens=16384,
                temperature=0.5
            )
            return formatted
        return "无公司信息"
    
    def format_industry_info(self, data: Dict) -> str:
        """整理行业信息"""
        search_file = os.path.join(self.config.industry_dir, "all_search_results.json")
        if not os.path.exists(search_file):
            return "无行业信息"
        
        with open(search_file, 'r', encoding='utf-8') as f:
            all_results = json.load(f)
        
        formatted = ""
        for company, results in all_results.items():
            formatted += f"【{company}搜索信息开始】\n"
            for result in results:
                title = result.get('title', '无标题')
                url = result.get('url') or result.get('href', '无链接')
                desc = result.get('description') or result.get('body', '无摘要')
                formatted += f"标题: {title}\n链接: {url}\n摘要: {desc}\n----\n"
            formatted += f"【{company}搜索信息结束】\n\n"
        
        return formatted
    
    def format_analysis_reports(self, analysis_results: Dict) -> str:
        """格式化分析报告"""
        formatted = []
        
        # 单公司报告
        for company, report in analysis_results.get('individual_reports', {}).items():
            formatted.append(f"【{company}财务数据分析结果开始】")
            final_report = report.get("final_report", "未生成报告")
            formatted.append(final_report)
            formatted.append(f"【{company}财务数据分析结果结束】\n")
        
        # 对比报告
        for comp_key, report in analysis_results.get('comparison_reports', {}).items():
            formatted.append(f"【{comp_key}对比分析结果开始】")
            final_report = report.get("final_report", "未生成报告")
            formatted.append(final_report)
            formatted.append(f"【{comp_key}对比分析结果结束】\n")
        
        return "\n".join(formatted)
    
    def generate_report(self, data: Dict, analysis_results: Dict) -> str:
        """
        生成完整研报
        
        Args:
            data: 采集的数据
            analysis_results: 分析结果
            
        Returns:
            研报文件路径
        """
        print("\n" + "="*80)
        print("📝 生成完整研报")
        print("="*80)
        
        # 整理各部分内容
        company_info = self.format_company_info(data)
        industry_info = self.format_industry_info(data)
        analysis_report = self.format_analysis_reports(analysis_results)
        
        # 生成Markdown报告
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(self.config.output_dir, f"财务研报汇总_{timestamp}.md")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# {self.config.target_company} 财务研报\n\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")
            f.write(f"## 公司基础信息\n\n{company_info}\n\n")
            f.write("---\n\n")
            f.write(f"## 行业信息\n\n{industry_info}\n\n")
            f.write("---\n\n")
            f.write(f"## 财务数据分析\n\n{analysis_report}\n\n")
        
        print(f"✅ 研报已保存到: {output_file}")
        return output_file

