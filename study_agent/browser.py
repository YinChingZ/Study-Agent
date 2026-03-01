"""
StudyAgent 浏览器连接模块

负责创建并管理 BrowserSession（CDP 连接到用户本地 Chrome）。
"""

import json
from urllib.parse import urljoin
from urllib.request import urlopen

from browser_use.browser import BrowserProfile, BrowserSession

from study_agent.config import BrowserConfig


def _resolve_cdp_url(cdp_url: str) -> str:
    """将 HTTP CDP 地址解析为 websocket 调试地址。"""
    if cdp_url.startswith("ws://") or cdp_url.startswith("wss://"):
        return cdp_url

    if not (cdp_url.startswith("http://") or cdp_url.startswith("https://")):
        return cdp_url

    version_url = urljoin(cdp_url if cdp_url.endswith("/") else f"{cdp_url}/", "json/version")
    try:
        with urlopen(version_url, timeout=2.0) as response:
            content = response.read().decode("utf-8", errors="replace")
        payload = json.loads(content)
    except json.JSONDecodeError:
        snippet = content[:120].replace("\n", " ") if "content" in locals() else ""
        raise RuntimeError(f"CDP 地址返回非 JSON：{version_url} -> {snippet}")
    except Exception as exc:
        raise RuntimeError(f"无法访问 CDP 地址：{version_url}，错误：{exc}") from exc

    ws_url = payload.get("webSocketDebuggerUrl") if isinstance(payload, dict) else None
    if not isinstance(ws_url, str) or not ws_url.strip():
        raise RuntimeError(f"CDP 响应缺少 webSocketDebuggerUrl：{version_url}")
    return ws_url


def create_browser_session(config: BrowserConfig | None = None) -> BrowserSession:
    """创建连接到本地 Chrome 的 BrowserSession。"""
    config = config or BrowserConfig()
    resolved_cdp_url = _resolve_cdp_url(config.cdp_url)
    print(f"🌐 连接 Chrome CDP：{resolved_cdp_url}")

    return BrowserSession(
        browser_profile=BrowserProfile(
            cdp_url=resolved_cdp_url,
            is_local=True,
            minimum_wait_page_load_time=config.minimum_wait_page_load_time,
            wait_for_network_idle_page_load_time=config.wait_for_network_idle_page_load_time,
            wait_between_actions=config.wait_between_actions,
        )
    )
