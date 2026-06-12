# Kouhai Bot

Kouhai Bot 是一个面向 QQ 群的 Codeforces 每日题机器人。它可以随机抓取 CF 题目、把题面渲染成图片发送到群里、用配置文件里的大模型 API 和用户交互，并在题目解出后提供复盘和可行题解。

## 功能概览

- `/newproblem`：发布一道新题；当前题未解出时不会直接换题。
- `/newproblem --force`：强制换题。
- `/problem`：重新发送当前题。
- `/submit <做法>`：提交你的思路，让 AI 判断是否能推出正确解法。
- `/clarify <问题>`：只澄清题意细节，不给解法提示。
- `/guess <猜想/做法>`：当前题未解出时，分析你的做法和答案方向的契合度，但不直接泄露标准解法。
- `/review <问题>`：题目解出后复盘做法、错误原因或复杂度。
- `/tourial`：题目解出后发送一种可行答案。`/tutorial` 是同义别名。
- `/tag`：题目解出后查看标签；未解出前会保密。
- `/scoreboard`：查看累计解题排行。
- `/status`：查看机器人是否正在处理任务。
- `/help`：查看命令帮助。

## 环境准备

项目需要 Python 3.11+。推荐用 `uv` 管理依赖：

```bash
git clone https://github.com/KaoXiaoYu/SanWenYu.git
cd SanWenYu
uv sync
```

如果你不用 `uv`，也可以用普通虚拟环境安装：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

## Playwright / Firefox 渲染

题面图片渲染使用 Playwright 打开浏览器页面，页面中用 MathJax 渲染 LaTeX 公式，再截图成 PNG。

默认浏览器是 Firefox。所有平台都需要先安装 Python 依赖，再安装 Playwright 管理的 Firefox 浏览器内核：

```bash
python -m playwright install firefox
```

如果你用 `uv`：

```bash
uv run python -m playwright install firefox
```

### Linux

Linux 服务器建议直接安装 Playwright 的 Firefox 和系统依赖：

```bash
python -m playwright install --with-deps firefox
```

如果你用 `uv`：

```bash
uv run python -m playwright install --with-deps firefox
```

`--with-deps` 会尝试安装 Firefox 无头运行所需的系统库，通常需要 `sudo` 权限。如果服务器不能自动安装依赖，可以手动安装常见依赖：

```bash
sudo apt update
sudo apt install -y \
  libgtk-3-0 libdbus-glib-1-2 libasound2 \
  libx11-xcb1 libxcomposite1 libxdamage1 libxfixes3 \
  libxrandr2 libgbm1 libnss3 libatk-bridge2.0-0 \
  fonts-noto-cjk fonts-noto-color-emoji
```

Linux 服务器不需要桌面环境，Playwright 默认以 headless 模式启动 Firefox。建议显式指定：

```bash
export KOUHAI_RENDER_BROWSER=firefox
```

如果渲染出的中文是方块，安装中文字体：

```bash
sudo apt install -y fonts-noto-cjk
```

如果 emoji 不是彩色或显示为空白，安装 emoji 字体：

```bash
sudo apt install -y fonts-noto-color-emoji
```

如果在 Docker、极简云服务器或 CI 环境中运行，优先使用 Playwright 下载的 Firefox，不要依赖系统自带 Firefox；Playwright 下载的浏览器和 Playwright API 兼容性最好。

### macOS

macOS 上安装 Playwright Firefox：

```bash
python -m playwright install firefox
```

如果你用 `uv`：

```bash
uv run python -m playwright install firefox
```

macOS 一般不需要额外系统依赖。系统自带中文字体和 Apple Color Emoji，题面中的中文与 emoji 通常可以直接渲染。

如果你使用 shell 启动机器人，建议写入环境变量：

```bash
export KOUHAI_RENDER_BROWSER=firefox
```

如果你用 launchd、pm2、systemd 之类的方式托管进程，需要把 `KOUHAI_RENDER_BROWSER=firefox` 写进对应服务配置里，而不是只在当前终端里 export。

### 浏览器选择

渲染器默认读取环境变量 `KOUHAI_RENDER_BROWSER`，可选值：

Windows PowerShell:

```powershell
set KOUHAI_RENDER_BROWSER=firefox
```

Linux/macOS:

```bash
export KOUHAI_RENDER_BROWSER=firefox
```

可选值包括：

- `firefox`
- `chromium`
- `webkit`

如果 Firefox 启动失败，代码会依次尝试 Firefox、Chromium、WebKit。若所有 Playwright 浏览器都不可用，会退回到 Pillow 文本图片渲染；这个兜底模式不会真正渲染 LaTeX，也不能嵌入原题图片。

### MathJax 网络要求

注意：MathJax 当前从 CDN 加载。运行环境需要能访问：

```text
https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js
```

如果服务器不能联网，需要把 MathJax 文件下载到本地，并修改 `src/kouhai_bot/statement_render.py` 里的 `<script src="...">` 路径。

### 快速自检

安装后可以用下面的命令确认 Playwright 能启动 Firefox：

```bash
python -m playwright install firefox
python -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.firefox.launch(); print('firefox ok'); b.close(); p.stop()"
```

如果使用 `uv`：

```bash
uv run python -m playwright install firefox
uv run python -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.firefox.launch(); print('firefox ok'); b.close(); p.stop()"
```

Linux 上如果这一步报缺少系统库，优先重新运行：

```bash
python -m playwright install --with-deps firefox
```

## 配置文件

复制示例配置：

```bash
cp config.example.yaml config.yaml
```

Windows PowerShell:

```powershell
Copy-Item config.example.yaml config.yaml
```

然后编辑 `config.yaml`。常见字段包括：

- `bot_qq`：机器人 QQ 号。
- `current_group`：机器人服务的 QQ 群号。
- `napcat_http_host` / `napcat_http_port`：NapCat HTTP API 地址。
- `napcat_ws_host` / `napcat_ws_port`：机器人监听的反向 WebSocket 地址。
- `llm_provider` 和各类 API key/model：大模型服务配置。
- `qwen_api_key` / `qwen_model`：用于识别 Codeforces 原题中公式图片的视觉模型。
- `min_rating` / `max_rating`：每日题难度范围。
- `daily_post_cron`：定时发题时间。
- `newproblem_cooldown`：手动刷题冷却时间。

`config.yaml` 已被 `.gitignore` 忽略，不要把真实 API key 提交到仓库。

## NapCat 连接

机器人通过 NapCat 的 OneBot11 HTTP API 发送 QQ 消息，并通过反向 WebSocket 接收 QQ 事件。

你需要在 NapCat 中配置：

- HTTP 服务端口，对应 `napcat_http_host` / `napcat_http_port`。
- 反向 WebSocket，连接到机器人监听地址，对应 `napcat_ws_host` / `napcat_ws_port`。
- 让机器人 QQ 加入 `current_group` 指定的群。

一个机器人实例默认服务一个群。如果你要服务多个群，建议运行多个实例，并为每个实例使用不同的配置文件、端口和数据目录。

## 启动

使用 `uv`：

```bash
uv run start
```

普通 Python 环境：

```bash
python -m kouhai_bot.main start
```

其他管理命令：

```bash
uv run status
uv run restart
uv run stop
```

启动后，在目标 QQ 群中发送：

```text
/help
```

如果机器人能回复，说明 NapCat 和配置已经连通。

## 题面抓取与图片渲染

发题流程大致是：

1. 从 Codeforces 抓取候选题。
2. 下载原题 HTML。
3. 用视觉模型识别 CF 的公式图片，转成 LaTeX。
4. 保留原题里的普通图片，并把图片下载成 base64 嵌进 HTML。
5. 移除题目标题/header，避免未解出前暴露题号或题名。
6. 用 Firefox + MathJax 渲染 HTML/Markdown。
7. 截图生成 PNG，发送到 QQ 群。

缓存文件在：

```text
<data_dir>/statements/<pid>.json
```

渲染出的 PNG 在：

```text
<data_dir>/groups/<group_id>/rendered/
```

如果你修改了渲染逻辑，旧缓存里可能没有 `render_html` 字段。机器人会在再次遇到该题时重新抓取题面以补齐渲染缓存。

## 解题交互规则

在当前题未解出前：

- `/clarify` 只回答题意、输入输出、样例等问题。
- `/guess` 可以评价你的思路是否接近，但不会直接给完整做法。
- `/tag` 不会展示标签。
- 机器人不会主动暴露题号、题名、比赛编号或链接。

当有人通过 `/submit` 被判定为正确后：

- 计入 scoreboard。
- 可以使用 `/review` 复盘。
- 可以使用 `/tourial` 查看一种可行答案。
- `/tag` 开始展示标签。

## 题解缓存

官方题解由 `tools/` 下的脚本抓取，缓存到：

```text
<data_dir>/tutorials/<pid>.json
```

当题目解出后，机器人会尝试翻译并发送题解。翻译缓存保存到：

```text
<data_dir>/tutorial_translations/<pid>.txt
```

如果 `/tourial` 提示没有题解缓存，说明该题还没有抓到可用 editorial。

## 常见问题

### 中文显示成方块或乱码

浏览器截图模式通常不会有这个问题。如果退回 Pillow 模式，服务器需要安装中文字体。

Windows 推荐：

```text
C:\Windows\Fonts\msyh.ttc
C:\Windows\Fonts\simsun.ttc
```

Linux 推荐安装 Noto CJK：

```bash
sudo apt install fonts-noto-cjk fonts-noto-color-emoji
```

### LaTeX 没有渲染

检查：

1. 是否安装了 Playwright Firefox：

```bash
python -m playwright install firefox
```

2. 服务器是否能访问 MathJax CDN。
3. 是否设置了错误的 `KOUHAI_RENDER_BROWSER`。

### 原题图片没有出现在输出图中

原题普通图片会在抓题时下载并嵌入 `render_html`。如果下载失败，会显示 `[IMAGE]`。常见原因是服务器不能访问 Codeforces 图片地址。

### 机器人没有反应

检查：

1. `current_group` 是否是目标群号。
2. `bot_qq` 是否是机器人 QQ。
3. NapCat HTTP 和反向 WebSocket 端口是否匹配。
4. 机器人是否过滤了自己的消息。
5. 日志里是否有 API key、网络或模型超时错误。

## 开发

运行语法检查：

```bash
python -m compileall src tests
```

运行测试：

```bash
python -m pytest
```

如果使用 `uv`：

```bash
uv run pytest
```

## License

MIT
