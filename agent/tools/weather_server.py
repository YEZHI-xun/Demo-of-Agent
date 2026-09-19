"""天气/位置 MCP Server（HTTP 传输，常驻进程）"""
import os
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import FastMCP
import httpx

# weather_server 为独立进程，需自行加载项目根目录 .env（parents[2]: tools → agent → 项目根）
load_dotenv(Path(__file__).resolve().parents[2] / ".env", encoding="utf-8")

mcp = FastMCP(name="weather")

# 读取环境配置的高德Web服务Key
AMAP_KEY = os.getenv("AMAP_KEY")
if not AMAP_KEY:
    raise RuntimeError("未配置 AMAP_KEY：请在项目根目录 .env 中设置后重启 weather_server")
AMAP_WEATHER_URL = os.getenv("AMAP_WEATHER_URL")
AMAP_IP_URL = os.getenv("AMAP_IP_URL")

CITY_ADCODE = {
    "北京": "110000", "上海": "310000", "广州": "440100", "深圳": "440300",
    "杭州": "330100", "合肥": "340100", "南京": "320100", "成都": "510100",
    "武汉": "420100", "西安": "610100", "重庆": "500000", "天津": "120000",
}

@mcp.tool
def get_weather(city: str) -> str:
    """获取指定城市的天气，以消息字符串的形式返回"""
    params = {
        "key": AMAP_KEY,
        "city": CITY_ADCODE.get(city, city),   # 优先 adcode，查不到用城市名
        "extensions": "base",                  # base=实况天气(lives)，all=预报天气(forecasts)
    }
    try:
        resp = httpx.get(AMAP_WEATHER_URL, params=params, timeout=10)
        data = resp.json()
        if data.get("status") != "1" or not data.get("lives"):
            return f"城市{city}天气查询失败：{data.get('info', '未知错误')}"
        live = data["lives"][0]
        return (f"城市{city}当前天气为{live.get('weather')}，气温{live.get('temperature')}摄氏度，"
                f"湿度{live.get('humidity')}%，{live.get('winddirection')}风{live.get('windpower')}级")
    except Exception as e:
        return f"城市{city}天气查询失败：{str(e)}"

@mcp.tool
def get_user_location() -> str:
    """获取用户所在城市的名称，以纯字符串形式返回"""
    try:
        # 不传 ip：自动定位请求来源出口 IP
        resp = httpx.get(AMAP_IP_URL, params={"key": AMAP_KEY}, timeout=10)
        data = resp.json()
        if data.get("status") == "1" and data.get("city"):
            return data["city"]
        return data.get("province") or "未知位置"
    except Exception as e:
        return f"位置查询失败：{str(e)}"

if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=18001)