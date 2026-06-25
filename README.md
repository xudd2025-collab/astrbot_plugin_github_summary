# astrbot_plugin_github_summary

群内 GitHub 链接自动解析插件。当群聊中出现 GitHub 仓库链接时，自动抓取 README 并截图，AI 智能总结，合并转发一条消息发出。

## 这是什么

在群聊里发 GitHub 仓库链接（比如 `https://github.com/yt-dlp/yt-dlp`），机器人会自动：

1. 检测链接，解析仓库信息
2. 用手机模式打开页面，截图 README（超长页面自动分 3 段）
3. AI 生成中文总结（项目简介、核心功能、安装方式）
4. 合并转发一条消息发到群里

![效果截图](screenshot.jpg)

**AI 总结效果：**

![总结示例](summary_sample.jpg)

## 怎么安装

### 方式一：插件市场安装

在 AstrBot 插件市场搜索 `astrbot_plugin_github_summary` 并安装。

### 方式二：手动下载

1. **下载插件**：从本仓库下载 ZIP 或 `git clone`
2. **放入插件目录**：将文件夹放入 AstrBot 的 `data/plugins/` 下，确保目录结构为：
   ```
   data/plugins/astrbot_plugin_github_summary/
   ├── main.py
   ├── metadata.yaml
   ├── requirements.txt
   └── _conf_schema.json
   ```
3. **检查 Python 版本**：
   ```bash
   python --version
   ```
   需 >= 3.8。推荐 3.10+。

4. **安装 Python 依赖**：
   ```bash
   pip install -r requirements.txt
   ```
   如报权限错误，加 `--user`：
   ```bash
   pip install --user -r requirements.txt
   ```

5. **安装 Chromium 浏览器**：
   ```bash
   playwright install chromium
   ```
   > Windows 一般直接成功。Linux 如报缺少系统库，先执行：
   > ```bash
   > playwright install-deps chromium
   > ```

6. **验证安装**：在 AstrBot 根目录执行：
   ```bash
   python -c "from playwright.sync_api import sync_playwright; print('OK')"
   ```
   输出 `OK` 表示依赖就绪。

7. **重启 AstrBot**，在 WebUI 插件管理页启用即可

### 公共步骤

在 WebUI 插件配置页填写：

- **`ai_api_key`**（必填）：AI API 密钥，否则 AI 总结无法工作。推荐用 DeepSeek，注册即送额度。
- **`github_token`**（可选）：提高 GitHub API 频率限制。

## 依赖

| 依赖 | 说明 |
|------|------|
| Python >= 3.8 | 运行环境 |
| AstrBot 框架 | 插件运行平台 |
| AI API（DeepSeek / OpenAI 兼容） | AI 总结 README 必需 |
| `playwright >= 1.40.0` | 网页截图引擎 |
| Chromium 浏览器 | 由 `playwright install chromium` 安装 |
| `aiohttp >= 3.9.0` | 异步 HTTP 请求 |

## 怎么使用

安装后无需任何命令，直接使用：

- 在群聊中发送任意 GitHub 仓库链接
- 机器人自动处理，几秒后返回合并转发消息
- 消息包含截图（分 3 段）+ AI 中文总结

**示例：**
发送 `https://github.com/yt-dlp/yt-dlp` → 自动返回截图 + 总结

## 配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `ai_api_url` | AI API 地址，支持 OpenAI 兼容接口 | `https://api.deepseek.com/v1` |
| `ai_api_key` | AI API 密钥（**必填**，否则总结不可用） | 空 |
| `ai_model` | AI 模型名称 | `deepseek-chat` |
| `github_token` | GitHub Personal Access Token（可选） | 空 |

## 作者

橙猫猫
