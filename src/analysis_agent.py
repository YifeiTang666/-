"""
轻量级数据分析智能体
从 data_analysis_agent 精简整合而来
"""

import os
import ast
import uuid
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

import yaml
from openai import OpenAI
from IPython.core.interactiveshell import InteractiveShell
from IPython.utils.capture import capture_output
import matplotlib
import matplotlib.pyplot as plt


@dataclass
class LLMConfig:
    """LLM配置"""
    api_key: str
    base_url: str
    model: str
    temperature: float = 0.1
    max_tokens: int = 16384


class LLMHelper:
    """LLM调用辅助类（同步）"""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = OpenAI(api_key=config.api_key, base_url=config.base_url)

    def call(self, prompt: str, system_prompt: str = None, max_tokens: int = None, temperature: float = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            max_tokens=max_tokens or self.config.max_tokens,
            temperature=temperature if temperature is not None else self.config.temperature,
        )
        return response.choices[0].message.content

    def parse_yaml_response(self, response: str) -> dict:
        """解析YAML格式的响应"""
        try:
            if "```yaml" in response:
                start = response.find("```yaml") + 7
                end = response.find("```", start)
                yaml_content = response[start:end].strip()
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                yaml_content = response[start:end].strip()
            else:
                yaml_content = response.strip()
            return yaml.safe_load(yaml_content)
        except Exception as exc:
            print(f"YAML解析失败: {exc}")
            print(f"原始响应: {response}")
            return {}


def create_session_output_dir(base_output_dir: str, user_input: str) -> str:
    """为本次分析创建独立输出目录"""
    session_id = uuid.uuid4().hex
    dir_name = f"session_{session_id}"
    session_dir = os.path.join(base_output_dir, dir_name)
    os.makedirs(session_dir, exist_ok=True)
    return session_dir


def extract_code_from_response(response: str) -> Optional[str]:
    """从LLM响应中提取代码"""
    try:
        if "```yaml" in response:
            start = response.find("```yaml") + 7
            end = response.find("```", start)
            yaml_content = response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            yaml_content = response[start:end].strip()
        else:
            yaml_content = response.strip()

        yaml_data = yaml.safe_load(yaml_content)
        if "code" in yaml_data:
            return yaml_data["code"]
    except Exception:
        pass

    if "```python" in response:
        start = response.find("```python") + 9
        end = response.find("```", start)
        if end != -1:
            return response[start:end].strip()
    elif "```" in response:
        start = response.find("```") + 3
        end = response.find("```", start)
        if end != -1:
            return response[start:end].strip()
    return None


def format_execution_result(result: Dict[str, Any]) -> str:
    """格式化执行结果为用户可读的反馈"""
    feedback = []
    if result["success"]:
        feedback.append("✅ 代码执行成功")
        if result["output"]:
            feedback.append(f"📊 输出结果：\n{result['output']}")
        if result.get("variables"):
            feedback.append("📋 新生成的变量：")
            for var_name, var_info in result["variables"].items():
                feedback.append(f"  - {var_name}: {var_info}")
    else:
        feedback.append("❌ 代码执行失败")
        feedback.append(f"错误信息: {result['error']}")
        if result["output"]:
            feedback.append(f"部分输出: {result['output']}")
    return "\n".join(feedback)


class CodeExecutor:
    """安全的代码执行器，限制依赖库，捕获输出"""

    ALLOWED_IMPORTS = {
        "pandas", "pd",
        "numpy", "np",
        "matplotlib", "matplotlib.pyplot", "plt",
        "duckdb",
        "os", "sys", "json", "csv", "datetime", "time",
        "math", "statistics", "re", "pathlib", "io",
        "collections", "itertools", "functools", "operator",
        "warnings", "logging", "copy", "pickle", "gzip", "zipfile",
        "typing", "dataclasses", "enum", "sqlite3",
    }

    def __init__(self, output_dir: str = "outputs"):
        self.output_dir = os.path.abspath(output_dir)
        os.makedirs(self.output_dir, exist_ok=True)
        self.shell = InteractiveShell.instance()
        self._setup_chinese_font()
        self._setup_common_imports()
        self.image_counter = 0

    def _setup_chinese_font(self):
        try:
            matplotlib.use("Agg")
            plt.rcParams["font.sans-serif"] = ["SimHei", "DejaVu Sans", "Arial Unicode MS"]
            plt.rcParams["axes.unicode_minus"] = False
            self.shell.run_cell(
                """
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False
"""
            )
        except Exception as exc:
            print(f"设置中文字体失败: {exc}")

    def _setup_common_imports(self):
        common_imports = """
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import duckdb
import os
import json
from IPython.display import display
"""
        try:
            self.shell.run_cell(common_imports)
            from IPython.display import display
            self.shell.user_ns["display"] = display
        except Exception as exc:
            print(f"预导入库失败: {exc}")

    def _check_code_safety(self, code: str) -> tuple[bool, str]:
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return False, f"语法错误: {exc}"

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name not in self.ALLOWED_IMPORTS:
                        return False, f"不允许的导入: {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module not in self.ALLOWED_IMPORTS:
                    return False, f"不允许的导入: {node.module}"
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in ["exec", "eval", "__import__"]:
                    return False, f"不允许的函数调用: {node.func.id}"
        return True, ""

    def _format_table_output(self, obj: Any) -> str:
        if hasattr(obj, "shape") and hasattr(obj, "head"):
            rows, cols = obj.shape
            print(f"\n数据表形状: {rows}行 x {cols}列")
            print(f"列名: {list(obj.columns)}")
            if rows <= 15:
                return str(obj)
            head_part = obj.head(5)
            tail_part = obj.tail(5)
            return f"{head_part}\n...\n(省略 {rows-10} 行)\n...\n{tail_part}"
        return str(obj)

    def execute_code(self, code: str) -> Dict[str, Any]:
        is_safe, safety_error = self._check_code_safety(code)
        if not is_safe:
            return {"success": False, "output": "", "error": f"代码安全检查失败: {safety_error}", "variables": {}}

        vars_before = set(self.shell.user_ns.keys())
        try:
            with capture_output() as captured:
                result = self.shell.run_cell(code)

            if result.error_before_exec:
                return {"success": False, "output": captured.stdout, "error": f"执行前错误: {result.error_before_exec}", "variables": {}}
            if result.error_in_exec:
                return {"success": False, "output": captured.stdout, "error": f"执行错误: {result.error_in_exec}", "variables": {}}

            output = captured.stdout
            if result.result is not None:
                formatted_result = self._format_table_output(result.result)
                output += f"\n{formatted_result}"

            vars_after = set(self.shell.user_ns.keys())
            new_vars = vars_after - vars_before
            important_new_vars = {}
            for var_name in new_vars:
                if var_name.startswith("_"):
                    continue
                try:
                    var_value = self.shell.user_ns[var_name]
                    if hasattr(var_value, "shape"):
                        important_new_vars[var_name] = f"{type(var_value).__name__} with shape {var_value.shape}"
                    elif var_name == "session_output_dir":
                        important_new_vars[var_name] = str(var_value)
                except Exception:
                    pass

            return {"success": True, "output": output, "error": "", "variables": important_new_vars}
        except Exception as exc:
            return {
                "success": False,
                "output": captured.stdout if "captured" in locals() else "",
                "error": f"执行异常: {exc}",
                "variables": {},
            }

    def reset_environment(self):
        self.shell.reset()
        self._setup_common_imports()
        self._setup_chinese_font()
        plt.close("all")
        self.image_counter = 0

    def set_variable(self, name: str, value: Any):
        self.shell.user_ns[name] = value

    def get_environment_info(self) -> str:
        info_parts = []
        important_vars = {}
        for var_name, var_value in self.shell.user_ns.items():
            if var_name.startswith("_") or var_name in ["In", "Out", "get_ipython", "exit", "quit"]:
                continue
            try:
                if hasattr(var_value, "shape"):
                    important_vars[var_name] = f"{type(var_value).__name__} with shape {var_value.shape}"
                elif var_name == "session_output_dir":
                    important_vars[var_name] = str(var_value)
                elif isinstance(var_value, (int, float, str, bool)) and len(str(var_value)) < 100:
                    important_vars[var_name] = f"{type(var_value).__name__}: {var_value}"
            except Exception:
                continue

        if important_vars:
            info_parts.append("当前环境变量:")
            for var_name, var_info in important_vars.items():
                info_parts.append(f"- {var_name}: {var_info}")
        else:
            info_parts.append("当前环境已预装pandas, numpy, matplotlib等库")

        if "session_output_dir" in self.shell.user_ns:
            info_parts.append(f"图片保存目录: session_output_dir = '{self.shell.user_ns['session_output_dir']}'")
        return "\n".join(info_parts)


data_analysis_system_prompt = """你是一个专业的数据分析助手，运行在Jupyter Notebook环境中，能够根据用户需求生成和执行Python数据分析代码。

🎯 **重要指导原则**：
- 当需要执行Python代码（数据加载、分析、可视化）时，使用 `generate_code` 动作
- 当需要收集和分析已生成的图表时，使用 `collect_figures` 动作  
- 当所有分析工作完成，需要输出最终报告时，使用 `analysis_complete` 动作
- 每次响应只能选择一种动作类型，不要混合使用

目前jupyter notebook环境下有以下变量：
{notebook_variables}

✨ 核心能力：
1. 接收用户的自然语言分析需求
2. 按步骤生成安全的Python分析代码
3. 基于代码执行结果继续优化分析

🔧 Notebook环境特性：
- 你运行在IPython Notebook环境中，变量会在各个代码块之间保持
- 第一次执行后，pandas、numpy、matplotlib等库已经导入，无需重复导入
- 数据框(DataFrame)等变量在执行后会保留，可以直接使用
- 因此，除非是第一次使用某个库，否则不需要重复import语句

🚨 重要约束：
1. 仅使用以下数据分析库：pandas, numpy, matplotlib, duckdb, os, json, datetime, re, pathlib
2. 图片必须保存到指定的会话目录中，输出绝对路径，禁止使用plt.show()
4. 表格输出控制：超过15行只显示前5行和后5行
5. 强制使用SimHei字体：plt.rcParams['font.sans-serif'] = ['SimHei']
6. 输出格式严格使用YAML
7. 不能使用上述库之外的任何库
📁 输出目录管理：
- 本次分析使用UUID生成的专用目录（16进制格式），确保每次分析的输出文件隔离
- 会话目录格式：session_[32位16进制UUID]，如 session_a1b2c3d4e5f6789012345678901234ab
- 图片保存路径格式：os.path.join(session_output_dir, '图片名称.png')
- 使用有意义的中文文件名：如'营业收入趋势.png', '利润分析对比.png'
- 每个图表保存后必须使用plt.close()释放内存
- 输出绝对路径：使用os.path.abspath()获取图片的完整路径

📊 数据分析工作流程（必须严格按顺序执行）：

**阶段1：数据探索（使用 generate_code 动作）**
- 首次数据加载时尝试多种编码：['utf-8', 'gbk', 'gb18030', 'gb2312']
- 使用df.head()查看前几行数据
- 使用df.info()了解数据类型和缺失值
- 使用df.describe()查看数值列的统计信息
- **强制要求：必须先打印所有列名**：print("实际列名:", df.columns.tolist())
- **严禁假设列名**：绝对不要使用任何未经验证的列名，所有列名必须从df.columns中获取
- **列名使用规则**：在后续代码中引用列名时，必须使用df.columns中实际存在的列名

**阶段2：数据清洗和检查（使用 generate_code 动作）**
- **列名验证**：再次确认要使用的列名确实存在于df.columns中
- 检查关键列的数据类型（特别是日期列）
- 查找异常值和缺失值
- 处理日期格式转换
- 检查数据的时间范围和排序
- **错误预防**：每次使用列名前，先检查该列是否存在

**阶段3：数据分析和可视化（使用 generate_code 动作）**
- **列名安全使用**：只使用已经验证存在的列名进行计算
- **动态列名匹配**：如果需要找特定含义的列，使用模糊匹配或包含关键字的方式查找
- **智能图表选择**：根据数据类型和分析目标选择最合适的图表类型
  - 时间序列数据：使用线图(plot)展示趋势变化
  - 分类比较：使用柱状图(bar)比较不同类别的数值
  - 分布分析：使用直方图(hist)或箱型图(boxplot)
  - 相关性分析：使用散点图(scatter)或热力图(heatmap)
  - 占比分析：使用饼图(pie)或堆叠柱状图(stacked bar)
- **图表设计原则**：
  - 确保图表清晰易读，合理设置图表尺寸(figsize=(10,6)或更大)
  - 使用有意义的中文标题、坐标轴标签和图例
  - 对于金融数据，优先展示趋势、对比和关键指标
  - 数值过大时使用科学计数法或单位转换(如万元、亿元)
  - 合理设置颜色和样式，提高可读性
- 图片保存到会话专用目录中
- 每生成一个图表后，必须打印绝对路径

**阶段4：图片收集和分析（使用 collect_figures 动作）**
- 当已生成2-3个图表后，使用 collect_figures 动作
- 收集所有已生成的图片路径和信息
- 对每个图片进行详细的分析和解读

**阶段5：最终报告（使用 analysis_complete 动作）**
- 当所有分析工作完成后，生成最终的分析报告
- 包含对所有图片和分析结果的综合总结
"""

final_report_system_prompt = """你是一个专业的数据分析师，需要基于完整的分析过程生成最终的分析报告。

📝 分析信息：
分析轮数: {current_round}
输出目录: {session_output_dir}

{figures_summary}

代码执行结果摘要:
{code_results_summary}

📊 报告生成要求：
报告应使用markdown格式，确保结构清晰；需要包含对所有生成图片的详细分析和说明；总结分析过程中的关键发现；提供有价值的结论和建议；内容必须专业且逻辑性强。**重要提醒：图片引用必须使用相对路径格式 `![图片描述](./图片文件名.png)`**

🖼️ 图片路径格式要求：
报告和图片都在同一目录下，必须使用相对路径。格式为`![图片描述](./图片文件名.png)`，例如`![营业总收入趋势](./营业总收入趋势.png)`。禁止使用绝对路径，这样可以确保报告在不同环境下都能正确显示图片。

🎯 响应格式要求：
必须严格使用以下YAML格式输出：

```yaml
action: "analysis_complete"
final_report: |
  # 数据分析报告
  
  ## 分析概述
  [概述本次分析的目标和范围]
  
  ## 数据分析过程
  [总结分析的主要步骤]
  
  ## 关键发现
  [描述重要的分析结果，使用段落形式而非列表]
  
  ## 图表分析
  
  ### [图表标题]
  ![图表描述](./图片文件名.png)
  
  [对图表的详细分析，使用连续的段落描述，避免使用分点列表]
  
  ### [下一个图表标题]
  ![图表描述](./另一个图片文件名.png)
  
  [对图表的详细分析，使用连续的段落描述]
  
  ## 结论与建议
  [基于分析结果提出结论和投资建议，使用段落形式表达]
```
"""

final_report_system_prompt_absolute = """你是一个专业的数据分析师，需要基于完整的分析过程生成最终的分析报告。

📝 分析信息：
分析轮数: {current_round}
输出目录: {session_output_dir}

{figures_summary}

代码执行结果摘要:
{code_results_summary}

📊 报告生成要求：
报告应使用markdown格式，确保结构清晰；需要包含对所有生成图片的详细分析和说明；总结分析过程中的关键发现；提供有价值的结论和建议；内容必须专业且逻辑性强。**重要提醒：图片引用必须使用绝对路径格式显示完整路径信息**

🖼️ 图片路径格式要求：
使用完整的绝对路径引用图片，格式为`![图片描述](绝对路径)`。这种方式可以显示图片的完整存储位置，便于文件管理和后续处理。所有图片路径都必须是完整的绝对路径，包含完整的目录结构。

🎯 响应格式要求：
必须严格使用以下YAML格式输出：

```yaml
action: "analysis_complete"
final_report: |
  # 数据分析报告
  
  ## 分析概述
  [概述本次分析的目标和范围]
  
  ## 数据分析过程
  [总结分析的主要步骤]
  
  ## 关键发现
  [描述重要的分析结果，使用段落形式而非列表]
  
  ## 图表分析
  
  ### [图表标题]
  ![图表描述](完整的绝对路径/图片文件名.png)
  
  [对图表的详细分析，使用连续的段落描述，避免使用分点列表]
  
  ### [下一个图表标题]
  ![图表描述](完整的绝对路径/另一个图片文件名.png)
  
  [对图表的详细分析，使用连续的段落描述]
  
  ## 结论与建议
  [基于分析结果提出结论和投资建议，使用段落形式表达]

```
"""


class DataAnalysisAgent:
    """数据分析智能体（精简版）"""

    def __init__(self, llm_config: LLMConfig = None, output_dir: str = "outputs", max_rounds: int = 20, absolute_path: bool = False):
        self.config = llm_config
        self.llm = LLMHelper(self.config)
        self.base_output_dir = output_dir
        self.max_rounds = max_rounds
        self.conversation_history = []
        self.analysis_results = []
        self.current_round = 0
        self.session_output_dir = None
        self.executor = None
        self.absolute_path = absolute_path

    def _handle_analysis_complete(self, response: str, yaml_data: Dict[str, Any]) -> Dict[str, Any]:
        final_report = yaml_data.get("final_report", "分析完成，无最终报告")
        return {"action": "analysis_complete", "final_report": final_report, "response": response, "continue": False}

    def _handle_collect_figures(self, response: str, yaml_data: Dict[str, Any]) -> Dict[str, Any]:
        figures_to_collect = yaml_data.get("figures_to_collect", [])
        collected_figures = []
        for figure_info in figures_to_collect:
            file_path = figure_info.get("file_path", "")
            if file_path and os.path.exists(file_path):
                collected_figures.append(figure_info)
        return {"action": "collect_figures", "collected_figures": collected_figures, "response": response, "continue": True}

    def _handle_generate_code(self, response: str, yaml_data: Dict[str, Any]) -> Dict[str, Any]:
        code = yaml_data.get("code", "") or extract_code_from_response(response) or ""
        if not code:
            return {"action": "invalid_response", "error": "响应中缺少可执行代码", "response": response, "continue": True}
        result = self.executor.execute_code(code)
        feedback = format_execution_result(result)
        return {"action": "generate_code", "code": code, "result": result, "feedback": feedback, "response": response, "continue": True}

    def _process_response(self, response: str) -> Dict[str, Any]:
        try:
            yaml_data = self.llm.parse_yaml_response(response)
            action = yaml_data.get("action", "generate_code")
            if action == "analysis_complete":
                return self._handle_analysis_complete(response, yaml_data)
            if action == "collect_figures":
                return self._handle_collect_figures(response, yaml_data)
            return self._handle_generate_code(response, yaml_data)
        except Exception:
            return self._handle_generate_code(response, {})

    def _build_conversation_prompt(self) -> str:
        prompt_parts = []
        for msg in self.conversation_history:
            role = msg["role"]
            content = msg["content"]
            prompt_parts.append(f"{'用户' if role == 'user' else '助手'}: {content}")
        return "\n\n".join(prompt_parts)

    def _build_final_report_prompt(self, all_figures: List[Dict[str, Any]]) -> str:
        figures_summary = "\n本次分析未生成图片。\n"
        if all_figures:
            figures_summary = "\n生成的图片及分析:\n"
            for i, figure in enumerate(all_figures, 1):
                filename = figure.get("filename", "未知文件名")
                figures_summary += f"{i}. {filename}\n"
                figures_summary += f"   路径: ./{filename}\n"
                figures_summary += f"   描述: {figure.get('description', '无描述')}\n"
                figures_summary += f"   分析: {figure.get('analysis', '无分析')}\n\n"

        code_results_summary = ""
        success_code_count = 0
        for result in self.analysis_results:
            if result.get("action") != "collect_figures" and result.get("code"):
                exec_result = result.get("result", {})
                if exec_result.get("success"):
                    success_code_count += 1
                    code_results_summary += f"代码块 {success_code_count}: 执行成功\n"
                    if exec_result.get("output"):
                        code_results_summary += f"输出: {exec_result.get('output')[:]}\n\n"

        pre_prompt = final_report_system_prompt_absolute if self.absolute_path else final_report_system_prompt
        return pre_prompt.format(
            current_round=self.current_round,
            session_output_dir=self.session_output_dir,
            figures_summary=figures_summary,
            code_results_summary=code_results_summary,
        )

    def _generate_final_report(self) -> Dict[str, Any]:
        all_figures = []
        for result in self.analysis_results:
            if result.get("action") == "collect_figures":
                all_figures.extend(result.get("collected_figures", []))

        final_report_prompt = self._build_final_report_prompt(all_figures)
        response = self.llm.call(
            prompt=final_report_prompt,
            system_prompt="你将会接收到一个数据分析任务的最终报告请求，请根据提供的分析结果和图片信息生成完整的分析报告。",
            max_tokens=16384,
        )

        try:
            yaml_data = self.llm.parse_yaml_response(response)
            final_report_content = yaml_data.get("final_report", "报告生成失败")
        except Exception:
            final_report_content = response

        if all_figures:
            appendix_section = "\n\n## 附件清单\n\n"
            appendix_section += "本报告包含以下图片附件：\n\n"
            for i, figure in enumerate(all_figures, 1):
                filename = figure.get("filename", "未知文件名")
                description = figure.get("description", "无描述")
                analysis = figure.get("analysis", "无分析")
                file_path = figure.get("file_path", "")
                appendix_section += f"{i}. **{filename}**\n"
                appendix_section += f"   - 描述：{description}\n"
                appendix_section += f"   - 细节分析：{analysis}\n"
                appendix_section += f"   - 文件路径：{file_path if self.absolute_path else './' + filename}\n\n"
            final_report_content += appendix_section

        report_file_path = os.path.join(self.session_output_dir, "最终分析报告.md")
        with open(report_file_path, "w", encoding="utf-8") as f:
            f.write(final_report_content)

        return {
            "session_output_dir": self.session_output_dir,
            "total_rounds": self.current_round,
            "analysis_results": self.analysis_results,
            "collected_figures": all_figures,
            "conversation_history": self.conversation_history,
            "final_report": final_report_content,
            "report_file_path": report_file_path,
        }

    def analyze(self, user_input: str, files: List[str] = None) -> Dict[str, Any]:
        self.conversation_history = []
        self.analysis_results = []
        self.current_round = 0
        self.session_output_dir = create_session_output_dir(self.base_output_dir, user_input)
        self.executor = CodeExecutor(self.session_output_dir)
        self.executor.set_variable("session_output_dir", self.session_output_dir)

        initial_prompt = f"用户需求: {user_input}"
        if files:
            initial_prompt += f"\n数据文件: {', '.join(files)}"
        self.conversation_history.append({"role": "user", "content": initial_prompt})

        while self.current_round < self.max_rounds:
            self.current_round += 1
            notebook_variables = self.executor.get_environment_info()
            formatted_system_prompt = data_analysis_system_prompt.format(notebook_variables=notebook_variables)
            response = self.llm.call(prompt=self._build_conversation_prompt(), system_prompt=formatted_system_prompt)
            process_result = self._process_response(response)
            if not process_result.get("continue", True):
                break
            self.conversation_history.append({"role": "assistant", "content": response})
            if process_result["action"] == "generate_code":
                self.conversation_history.append({"role": "user", "content": f"代码执行反馈:\n{process_result.get('feedback', '')}"})
                self.analysis_results.append({"round": self.current_round, "code": process_result.get("code", ""), "result": process_result.get("result", {}), "response": response})
            elif process_result["action"] == "collect_figures":
                collected_figures = process_result.get("collected_figures", [])
                feedback = f"已收集 {len(collected_figures)} 个图片及其分析"
                self.conversation_history.append({"role": "user", "content": f"图片收集反馈:\n{feedback}\n请继续下一步分析。"})
                self.analysis_results.append({"round": self.current_round, "action": "collect_figures", "collected_figures": collected_figures, "response": response})

        return self._generate_final_report()


def create_agent(llm_config: LLMConfig = None, output_dir: str = "outputs", max_rounds: int = 30, absolute_path: bool = False) -> DataAnalysisAgent:
    if llm_config is None:
        raise ValueError("llm_config 不能为空")
    return DataAnalysisAgent(llm_config=llm_config, output_dir=output_dir, max_rounds=max_rounds, absolute_path=absolute_path)


def quick_analysis(query: str, files: List[str] = None, llm_config: LLMConfig = None, output_dir: str = "outputs", max_rounds: int = 10, absolute_path: bool = False) -> Dict[str, Any]:
    agent = create_agent(llm_config=llm_config, output_dir=output_dir, max_rounds=max_rounds, absolute_path=absolute_path)
    return agent.analyze(query, files)
