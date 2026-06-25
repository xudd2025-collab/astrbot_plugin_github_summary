import asyncio
import re
import json
import base64
import asyncio
import aiohttp
from pathlib import Path
from playwright.sync_api import sync_playwright

from astrbot.api import AstrBotConfig, logger
from astrbot.api.all import AstrMessageEvent, Context, Star, register
from astrbot.api.event import filter


@register(
    "astrbot_plugin_github_summary",
    "菲比",
    "群内 GitHub 链接自动解析插件，自动抓取 README 并 AI 总结，生成信息卡片",
    "1.0.0",
    "https://github.com/",
)
class GitHubSummaryPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.GITHUB_TOKEN = (config.get("github_token", "") if config else "")
        self._session: aiohttp.ClientSession | None = None
        self._recent_repos: dict[str, float] = {}
        self._img_dir = Path(__file__).parent / "temp"
        self._img_dir.mkdir(exist_ok=True)
        logger.info("[GitHub插件] 已加载!")

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    # ===== 诊断命令 =====
    @filter.command("gh_test")
    async def cmd_test(self, event: AstrMessageEvent):
        """测试插件是否在线"""
        yield event.plain_result("GitHub 插件在线，一切正常")

    # ===== 主功能 =====
    @filter.regex(r"github\.com/\S+")
    async def on_github_link(self, event: AstrMessageEvent):
        text = event.message_str
        m = re.search(r'github\.com/(?P<owner>[a-zA-Z0-9._-]+)/(?P<repo>[a-zA-Z0-9._-]+)', text)
        if not m:
            return

        owner = m.group("owner")
        repo = m.group("repo")
        repo_full = f"{owner}/{repo}"

        import time as _time
        now = _time.time()
        if repo_full in self._recent_repos and now - self._recent_repos[repo_full] < 3600:
            return
        self._recent_repos[repo_full] = now

        logger.info(f"[GitHub插件] 检测到仓库链接: {repo_full}")

        yield event.plain_result(f"检测到 GitHub 仓库 {repo_full}，正在解析...")

        # 1. 获取仓库信息
        repo_info = await self._fetch_repo_info(owner, repo)

        # 2. 获取 README + 文件树 + 最新提交（并发）
        readme_text, file_tree, latest_commit = await asyncio.gather(
            self._fetch_readme(owner, repo),
            self._fetch_file_tree(owner, repo),
            self._fetch_latest_commit(owner, repo),
        )
        readme_text = readme_text
        file_tree_data = file_tree
        commit_data = latest_commit

        # 3. 生成信息卡片图片
        card_paths = []
        if repo_info:
            card_paths = await self._render_html_card(repo_full, repo_info, file_tree_data, commit_data, readme_text)

        # 4. AI 总结 README
        summary_text = None
        if readme_text:
            summary_text = await self._summarize_readme(repo_full, readme_text)

        # 5. 先发卡片图获取 message_id，再构建合并转发
        nodes = []
        uin = event.get_self_id()
        name = "菲比"
        import time as _tt
        ts = int(_tt.time())

        if card_paths:
            for i, cp in enumerate(card_paths):
                nodes.append({
                    "type": "node",
                    "data": {
                        "name": name,
                        "uin": uin,
                        "content": [{"type": "image", "data": {"file": "file:///" + str(cp).replace("\\", "/")}}],
                        "time": ts + i,
                    }
                })
            logger.info(f"[GitHub插件] 卡片图 {len(card_paths)} 张已入转发节点")

        if summary_text:
            nodes.append({
                "type": "node",
                "data": {
                    "name": name,
                    "uin": uin,
                    "content": [{"type": "text", "data": {"text": summary_text}}],
                    "time": ts,
                }
            })
        elif repo_info and not card_paths:
            desc = repo_info.get("description", "（无描述）")
            nodes.append({
                "type": "node",
                "data": {
                    "name": name,
                    "uin": uin,
                    "content": [{"type": "text", "data": {"text": f"{repo_full}\\n简介：{desc}"}}],
                    "time": ts,
                }
            })
        elif not card_paths:
            nodes.append({
                "type": "node",
                "data": {
                    "name": name,
                    "uin": uin,
                    "content": [{"type": "text", "data": {"text": f"无法获取 {repo_full} 的信息，请检查仓库是否存在。"}}],
                    "time": ts,
                }
            })

        if nodes:
            try:
                client = event.bot
                group_id = event.get_group_id()
                await client.api.call_action(
                    "send_group_forward_msg",
                    group_id=group_id,
                    messages=nodes,
                )
                logger.info(f"[GitHub插件] 合并转发发送成功, {len(nodes)} 个节点")
            except Exception as exc:
                logger.error(f"[GitHub插件] 合并转发失败: {exc}")
                yield event.plain_result(f"解析完成但发送失败: {exc}")

    async def _fetch_repo_info(self, owner: str, repo: str) -> dict | None:
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {self.GITHUB_TOKEN}"
        url = f"https://api.github.com/repos/{owner}/{repo}"
        try:
            session = await self._get_session()
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    return await resp.json()
                logger.warning(f"[GitHub插件] repo info {resp.status}")
        except Exception as e:
            logger.error(f"[GitHub插件] repo info 异常: {e}")
        return None

    async def _fetch_readme(self, owner: str, repo: str) -> str | None:
        headers = {}
        if self.GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {self.GITHUB_TOKEN}"
        for branch in ["main", "master"]:
            url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/README.md"
            try:
                session = await self._get_session()
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        text = await resp.text(encoding="utf-8")
                        logger.info(f"[GitHub插件] README: {len(text)} 字符")
                        return text
                    elif resp.status != 404:
                        logger.warning(f"[GitHub插件] raw {resp.status}")
            except Exception as e:
                logger.warning(f"[GitHub插件] {branch}: {e}")
                continue
        api_url = f"https://api.github.com/repos/{owner}/{repo}/readme"
        api_headers = {"Accept": "application/vnd.github.v3+json"}
        if self.GITHUB_TOKEN:
            api_headers["Authorization"] = f"Bearer {self.GITHUB_TOKEN}"
        try:
            session = await self._get_session()
            async with session.get(api_url, headers=api_headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    content = base64.b64decode(data.get("content", "")).decode("utf-8", errors="replace")
                    return content
        except Exception as e:
            logger.error(f"[GitHub插件] API: {e}")
        return None

    async def _fetch_file_tree(self, owner: str, repo: str) -> list[dict] | None:
        """获取仓库根目录内容"""
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {self.GITHUB_TOKEN}"
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/"
        try:
            session = await self._get_session()
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, list):
                        return data
        except Exception as e:
            logger.warning(f"[GitHub插件] file_tree 异常: {e}")
        return None

    async def _fetch_latest_commit(self, owner: str, repo: str) -> dict | None:
        """获取最新提交"""
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {self.GITHUB_TOKEN}"
        url = f"https://api.github.com/repos/{owner}/{repo}/commits?per_page=1"
        try:
            session = await self._get_session()
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, list) and data:
                        return data[0]
        except Exception as e:
            logger.warning(f"[GitHub插件] commit 异常: {e}")
        return None

    async def _render_html_card(self, repo_full: str, info: dict, file_tree: list[dict] | None, commit: dict | None, readme_text: str | None = None) -> list[str]:
        """手机模式截 GitHub 页面，超长则分最多3段。返回图片路径列表"""
        try:
            self._img_dir.mkdir(parents=True, exist_ok=True)
            base = self._img_dir / f"gh_{repo_full.replace('/', '_')}"
            url = f"https://github.com/{repo_full}"

            def _shot():
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    iphone = p.devices["iPhone 12"]
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page(**iphone)
                    page.goto(url, timeout=30000, wait_until="domcontentloaded")
                    page.wait_for_timeout(4000)
                    W, VH = 390, 3000  # viewport height per segment
                    total_h = page.evaluate("document.body.scrollHeight")
                    n = min(3, max(1, -(-total_h // VH)))
                    seg_h = total_h // n if n > 1 else min(total_h, VH)
                    paths = []
                    for i in range(n):
                        y = i * seg_h
                        png = str(base) + (f"_{i}.png" if n > 1 else ".png")
                        page.set_viewport_size({"width": W, "height": VH})
                        page.evaluate(f"window.scrollTo(0, {y})")
                        page.wait_for_timeout(1000)
                        page.screenshot(path=png, clip={"x":0,"y":0,"width":W,"height":VH})
                        paths.append(png)
                    browser.close()
                    return paths

            return await asyncio.to_thread(_shot)
        except Exception as e:
            logger.error(f"[GitHub插件] 截图异常: {e}")
            return []
    @staticmethod
    def _wrap_text(text: str, font, max_width: int) -> list[str]:
        lines = []
        current = ""
        for ch in text:
            test = current + ch
            try:
                bbox = font.getbbox(test)
                w = bbox[2] - bbox[0]
            except Exception:
                w = len(test) * 12
            if w > max_width and current:
                lines.append(current)
                current = ch
            else:
                current = test
        if current:
            lines.append(current)
        return lines

    async def _summarize_readme(self, repo_full: str, text: str) -> str | None:
        """使用 AstrBot 当前 LLM 总结 README"""
        max_chars = 8000
        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n（README 过长，已截断至前 8000 字符）"

        system_prompt = (
            "你是开源项目速览助手。用户会给你一段 GitHub 项目的 README 文档。"
            "用中文极简总结，格式："
            "一句话简介 | 核心要点（3条以内）| 安装方式（一行）| 协议"
            "控制在 150 字内，不要废话。"
        )

        try:
            provider = self.context.get_using_provider()
            if not provider:
                logger.error("[GitHub插件] 未找到可用的 LLM 提供商")
                return None

            resp = await provider.text_chat(
                prompt=text,
                system_prompt=system_prompt,
            )
            content = resp.completion_text.strip()
            content = re.sub(r'^```(?:markdown|md)?\s*', '', content)
            content = re.sub(r'\s*```$', '', content)
            return f"GitHub 仓库 {repo_full} 的 README 总结：\n\n{content}"
        except Exception as e:
            logger.error(f"[GitHub插件] 总结异常: {e}")
            return None
