# astrbot_plugin_github_summary

群内 GitHub 链接自动解析插件。当群聊中出现 GitHub 仓库链接时，自动：
- 手机模式截图 README 页面（超长自动分最多 3 段）
- AI 智能总结项目简介、核心功能、安装方式
- 合并转发到群聊

## 安装

1. 在 AstrBot 插件市场搜索 `astrbot_plugin_github_summary` 安装
2. 安装 Playwright 浏览器：`playwright install chromium`
3. 可选：在插件配置中填入 GitHub Token 以提高 API 频率限制

## 依赖

- `playwright` + Chromium 浏览器
- `aiohttp`

## 配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `github_token` | GitHub Personal Access Token（可选） | 空 |

## 使用

直接在群聊中发送 GitHub 仓库链接（如 `https://github.com/yt-dlp/yt-dlp`），机器人自动处理并返回合并转发消息。

## 作者

菲比
