import asyncio
from langchain.agents import create_agent
from model.model_factory import chat_model
from utils.prompt_loader import load_system_prompts
from agent.tools.agent_tools import (rag_summarize, get_user_id,
                                     get_current_month, fetch_external_data, fill_context_for_report)
from agent.tools.middleware import monitor_tool, log_before_model, report_prompt_switch
from utils.mcp_tools import load_mcp_tools_sync

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

    def execute_stream(self, query: str, session_id: str = "default"):
        input_dict = {
            "messages": [
                {"role": "user", "content": query},
            ]
        }
        # 保持同步流式 + context（report / session_id）不变
        for chunk in self.agent.stream(
                input_dict,
                stream_mode="values",
                context={"report": False, "session_id": session_id}):
            latest_message = chunk["messages"][-1]
            if latest_message.content:
                yield latest_message.content.strip() + "\n"


if __name__ == '__main__':
    agent = ReactAgent()

    for chunk in agent.execute_stream("给我生成我的使用报告"):
        print(chunk, end="", flush=True)
