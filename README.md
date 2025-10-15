# GitHub Issue 自动分诊 Agent

本项目构建一个基于 LangChain 的智能 Agent，通过硅基流动提供的DeepSeek-V3大语言模型，模拟自动化处理 GitHub Issue 的分诊（Triage）流程。该 Agent 能够自主调用工具来阅读、分类 Issue，并为其分配合适的负责人。

## 功能特性
- **任务分解**: Agent 能将“分诊”这个复杂任务自动分解为阅读、分类、分配步骤。
- **工具调用**: Agent 拥有三个核心工具：`read_issue_content`, `categorize_issue`, `assign_developer`。
- **智能分类**: 核心的 `categorize_issue` 工具利用大语言模型（LLM）实现对 Issue 内容的智能分类。
- **可观察性**: Agent 的完整执行轨迹（Thought Process）会被打印出来，便于理解和调试其决策逻辑。

## 安装依赖

1.  **克隆项目**
    ```bash
    git clone <repo-url>
    ```

2. **安装所需库**
    项目依赖项已在 `requirements.txt` 中列出。
    ```bash
    pip install -r requirements.txt
    ```

## 配置 API Key

本项目需要使用 硅基流动的API。请按照以下步骤进行配置：

1.  在项目根目录下创建一个名为 `.env` 的文件。
2.  在该文件中添加你的 Silicon API Key，格式如下：
    ```
    SILICONFLOW_API_KEY="sk-SiliconFlowAIKey"
    SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
    ```
    请将 `sk-SiliconFlowAIKey` 替换为你自己的密钥。

3. 在该文件中添加你的 Langsmith API Key，格式如下：

   ```
   Langsmith_API_KEY="lsv2_LangsmithAPIKEY"
   ```

   请将 `lsv2_LangsmithAPIKEY` 替换为你自己的密钥。

## 如何运行

直接运行主脚本即可启动 Agent 并处理预设的两个 Issue 示例。

```bash
python github_issue_react_agent.py
```

您将看到 Agent 对一个 "Bug" 和一个 "Feature Request" 的完整处理流程和最终结果。

### 示例 Issue JSON
脚本中内置以下示例，可以修改它们来测试 Agent 的表现：
```json
// 示例 1: Bug
{
    "title": "登录按钮在 Safari 浏览器上点击无效",
    "body": "在最新的 macOS Sonoma 和 Safari 17.1 版本下，用户无法点击登录页面的主登录按钮...",
    "labels": ["web", "login"],
    "author": "user-a"
}

// 示例 2: Feature Request
{
    "title": "希望增加导出数据为 CSV 的功能",
    "body": "目前的数据报表只能在线查看，非常不方便。我们希望能在报表页面的右上角增加一个“导出为 CSV”的按钮...",
    "labels": ["reporting", "data"],
    "author": "user-b"
}
```

## 设计思路说明

### 1. `categorize_issue` 工具的 Prompt/Description 设计

为工具编写一个清晰、准确的描述 (即函数的 docstring) 是 Agent 设计中最关键的一环，因为它直接决定了 Agent 何时以及如何使用这个工具。

我的设计思路如下：

- **明确工具的核心功能**: 描述的第一句话 `[核心工具] 将 Issue 的文本内容分类。` 开门见山，并用标签强调其重要性，让 Agent 优先考虑。
- **定义清晰的输入/输出**: `此工具接收 Issue 的完整标题和描述作为输入字符串...` 和 `...必须将其归类到以下三个预定义类别之一：'Bug', 'Feature Request', 'Question'`。这为 Agent 提供精确的调用规范。
- **使用强约束指令**: `请务必从这三个选项中选择一个返回。` 这句话至关重要。通过强调和明确的指令，限制 LLM 的“自由发挥”，确保输出的稳定性和可预测性，这对于后续的程序化处理（如调用 `assign_developer`）是必需的。

这个描述就像是给 Agent 的“工具使用说明书”，写得越好，Agent 的表现就越可靠。

### 2. Agent 执行轨迹（Thought Process）分析

以下是一次处理 "Bug" Issue 的完整执行轨迹及其分析：

```
> Entering new AgentExecutor chain...

 # 思考过程 1
Thought: I need to understand the issue content first, then categorize it, and finally assign a developer based on the category.
 
 # 动作 1
Action: read_issue_content
Action Input: {"title": "登录按钮在 Safari 浏览器上点击无效", "body": "在最新的 macOS Sonoma 和 Safari 17.1 版本下，用户无法点击登录页面的主登录按钮。控制台没有报错，按钮的 CSS `pointer-events` 也是正常的。在 Chrome 和 Firefox 上测试没有问题。", "labels": ["web", "login"], "author": "user-a"}


```
**分析**: Agent 的第一步完全正确。它理解输入是 JSON，并意识到自己的首要任务是“理解内容”。因此，它准确地选择 `read_issue_content` 工具，并正确地将 JSON 对象作为参数传入。

*(注：现代的 `create_tool_calling_agent` 会将思考和调用合并，轨迹更简洁。在 ReAct 风格中，这里会先有一个 Thought，再有一个 Action。)*

```
 # 观察 1 (上一步工具的返回结果)
 Observation:
 Issue 标题: 
 登录按钮在 Safari 浏览器上点击无效
 Issue 内容:
 在最新的 macOS Sonoma 和 Safari 17.1 版本下，用户无法点击登录页面的主登录按钮。控制台没有报错，按钮的 CSS `pointer-events` 也是正常的。在 Chrome 和 Firefox 上测试没有问题。

 # 思考过程 2
 Thought: Now that I have the issue content in a readable format, I need to categorize it.
 # 动作 2
 Action: categorize_issue
 Action Input: Issue 标题: 登录按钮在 Safari 浏览器上点击无效
 Issue 内容: 在最新的 macOS Sonoma 和 Safari 17.1 版本下，用户无法点击登录页面的主登录按钮。控制台没有报错，按钮的 CSS `pointer-events` 也是正常的。在 Chrome 和 Firefox 上测试没有问题。
```
**分析**: Agent 接收到 `read_issue_content` 的输出后，进入下一步思考。它正确地判断出“现在需要分类”，并选择 `categorize_issue` 工具。它还知道应该将上一步的输出作为这一步的输入，展现清晰的逻辑链条。

```
 # 观察 2
 Observation: Bug

 # 思考过程 3
 Thought: The issue has been categorized as a 'Bug'. Now I need to assign a developer who specializes in fixing bugs.
 
 # 动作 3
 Action: assign_developer
 Action Input: Bug
```
**分析**: 得到分类 "Bug" 后，Agent 的目标变为“分配开发者”。它再次正确地选择 `assign_developer` 工具，并将 "Bug" 作为参数。

```
 # 观察 3
 Observation: 张三

 # 思考过程 4
 Thought: I now know the final answer
 # 最终回答
 Final Answer: The issue "登录按钮在 Safari 浏览器上点击无效" has been categorized as a 'Bug' and assigned to developer 张三 for resolution.

> Finished chain.
```
**分析**: Agent 在完成所有工具调用后，意识到任务已接近尾声。它回顾系统 Prompt 中对最终输出格式的要求，并整合所有信息（"Bug" 和 "张三"），生成格式完全正确的最终答案。整个过程逻辑清晰，任务完成度高。

### 3. 如何增加一个新的分类（例如 "Documentation"）？

我的代码设计具有良好的模块化和可扩展性。要增加一个新的 "Documentation" 分类，只需修改两处地方，完全不需要触碰核心的 Agent 构建逻辑：

1.  **修改 `categorize_issue` 工具**: 新增Documentation
    
    ```python
    @tool
    def categorize_issue(text_content: str) -> str:
        # 修改函数描述-新增Documentation
        """
        ...归类到以下四个预定义类别之一：'Bug', 'Feature Request', 'Question', 'Documentation'。
        请务必从这四个选项中选择一个返回。
        """
        # 修改提示词-新增Documentation
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "你是一个精准的文本分类器。你的任务是将用户输入的文本内容分类为 'Bug'、'Feature Request' 或 'Question' 或 'Documentation'。请只返回这四个词中的一个，不要添加任何额外的解释。"),
            ("human", "{content}")
        ])
        # 修改内部逻辑-新增Documentation
        category = "Unknown"  # 默认
        if "Bug" in result:
            category = "Bug"
        elif "Feature Request" in result:
            category = "Feature Request"
        elif "Question" in result:
            category = "Question"
        elif "Documentation" in result:
            category = "Documentation"
        # ...
    ```

2.  **更新 `DEVELOPER_MAP` 字典**: 为新类别添加一个负责人。
    ```python
    DEVELOPER_MAP = {
        "Bug": "张三",
        "Feature Request": "李四",
        "Question": "王五",
        "Documentation": "赵六" # 新增条目
    }
    ```

完成这两处简单的修改后，Agent 将自动具备处理 "Documentation" 类型 Issue 的能力。
这是将具体业务逻辑（分类列表、开发者名单）封装在工具中，而不是硬编码在 Agent 的主 Prompt 里的好处。