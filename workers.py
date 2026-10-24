import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from contextlib import ExitStack

from PyQt6.QtCore import QThread, pyqtSignal

from engine import Cancelled, EngineManager, check_cancel
from processes import ProcessTree, start_process
from connection_settings import ConnectionSettings, private_cookie_file


def download_arguments(binary, url, save_dir, quality, playlist, cookie_file=None, proxy=None):
    formats = {
        '1080p（或更低）': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
        '720p（或更低）': 'bestvideo[height<=?720]+bestaudio/best[height<=?720]/best',
        '480p（或更低）': 'bestvideo[height<=?480]+bestaudio/best[height<=?480]/best',
        '最小体积（适合流量少）': 'bestvideo[height<=?360][vcodec^=avc1]+bestaudio[ext=m4a]/best[ext=mp4]',
    }
    audio = quality == '仅音频（MP3 192kbps）'
    arguments = [str(binary), '--ignore-config', '--no-plugin-dirs', '--no-update',
                 '--no-colors', '--encoding', 'utf-8', '--newline', '--progress',
                 '--no-simulate', '--no-warnings', '--continue', '--retries', '10',
                 '--fragment-retries', '10', '--socket-timeout', '30',
                 '--yes-playlist' if playlist else '--no-playlist',
                 '--format', 'bestaudio/best' if audio else formats.get(quality, 'bestvideo*+bestaudio/best'),
                 '--output', os.path.join(os.path.abspath(save_dir), '%(title)s.%(ext)s'),
                 '--progress-template', ('download:__YTDLP_PROGRESS__{"status":%(progress.status)j,'
                                         '"percent":%(progress._percent_str)j,"speed":%(progress._speed_str)j,'
                                         '"eta":%(progress._eta_str)j}'),
                 '--print', 'before_dl:__YTDLP_FILE__%(filename)j']
    if audio:
        arguments += ['--extract-audio', '--audio-format', 'mp3', '--audio-quality', '192K']
    else:
        arguments += ['--merge-output-format', 'mp4']
    if cookie_file:
        arguments += ['--cookies', str(cookie_file)]
    if proxy:
        arguments += ['--proxy', proxy]
    executable_suffix = '.exe' if os.name == 'nt' else ''
    # Keep supporting FFmpeg placed beside the GUI or included in its bundle.
    candidates = [Path(sys.executable).parent,
                  Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))]
    for folder in candidates:
        if all((folder / (name + executable_suffix)).is_file() for name in ('ffmpeg', 'ffprobe')):
            arguments += ['--ffmpeg-location', str(folder)]
            break
    # Prevent URL strings being interpreted as extra command-line switches.
    return arguments + ['--', url]


class EngineUpdateWorker(QThread):
    log = pyqtSignal(str)
    completed = pyqtSignal(bool, str)

    def __init__(self, manager=None):
        super().__init__()
        self.manager = manager or EngineManager()
        self._stop_requested = False

    def request_stop(self):
        self._stop_requested = True

    def run(self):
        try:
            with self.manager.exclusive():
                self.manager.ensure(self.log.emit, lambda: self._stop_requested, update=True)
            self.completed.emit(True, 'yt-dlp 已安装／更新，可以直接使用，无需重新编译软件。')
        except Exception as exc:
            self.completed.emit(False, f'更新未完成：{exc}')


class DownloadWorker(QThread):
    log = pyqtSignal(str)
    status = pyqtSignal(str)
    current_file = pyqtSignal(str)
    completed = pyqtSignal(bool, str)
    engine_version = pyqtSignal(str)

    def __init__(self, url, save_dir, quality_mode, download_playlist=False, manager=None, connection=None):
        super().__init__()
        self.url = url
        self.save_dir = save_dir
        self.quality_mode = quality_mode
        self.download_playlist = download_playlist
        self.manager = manager or EngineManager()
        self.connection = connection or ConnectionSettings()
        self._stop_requested = False
        self._tree = None
        self._process_lock = threading.Lock()

    def request_stop(self):
        self._stop_requested = True
        with self._process_lock:
            if self._tree:
                self._tree.stop()

    def _line(self, text):
        if text.startswith('__YTDLP_PROGRESS__'):
            try:
                progress = json.loads(text.removeprefix('__YTDLP_PROGRESS__'))
                if progress.get('status') == 'finished':
                    self.status.emit('合并／转换中...')
                self.log.emit(f"[download] {progress.get('percent', '?')} "
                              f"at {progress.get('speed', '?')} ETA {progress.get('eta', '?')}")
                return
            except (ValueError, TypeError, AttributeError):
                self.log.emit('[进度] 无法解析一条进度信息。')
                return
        elif text.startswith('__YTDLP_FILE__'):
            try:
                name = json.loads(text.removeprefix('__YTDLP_FILE__'))
                if isinstance(name, str):
                    self.current_file.emit(os.path.basename(name))
                    return
            except (ValueError, TypeError):
                return
        self.log.emit(text)

    def run(self):
        success = False
        message = '下载失败，请查看日志。'
        try:
            with self.manager.exclusive(), ExitStack() as task_files:
                proxy = self.connection.proxy_url()
                if self.connection.use_cookie and not self.connection.cookie_file:
                    raise ValueError('请先导入 Cookie 文件。')
                cookie_path = task_files.enter_context(private_cookie_file(
                    self.connection.cookie_file if self.connection.use_cookie else None))
                self.status.emit('准备下载引擎...')
                binary = self.manager.ensure(self.log.emit, lambda: self._stop_requested)
                self.engine_version.emit(self.manager.installed_version())
                check_cancel(lambda: self._stop_requested)
                os.makedirs(self.save_dir, exist_ok=True)
                arguments = download_arguments(binary, self.url, self.save_dir,
                                               self.quality_mode, self.download_playlist,
                                               cookie_file=cookie_path, proxy=proxy)
                if cookie_path:
                    self.log.emit('[Cookie] 已启用 Cookie 登录下载。')
                if proxy:
                    self.log.emit(f'[代理] 已启用 {self.connection.proxy_type.upper()} 代理。')
                self.status.emit('下载中...')
                with start_process(arguments, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   stdin=subprocess.DEVNULL, text=True, encoding='utf-8', errors='replace',
                                   bufsize=1) as process:
                    tree = ProcessTree(process)
                    with self._process_lock:
                        self._tree = tree
                        if self._stop_requested:
                            tree.stop()
                    try:
                        # Bound each line, so remote metadata cannot create an unbounded read.
                        discard_remainder = False
                        while True:
                            line = process.stdout.readline(65536)
                            if not line:
                                break
                            if discard_remainder:
                                discard_remainder = not line.endswith('\n')
                                continue
                            if len(line) == 65536 and not line.endswith('\n'):
                                self.log.emit('[日志] 单条输出过长，已省略。')
                                discard_remainder = True
                                continue
                            self._line(line.rstrip('\r\n'))
                        code = process.wait()
                    finally:
                        with self._process_lock:
                            self._tree = None
                            tree.close()
                check_cancel(lambda: self._stop_requested)
                success = code == 0
                message = '下载 & 处理完成' if success else f'yt-dlp 返回错误（退出码 {code}），请查看日志。'
        except Cancelled:
            message = '已停止（下载部分支持断点续传）'
        except Exception as exc:
            message = f'发生错误：{exc}'
        self.completed.emit(success, message)
