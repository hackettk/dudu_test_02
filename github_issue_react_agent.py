import os
import json

from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain.tools import tool
from dotenv import load_dotenv
from langsmith import Client

# --- 1. 环境与配置 ---
# 加载 .env 文件中的环境变量
load_dotenv()

# 从环境变量中读取硅基流动的配置
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY")
SILICONFLOW_BASE_URL = os.getenv("SILICONFLOW_BASE_URL")

# 从环境变量中读取 LANGSMITH_API_KEY
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")

if not SILICONFLOW_API_KEY or not SILICONFLOW_BASE_URL:
    raise ValueError("请确保 .env 文件中已配置 SILICONFLOW_API_KEY 和 SILICONFLOW_BASE_URL")



# 初始化大语言模型 (LLM)
# 我们将为 Agent 和 categorize_issue 工具分别创建 LLM 实例，以保持逻辑清晰
llm = ChatOpenAI(model_name="deepseek-ai/DeepSeek-V3", api_key=SILICONFLOW_API_KEY, base_url=SILICONFLOW_BASE_URL, temperature=0)

# 初始化langsmith客户端
langsmith_client = Client(api_key=LANGSMITH_API_KEY)

# --- 2. 定义 Agent 的工具 (Tools) ---

# 预设的开发者名单
DEVELOPER_MAP = {
    "Bug": "张三",
    "Feature Request": "李四",
    "Question": "王五"
}


@tool
def read_issue_content(issue_data: str) -> str:
    """
    当需要理解一个 GitHub Issue 的具体内容时，使用此工具。
    它会从原始 Issue JSON 数据中提取标题(title)和描述(body)，并格式化为易于阅读的文本。
    输入必须是一个有效的 JSON 格式的字符串。
    """
    try:
        # 在工具内部将字符串解析为字典
        data = json.loads(issue_data)
        title = data.get("title", "")
        body = data.get("body", "")
        return f"\n\nIssue 标题: \n{title}\nIssue 内容:\n{body}\n\n"
    except json.JSONDecodeError:
        return "\n\n错误：输入不是一个有效的 JSON 字符串。\n\n"


@tool
def categorize_issue(text_content: str) -> str:
    """
    [核心工具] 将 Issue 的文本内容分类。
    此工具接收 Issue 的完整标题和描述作为输入字符串，并必须将其归类到以下三个预定义类别之一：'Bug', 'Feature Request', 'Question'。
    请务必从这三个选项中选择一个返回。
    """
    # 这个工具内部调用 LLM 来完成分类任务，使其成为一个 "智能工具"
    categorizer_llm = ChatOpenAI(model_name="deepseek-ai/DeepSeek-V3", api_key=SILICONFLOW_API_KEY, base_url=SILICONFLOW_BASE_URL, temperature=0)
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "你是一个精准的文本分类器。你的任务是将用户输入的文本内容分类为 'Bug'、'Feature Request' 或 'Question'。请只返回这三个词中的一个，不要添加任何额外的解释。"),
        ("human", "{content}")
    ])
    chain = prompt | categorizer_llm
    # .content 用于从 AIMessage 对象中提取字符串结果
    result = chain.invoke({"content": text_content}).content
    # 清理可能的意外输出
    category = "Unknown"  # 默认
    if "Bug" in result:
        category = "Bug"
    elif "Feature Request" in result:
        category = "Feature Request"
    elif "Question" in result:
        category = "Question"

    # 在返回字符串的末尾添加一个换行符
    return f"\n\n{category}\n\n"  # <--- 修改点


@tool
def assign_developer(category: str) -> str:
    """
    根据 Issue 的分类结果，分配一个合适的开发者。
    输入必须是 'Bug'、'Feature Request' 或 'Question' 中的一个。
    工具会返回被分配的开发者的名字和专长。
    """
    developer = DEVELOPER_MAP.get(category.strip(), "未找到合适的开发者，请手动分配。")
    return f"\n\n{developer}\n\n"  # <--- 修改点


# --- 3. 构建 Agent 执行逻辑 ---
def build_react_agent():
    """构建并返回一个配置好的 Agent Executor"""
    tools = [read_issue_content, categorize_issue, assign_developer]

    # 1. 拉取 ReAct Prompt 模板
    # hwchase17/react 是 LangChain 官方提供的一个经过验证的 ReAct prompt
    prompt = langsmith_client.pull_prompt("hwchase17/react", include_model=True)

    # 2. 创建 ReAct Agent
    # 这个 agent 知道如何解析 LLM 的输出，以分离出 Thought 和 Action
    agent = create_react_agent(llm, tools, prompt)

    # 创建 Agent 执行器
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,  # 设为 True 以打印详细的思考过程
        handle_parsing_errors=True  # 处理潜在的解析错误
    )

    return agent_executor

# --- 4. 主程序 ---

if __name__ == "__main__":
    # 实例化 Agent
    triage_agent = build_react_agent()

    # 模拟的 Issue JSON 对象 1 (Bug)
    sample_issue_bug = {
        "title": "登录按钮在 Safari 浏览器上点击无效",
        "body": "在最新的 macOS Sonoma 和 Safari 17.1 版本下，用户无法点击登录页面的主登录按钮。控制台没有报错，按钮的 CSS `pointer-events` 也是正常的。在 Chrome 和 Firefox 上测试没有问题。",
        "labels": ["web", "login"],
        "author": "user-a"
    }

    # 模拟的 Issue JSON 对象 2 (Feature Request)
    sample_issue_feature = {
        "title": "希望增加导出数据为 CSV 的功能",
        "body": "目前的数据报表只能在线查看，非常不方便。我们希望能在报表页面的右上角增加一个“导出为 CSV”的按钮，方便我们进行离线的数据分析和归档。",
        "labels": ["reporting", "data"],
        "author": "user-b"
    }

    print("\n" + "=" * 50)
    print("案例一：处理一个 Bug Report")
    print("=" * 50)

    # 调用 Agent 执行分诊任务
    # LangChain Agent 的输入通常是一个字典
    result_bug = triage_agent.invoke({"input": json.dumps(sample_issue_bug, ensure_ascii=False)})

    print("\n--- 最终分诊结果 ---")
    print(result_bug["output"])
    print("=" * 50)

    print("\n" + "=" * 50)
    print("案例二：处理一个 Feature Request")
    print("=" * 50)

    result_feature = triage_agent.invoke({"input": json.dumps(sample_issue_feature, ensure_ascii=False)})

    print("\n--- 最终分诊结果 ---")
    print(result_feature["output"])
    print("=" * 50)