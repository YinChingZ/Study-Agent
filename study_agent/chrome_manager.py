"""
Chrome 自动检测、启动和连接管理。

功能：
1. 自动检测系统中 Chrome 的安装路径（Windows / macOS / Linux）
2. 检测指定端口是否已有 Chrome debug 实例在运行
3. 自动以 --remote-debugging-port 启动 Chrome
4. 等待 CDP 就绪
"""

import asyncio
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


class ChromeManager:
    """Chrome 调试实例管理器。"""

    def __init__(self, port: int = 9222):
        self.port = port
        self._process: subprocess.Popen | None = None

    def find_chrome(self) -> str | None:
        """在系统中查找 Chrome 可执行文件路径。"""
        system = platform.system()

        if system == "Windows":
            candidates = [
                Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
                Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google/Chrome/Application/chrome.exe",
                Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
                Path(os.environ.get("PROGRAMFILES", "")) / "Chromium/Application/chrome.exe",
                Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Chromium/Application/chrome.exe",
            ]
            for candidate in candidates:
                if candidate.exists():
                    return str(candidate)
            found = shutil.which("chrome") or shutil.which("chrome.exe")
            return found

        if system == "Darwin":
            candidates = [
                Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
                Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
            ]
            for candidate in candidates:
                if candidate.exists():
                    return str(candidate)
            return shutil.which("google-chrome") or shutil.which("chromium")

        linux_candidates = [
            shutil.which("google-chrome"),
            shutil.which("google-chrome-stable"),
            shutil.which("chromium-browser"),
            shutil.which("chromium"),
        ]
        for candidate in linux_candidates:
            if candidate:
                return candidate
        return None

    async def probe_cdp(self) -> tuple[bool, str | None]:
        """探测 CDP 端口是否为有效 Chrome DevTools endpoint。"""
        url = f"http://127.0.0.1:{self.port}/json/version"

        def _probe() -> tuple[bool, str | None]:
            try:
                with urlopen(url, timeout=1.5) as response:
                    content = response.read().decode("utf-8", errors="replace")
                    if response.status != 200:
                        return False, f"HTTP {response.status}"
                    try:
                        payload = json.loads(content)
                    except json.JSONDecodeError:
                        snippet = content[:120].replace("\n", " ")
                        return False, f"/json/version 返回非 JSON：{snippet}"

                    ws_url = payload.get("webSocketDebuggerUrl") if isinstance(payload, dict) else None
                    if not isinstance(ws_url, str) or not ws_url.strip():
                        return False, "响应缺少 webSocketDebuggerUrl"
                    return True, None
            except (URLError, TimeoutError, OSError):
                return False, "端口未就绪"

        return await asyncio.to_thread(_probe)

    async def is_running(self) -> bool:
        """检测 CDP 端口是否已在监听。"""
        ok, _ = await self.probe_cdp()
        return ok

    async def ensure_running(self, chrome_path: str | None = None) -> str:
        """确保 Chrome debug 实例在运行，返回 CDP URL。"""
        ok, reason = await self.probe_cdp()
        if ok:
            return f"http://127.0.0.1:{self.port}"

        path = chrome_path or self.find_chrome()
        if not path:
            raise RuntimeError("未找到 Chrome，请手动指定路径或安装 Chrome")

        user_data_dir = Path.home() / ".studyagent" / "chrome-profile"
        user_data_dir.mkdir(parents=True, exist_ok=True)

        self._process = subprocess.Popen(
            [
                path,
                f"--remote-debugging-port={self.port}",
                f"--user-data-dir={user_data_dir}",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        deadline = asyncio.get_running_loop().time() + 15
        last_reason = reason
        while asyncio.get_running_loop().time() < deadline:
            ok, reason = await self.probe_cdp()
            if ok:
                return f"http://127.0.0.1:{self.port}"
            last_reason = reason
            await asyncio.sleep(0.5)

        raise RuntimeError(f"Chrome 调试端口未在预期时间内就绪：{last_reason or '未知原因'}")

    def shutdown(self) -> None:
        """关闭由本程序启动的 Chrome 实例。"""
        if not self._process:
            return
        self._process.terminate()
        self._process = None
