import asyncio
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage
from model.model_factory import chat_model
from utils.prompt_loader import load_system_prompts
from agent.tools.agent_tools import (rag_summarize, get_user_id,
                                     get_current_month, fetch_external_data, fill_context_for_report)
from agent.tools.middleware import monitor_tool, log_before_model, report_prompt_switch
from utils.mcp_tools import load_mcp_tools_sync
from rag.file_history_store import get_history

# MCP Server 地址（HTTP 常驻进程）
MCP_WEATHER_URL = "http://127.0.0.1:18001/mcp"


class ReactAgent:
    def __init__(self):
        # 构建阶段：一次性连接 MCP Server 发现工具并同步包装（随后可缓存，供多轮调用）
        mcp_tools = asyncio.run(load_mcp_tools_sync(MCP_WEATHER_URL))

        local_tools = [rag_summarize, get_user_id, get_current_month,
                       fetch_external_data, fill_context_for_report]

        self.agent = create_agent(
            model=chat_model,
            system_prompt=load_system_prompts(),
            tools=mcp_tools + local_tools,
            middleware=[monitor_tool, log_before_model, report_prompt_switch],
        )

    # 将用户查询流式执行并返回结果
    def execute_stream(self, query: str, session_id: str = "default"):
        # ===== 记忆：加载当前会话的历史消息 =====
        # 历史持久化在 chat_history/<session_id> 文件中，TODO 可优化为 LangGraph 的 checkpointer；
        # 每次调用都会触发目录检查，目录/文件被删除后可自动重建
        history = get_history(session_id)

        input_dict = {
            # 历史消息 + 本轮提问一并提交，让模型拥有多轮对话上下文
            "messages": history.messages + [HumanMessage(content=query)],
        }
        # 保持同步流式 + context（report / session_id）不变
        latest_message = None
        for chunk in self.agent.stream(
                input_dict,
                stream_mode="values",
                context={"report": False, "session_id": session_id}):
            latest_message = chunk["messages"][-1]
            if latest_message.content:
                yield latest_message.content.strip() + "\n"

        # 只保存干净的问答对；工具调用消息不入库，避免后续轮次因为tool_calls / ToolMessage 配对缺失而报错
        if (isinstance(latest_message, AIMessage)
                and latest_message.content
                and not latest_message.tool_calls):
            history.add_messages([
                HumanMessage(content=query),
                AIMessage(content=latest_message.content),
            ])

