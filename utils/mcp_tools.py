"""
MCP 工具同步包装层
解决：MCPAdapter 返回的异步工具无法被原项目同步 agent 链路直接调用的问题。
方案：每个异步工具包装为「新线程内 asyncio.run」的同步工具。
     线程内没有运行中的事件循环，asyncio.run 天然安全；
     HTTP 传输下每次调用独立连接，不依赖构建时的事件循环。
"""
import asyncio
import threading
from typing import Any

from langchain.mcp import MCPAdapter
from langchain_core.tools import StructuredTool


def _extract_text(content: Any) -> str:
    """MCP 工具返回 content blocks（list[dict]），抽取 text 拼接为纯字符串"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(block.get("text", "") for block in content if block.get("type") == "text")
    return str(content)


def to_sync_tool(async_tool: StructuredTool) -> StructuredTool:
    """把 MCP 异步工具包装为同步工具（保持 name/description/args_schema 不变）"""
    async def _ainvoke(**kwargs: Any) -> str:
        return _extract_text(await async_tool.ainvoke(kwargs))

    def _func(**kwargs: Any) -> str:
        box: dict[str, Any] = {}

        def _runner():
            box["result"] = asyncio.run(_ainvoke(**kwargs))

        t = threading.Thread(target=_runner)
        t.start()
        t.join()
        return box["result"]

    return StructuredTool.from_function(
        func=_func,
        name=async_tool.name,
        description=async_tool.description,
        args_schema=async_tool.args_schema,
    )


async def load_mcp_tools_sync(mcp_server_url: str) -> list[StructuredTool]:
    """连接 MCP Server（HTTP），发现工具并同步包装，返回可被 create_agent 使用的工具列表"""
    async with MCPAdapter(mcp_server_url) as adapter:
        mcp_tools = await adapter.list_tools()
        return [to_sync_tool(t) for t in mcp_tools]