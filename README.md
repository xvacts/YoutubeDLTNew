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

## Security boundaries

URLs and redirects can reach sites on your local network; multi-site downloading is
intentional. Only download from trusted sources and run without administrator rights.
URL paths, credentials, query parameters and fragments are removed from GUI logs.
Review other error text before sharing logs; automatic redaction is not a guarantee
that arbitrary upstream messages contain no sensitive data.

The audited PyQt6-Qt6 wheel is 6.11.2. Qt advisories requiring 6.11.3 remain under
review until a patched wheel is available; affected QDom/Qt JSON/HTTP2 APIs are not
called by the application. Python package audit tools do not cover all native Qt
or external FFmpeg vulnerabilities.

Do not commit credentials, `.env`, cookie exports or private keys. If a real secret
has ever been committed or disclosed, revoke and replace it at its provider;
deleting the current file alone does not invalidate the secret.
