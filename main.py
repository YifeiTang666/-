"""
金融研报生成系统 - 主入口
统一接口，模块化架构
"""

import argparse  # 命令行参数解析器，让你可以用命令行传参
from src import (
    Config,
    DataCollector,
    ReportGenerator,
)  # 从你项目里的 src 包导入三个对象，三个对象在src/__init__.py


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="金融研报生成系统"
    )  # 创建命令行解析器对象 parser，description 是 --help 时显示的说明文字
    parser.add_argument(
        "--company", default="商汤科技", help="目标公司名称"
    )  # help是参数说明
    parser.add_argument("--code", default="00020", help="股票代码")
    parser.add_argument(
        "--market", default="HK", choices=["HK", "A"], help="市场类型"
    )  # 限制只能传这两种值，否则 argparse 会直接报错并提示正确用法
    parser.add_argument(
        "--search-engine", default="sogou", choices=["sogou"], help="搜索引擎"
    )

    args = parser.parse_args()  # 解析命令行参数

    print("=" * 80)
    print("🚀 金融研报生成系统")
    print("=" * 80)
    print(f"目标公司: {args.company}")
    print(f"股票代码: {args.code}")
    print(f"市场类型: {args.market}")
    print(f"搜索引擎: {args.search_engine}")
    print("=" * 80)

    # 1. 初始化配置
    config = Config.from_env(
        target_company=args.company,
        target_company_code=args.code,
        target_company_market=args.market,
    )
    config.search_engine = args.search_engine

    # 2. 初始化数据采集器
    collector = DataCollector(config)

    # 3. 采集数据
    data = collector.collect_all_data()

    # 4. 初始化生成器
    generator = ReportGenerator(config, collector)

    # 5. 分析数据
    analysis_results = generator.analyze_financial_data(data)

    # 6. 生成报告
    report_file = generator.generate_report(data, analysis_results)

    print("\n" + "=" * 80)
    print("✅ 流程完成！")
    print(f"📄 报告文件: {report_file}")
    print("=" * 80)


if __name__ == "__main__":
    main()
