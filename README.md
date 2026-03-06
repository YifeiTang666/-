# 金融研报生成系统

## 📋 项目简介

基于AI大模型的智能金融研报生成平台，通过整合多源数据采集、智能数据分析和专业报告生成功能，实现从数据获取到研报输出的全流程自动化。

## 🏗️ 项目结构

```
financial_research_v2/
├── src/                    # 核心模块
│   ├── config.py          # 配置管理
│   ├── collector.py       # 数据采集器
│   └── generator.py       # 研报生成器
├── data/                   # 数据存储
│   ├── financial/         # 财务数据
│   ├── company/          # 公司信息
│   └── industry/         # 行业信息
├── outputs/               # 输出目录
├── main.py               # 主入口
└── requirements.txt      # 依赖包
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 运行

```bash
# 使用默认配置（商汤科技）
python main.py

# 自定义公司
python main.py --company 百度 --code 09888 --market HK
```

## 📊 功能特性

### 数据采集
- 财务报表采集（三大报表）
- 公司基本信息采集
- 竞争对手识别（AI驱动）
- 行业信息搜索

### 数据分析
- 单公司财务分析
- 多公司对比分析
- 自动生成图表
- 智能报告生成

### 报告生成
- Markdown格式报告
- 包含完整分析内容
- 自动格式化

## 🔧 配置说明

### 命令行参数

- `--company`: 目标公司名称（默认：商汤科技）
- `--code`: 股票代码（默认：00020）
- `--market`: 市场类型，HK或A（默认：HK）
- `--search-engine`: 搜索引擎，仅支持sogou（默认：sogou）

### 环境变量（可选）

如需覆盖默认配置，可创建 `.env` 文件：

```env
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-reasoner
SEARCH_ENGINE=sogou
```

## 📝 使用示例

### 命令行使用

```bash
# 分析商汤科技
python main.py

# 分析其他公司
python main.py --company 百度 --code 09888 --market HK
```

### 代码使用

```python
from src import Config, DataCollector, ReportGenerator

# 初始化配置
config = Config.from_env(
    target_company="商汤科技",
    target_company_code="00020",
    target_company_market="HK"
)

# 数据采集
collector = DataCollector(config)
data = collector.collect_all_data()

# 生成报告
generator = ReportGenerator(config, collector)
analysis_results = generator.analyze_financial_data(data)
report_file = generator.generate_report(data, analysis_results)
```

## 📦 主要依赖

- `pandas`: 数据处理
- `akshare`: 金融数据接口
- `openai`: LLM API
- `beautifulsoup4`: 网页解析
- `k-sogou-search`: 搜索引擎

完整依赖列表见 `requirements.txt`

## ⚠️ 注意事项

1. 系统已内置默认配置，可直接运行
2. 数据采集可能需要较长时间，请耐心等待
3. 搜索功能可能因网络问题失败，会自动重试
4. 建议使用搜狗搜索（更稳定）
