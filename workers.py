import json
import os
import subprocess
import sys
import threading
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from engine import Cancelled, EngineManager, check_cancel
from processes import ProcessTree, start_process


def download_arguments(binary, url, save_dir, quality, playlist):
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
                 '--progress-template', 'download:__YTDLP_PROGRESS__%(progress)j',
                 '--print', 'before_dl:__YTDLP_FILE__%(filename)j']
    if audio:
        arguments += ['--extract-audio', '--audio-format', 'mp3', '--audio-quality', '192K']
    else:
        arguments += ['--merge-output-format', 'mp4']
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

    def __init__(self, url, save_dir, quality_mode, download_playlist=False, manager=None):
        super().__init__()
        self.url = url
        self.save_dir = save_dir
        self.quality_mode = quality_mode
        self.download_playlist = download_playlist
        self.manager = manager or EngineManager()
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
                self.log.emit(f"[download] {progress.get('_percent_str', '?')} "
                              f"at {progress.get('_speed_str', '?')} ETA {progress.get('_eta_str', '?')}")
                return
            except (ValueError, TypeError, AttributeError):
                pass
        elif text.startswith('__YTDLP_FILE__'):
            try:
                name = json.loads(text.removeprefix('__YTDLP_FILE__'))
                if isinstance(name, str):
                    self.current_file.emit(os.path.basename(name))
                    return
            except (ValueError, TypeError):
                pass
        self.log.emit(text)

    def run(self):
        success = False
        message = '下载失败，请查看日志。'
        try:
            with self.manager.exclusive():
                self.status.emit('准备下载引擎...')
                binary = self.manager.ensure(self.log.emit, lambda: self._stop_requested)
                self.engine_version.emit(self.manager.installed_version())
                check_cancel(lambda: self._stop_requested)
                os.makedirs(self.save_dir, exist_ok=True)
                arguments = download_arguments(binary, self.url, self.save_dir,
                                               self.quality_mode, self.download_playlist)
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
                        while True:
                            line = process.stdout.readline(65536)
                            if not line:
                                break
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
