"""
StudyAgent 浏览器连接模块

负责创建并管理 BrowserSession（CDP 连接到用户本地 Chrome）。
"""

from browser_use.browser import BrowserProfile, BrowserSession

from study_agent.config import BrowserConfig


def create_browser_session(config: BrowserConfig | None = None) -> BrowserSession:
    """创建连接到本地 Chrome 的 BrowserSession。"""
    config = config or BrowserConfig()
    print(f"🌐 连接 Chrome CDP：{config.cdp_url}")

    return BrowserSession(
        browser_profile=BrowserProfile(
            cdp_url=config.cdp_url,
            is_local=True,
            minimum_wait_page_load_time=config.minimum_wait_page_load_time,
            wait_for_network_idle_page_load_time=config.wait_for_network_idle_page_load_time,
            wait_between_actions=config.wait_between_actions,
        )
    )
