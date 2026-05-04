"""
# Kimi 联网搜索插件

基于 Moonshot AI Kimi 模型内置 $web_search 工具的联网搜索插件，
为 AI 提供实时信息获取能力。

配置 Moonshot AI API Key 后即可使用。
"""

import json
import time
from typing import Any, Dict

from pydantic import Field

from nekro_agent.api import core
from nekro_agent.api.plugin import ConfigBase, NekroPlugin, SandboxMethodType
from nekro_agent.api.schemas import AgentCtx

kimi_search_plugin = NekroPlugin(
    name="Kimi联网搜索插件",
    module_name="kimi_search_plugin",
    description="基于 Moonshot AI Kimi 模型内置 $web_search 工具的第三方联网搜索插件，支持实时信息获取",
    version="0.1.1",
    author="dirac",
    url="https://github.com/1A7432/nekro_agent_kimi_search",
)


@kimi_search_plugin.mount_config()
class KimiSearchConfig(ConfigBase):
    """Kimi 联网搜索配置"""

    API_KEY: str = Field(
        default="",
        title="Moonshot AI API密钥",
        description="Moonshot AI API 密钥 <a href='https://platform.moonshot.ai/' target='_blank'>获取地址</a>",
        json_schema_extra={"is_secret": True},
    )
    BASE_URL: str = Field(
        default="https://api.moonshot.cn/v1",
        title="API 基础URL",
        description="Moonshot AI API 基础 URL，一般不需要修改",
    )
    MODEL: str = Field(
        default="kimi-k2-0905-preview",
        title="使用的模型",
        description="用于联网搜索的 Kimi 模型，推荐使用 kimi-k2.6（支持长上下文）",
    )
    THROTTLE_TIME: int = Field(
        default=10,
        title="搜索冷却时间(秒)",
        description="同一查询在此时间内重复搜索将被阻止",
    )
    MAX_TOKENS: int = Field(
        default=32768,
        title="最大返回Token数",
        description="搜索结果的最大 Token 数量",
    )


# 获取配置
config: KimiSearchConfig = kimi_search_plugin.get_config(KimiSearchConfig)

# 缓存变量
_last_query = None
_last_call_time = 0


def _web_search_impl(arguments: Dict[str, Any]) -> Any:
    """
    在使用 Moonshot AI 提供的 $web_search 工具时，只需要原封不动返回 arguments 即可，
    不需要额外的处理逻辑。这是因为 $web_search 是 Kimi 内置函数，由 Kimi 模型执行。
    """
    return arguments


async def _chat_with_web_search(query: str) -> str:
    """执行带联网搜索的对话"""
    import httpx

    api_key = config.API_KEY
    if not api_key:
        return "[Kimi] 未配置 API Key，请在插件设置中配置 Moonshot AI API Key"

    proxy = core.config.DEFAULT_PROXY
    if proxy and not proxy.startswith("http"):
        proxy = f"http://{proxy}"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

    # 构造消息
    messages = [
        {
            "role": "system",
            "content": "你是 Kimi，一个由 Moonshot AI 提供的人工智能助手。",
        },
        {"role": "user", "content": query},
    ]

    try:
        async with httpx.AsyncClient(proxy=proxy, timeout=120.0) as client:
            finish_reason = None

            while finish_reason is None or finish_reason == "tool_calls":
                # 发送请求
                # 注意：使用 $web_search 时必须禁用模型的思考能力 (thinking)
                # 参考文档: https://platform.kimi.com/docs/guide/use-web-search
                # 注意：kimi-k2.6 在禁用 thinking 时 temperature 固定为 0.6，不可配置
                data = {
                    "model": config.MODEL,
                    "messages": messages,
                    "temperature": 0.6,
                    "max_tokens": config.MAX_TOKENS,
                    "thinking": {"type": "disabled"},
                    "tools": [
                        {
                            "type": "builtin_function",
                            "function": {
                                "name": "$web_search",
                            },
                        },
                    ],
                }

                response = await client.post(
                    f"{config.BASE_URL}/chat/completions",
                    headers=headers,
                    json=data,
                )

                if response.status_code != 200:
                    error_msg = f"API 请求失败，状态码: {response.status_code}"
                    try:
                        err_detail = response.json().get("error", {})
                        if err_detail:
                            error_msg += f"，详情: {err_detail.get('message', '')}"
                    except Exception:
                        pass
                    if response.status_code == 401:
                        error_msg += "，请检查 API Key 是否正确"
                    elif response.status_code == 429:
                        error_msg += "，API 调用次数超限，请稍后再试"
                    return f"[Kimi] {error_msg}"

                result = response.json()

                if "error" in result:
                    err = result["error"]
                    return f"[Kimi] API 错误: {err.get('message', err)}"

                if "choices" not in result or not result["choices"]:
                    return "[Kimi] API 响应格式异常，未找到搜索结果"

                choice = result["choices"][0]
                finish_reason = choice["finish_reason"]

                if finish_reason == "tool_calls":
                    # 处理工具调用
                    # 按照官方文档建议，手动构造 assistant message，确保包含 reasoning_content 字段
                    msg = choice["message"]
                    message_dict = {
                        "role": "assistant",
                        "content": msg.get("content", ""),
                        "tool_calls": msg["tool_calls"],
                    }
                    if "reasoning_content" in msg:
                        message_dict["reasoning_content"] = msg["reasoning_content"]
                    messages.append(message_dict)

                    for tool_call in msg["tool_calls"]:
                        tool_call_name = tool_call["function"]["name"]
                        tool_call_arguments = json.loads(
                            tool_call["function"]["arguments"],
                        )

                        if tool_call_name == "$web_search":
                            tool_result = _web_search_impl(tool_call_arguments)
                        else:
                            tool_result = (
                                f"Error: unable to find tool by name '{tool_call_name}'"
                            )

                        # 添加工具调用结果
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call["id"],
                                "name": tool_call_name,
                                "content": json.dumps(tool_result),
                            },
                        )
                elif finish_reason == "stop":
                    return choice["message"]["content"]

            return "[Kimi] 搜索流程异常结束"

    except Exception as e:
        core.logger.exception("Kimi联网搜索失败")
        return f"[Kimi] 搜索失败: {e!s}"


@kimi_search_plugin.mount_sandbox_method(
    SandboxMethodType.AGENT,
    name="Kimi联网搜索",
    description="使用 Moonshot AI Kimi 模型内置联网搜索功能获取实时信息",
)
async def kimi_search(_ctx: AgentCtx, query: str) -> str:
    """使用 Kimi 联网搜索获取实时信息

    Args:
        query (str): 搜索查询内容

    Returns:
        str: 搜索结果
    """
    global _last_query, _last_call_time

    # 防止重复搜索和频繁调用
    if query == _last_query and time.time() - _last_call_time < config.THROTTLE_TIME:
        return "[错误] 禁止频繁搜索相同内容，请稍后再试"

    result = await _chat_with_web_search(query)

    # 更新缓存
    _last_query = query
    _last_call_time = time.time()

    return result


@kimi_search_plugin.mount_cleanup_method()
async def clean_up():
    """清理插件"""
    global _last_query, _last_call_time
    _last_query = None
    _last_call_time = 0
