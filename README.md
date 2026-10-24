## AI Assistant Support

You can send this page to an AI assistant:

https://github.com/xvacts/YoutubeDLTNew/blob/master/AGENTS.md

Example prompt:

Use websearch to read this page and help me use the project.

## Install and verify

Use Python 3.10 or later (3.12 recommended) to run/build the GUI from source.
Install an up-to-date FFmpeg/ffprobe from a trusted source on your PATH.

```sh
python -m venv .venv
# Activate .venv using your platform's activation script, then:
python -m pip install --upgrade pip
python -m pip install --upgrade -r requirements.txt
python main.py
python -m unittest discover -s tests -v
```

Windows reproducible runtime install:

```sh
python -m pip install --require-hashes --only-binary=:all: -r requirements-windows.lock
```

For Windows builds use `requirements-build-windows.lock` with the same flags.
For macOS builds use `requirements-build.txt`; the Windows lock is not a macOS lock.
Refresh the locks after reviewing dependency updates and rerun the tests/build.
The locks include the full runtime/build dependency closure and PyPI wheel SHA-256 hashes.
Build in a clean environment. In particular, keep unrelated tool directories off
the Windows build process PATH: PyInstaller can otherwise collect a conflicting
ICU DLL from another application. The Windows CI build step restricts PATH to the
selected Python installation and Windows system directories for this reason.

## 独立更新 yt-dlp

软件不再把 yt-dlp Python 包打进主程序。首次点击下载会安装官方稳定版，
也可以点击“安装／更新 yt-dlp”。后续更新只下载适用于本机的官方二进制，
无需重装、重新编译主程序或在用户电脑安装 Python。

引擎保存在 `~/.youtube_downloader/engine/`（Windows 为
`%USERPROFILE%\.youtube_downloader\engine\`），按版本存放。
安装流程校验 GitHub 官方 Release 的 SHA-256 和文件大小，并运行版本检查，
全部通过后才原子切换 `active.json`；下载、校验或启动失败会保留原来的可用版本。
界面主程序与 FFmpeg 仍各自维护；这个按钮不会更新 FFmpeg，也不需要管理员权限。
请先安装一次支持此功能的新版主程序，旧版内嵌引擎不会自动变成独立引擎。

下载期间禁用更新，暂停后可以更新再继续。下载／合并／转码通过独立子进程运行，
暂停和取消会终止它的子进程树，下载部分保留 `.part` 文件以便续传。
引擎进程禁用外部 yt-dlp 配置、插件及自身的自动更新，所有更新由界面统一校验。
使用官方稳定版，不下载镜像、远程插件或脚本；若发布信息缺少可信摘要则拒绝更新。
SHA-256 校验依赖通过 HTTPS 获取的官方 GitHub 元数据，未额外实施 GPG 签名验证，
无法防御上游发布账号本身被攻陷。引擎目录应仅对本机用户可写，程序不应提权运行。

首次安装及更新需联网访问 GitHub；已有有效引擎可直接复用，离线时不强制更新。
YouTube 的额外 JavaScript 运行环境要求以 [yt-dlp 官方说明](https://github.com/yt-dlp/yt-dlp#dependencies)
为准；本功能不自动安装额外运行环境。

## Cookie 与代理

界面采用深蓝紫渐变、半透明卡片、圆角按钮与动画开关，优先使用系统中文字体，
图标由本地 Qt 绘制，不下载字体或界面资源。当前文件的百分比和速度显示在进度卡片。
链接输入框粘贴完整 HTTP(S) 链接后自动换行，支持连续粘贴或批量多行粘贴；
在网址中间编辑时不自动拆行，一次粘贴可一次撤销。输入区字号和行距适合逐条查看链接。
Instagram（IG）视频请先导入有效的 IG Cookie，再粘贴视频链接；Facebook（FB）
公开视频可直接下载，需登录的内容请导入对应站点 Cookie。具体可用性受站点和账号权限影响。

已对齐上游界面的 Cookie 和代理控件，同时保留独立更新 yt-dlp：

- 勾选“使用 Cookie”，通过“导入 Cookie 文件”选择 Netscape 文本或浏览器 Cookie JSON
  （Cookie 数组，或包含 `cookies` 数组的对象）。文件上限 10 MB。
- 勾选“使用代理”，选择 HTTP、SOCKS5 或 SOCKS4，填写 IP／主机和端口，再点“确认”。
  支持 IPv4、IPv6 和普通域名；IP 输入框不填写协议或账号密码。
- 设置会保存，并兼容上游的 `cookie_file`、`use_proxy`、`proxy_ip`、`proxy_port`、`proxy_type`
  配置；只保存 Cookie 文件路径和启用状态，不将 Cookie 内容写入配置或日志。
- Cookie 使用每任务私有临时副本，JSON 会转换成 yt-dlp 所需的 Netscape 格式。
  下载结束或取消后删除临时副本，不覆盖原始导出文件。
- 同一批次的多个链接及暂停／继续沿用启动时的连接设置；更改设置用于下一批下载。
- 此处的代理用于视频下载。引擎安装和更新使用系统网络配置，Cookie 不会传给 GitHub 更新请求。

参考上游 `secure-artifacts/YoutubeDLT` 的 `main.py`（blob `3d65aa5b2418688e6a754c15759c5a60cf1b5030`）
的 Cookie 文件导入和 HTTP／SOCKS 代理控件。本项目使用独立进程接口接入这些功能，未重新引入内嵌 yt-dlp 包。

## Security boundaries

URLs and redirects can reach sites on your local network; multi-site downloading is
intentional. Only download from trusted sources and run without administrator rights.
URL paths, credentials, query parameters and fragments are removed from GUI logs.
Review other error text before sharing logs; automatic redaction is not a guarantee
that arbitrary upstream messages contain no sensitive data.

The audited PyQt6-Qt6 wheel is 6.11.2. Qt JSON/HTTP2 advisories requiring 6.11.3
remain under review until a patched wheel is available; those APIs are not called
by the application. QDom destructor CVE-2026-19248 is already fixed in 6.11.2.
Other optional Qt modules need their own reachability review before adding new
features. Python package audit tools do not cover all native Qt or external
FFmpeg vulnerabilities.

Update requests validate HTTPS and the official GitHub host allowlist before
following each redirect. Public update requests do not inherit `.netrc` logins.
Release metadata, local configuration and the active engine manifest have size
limits; malformed or deeply nested JSON is rejected safely. The GUI retains the
latest 2000 log lines. Cookie imports reject invalid control characters.

CI builds have read-only repository tokens. Separate publish jobs receive write
access and only download the corresponding artifact and publish it; they do not
install dependencies or execute project build scripts. macOS builds currently
use ad-hoc signing and are not Apple-notarized.

Audit snapshot (2026-10-24): the verified official Windows yt-dlp 2026.10.21
binary reports Brotli 1.2.0, Python 3.10.11 and OpenSSL 1.1.1t. Brotli 1.2.0 is
affected by the critical decoder advisory
[GHSA-9v8h-qqgm-4m35](https://github.com/advisories/GHSA-9v8h-qqgm-4m35);
the fixed Brotli release is 1.2.1. The Python package locks for this GUI do not
patch libraries inside the independent engine EXE. The developer elected to keep
the official stable distribution and its download functionality pending an
upstream fix. Avoid untrusted URLs/content in the meantime; this is a remaining
risk, not a completed security fix. Recheck the engine's embedded components
after an upstream update. An Accept-Encoding header alone cannot guarantee that
a malicious server will not send a Brotli response.

Do not commit credentials, `.env`, cookie exports or private keys. If a real secret
has ever been committed or disclosed, revoke and replace it at its provider;
deleting the current file alone does not invalidate the secret.
