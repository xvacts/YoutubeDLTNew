# -*- coding: utf-8 -*-
"""
YouTube 下载工具（基于 PyQt6 + yt-dlp）
- 支持单视频 / 播放列表 / 频道
- 支持一次粘贴多个链接（多行，每行一个）
- 频道链接 + 勾选播放列表时会有警告
- 逐个串行下载
"""
import sys
import os
import json
import datetime
import subprocess
import platform
import webbrowser
import html
import re
import tempfile
from urllib.parse import urlsplit, urlunsplit
from PyQt6.QtWidgets import QApplication, QMessageBox, QFileDialog
from PyQt6.QtCore import QTimer, QEvent, QLockFile
from PyQt6.QtGui import QIcon
from engine import EngineManager
from workers import DownloadWorker, EngineUpdateWorker
from connection_settings import ConnectionSettings, private_cookie_file
from ui_theme import AuroraWindow, line_icon
from ui_layout import build_interface

# ================== 配置路径 ==================
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".youtube_downloader")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
GITHUB_API_URL = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
GITHUB_RELEASES_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest"

# 单实例锁
LOCK_FILE = os.path.join(CONFIG_DIR, "app.lock")
MAX_CONFIG_BYTES = 512 * 1024

def redact_urls(text):
    """Keep URL credentials, signed paths, query tokens and fragments out of UI logs."""
    def redact(match):
        try:
            parts = urlsplit(match.group(0))
            # Only retain the origin: secrets may also appear in the URL path.
            host = parts.hostname or "redacted"
            if not re.fullmatch(r'[A-Za-z0-9._:-]+', host):
                return '[redacted URL]'
            if ':' in host:
                host = f'[{host}]'
            return urlunsplit((parts.scheme, host, '/[redacted]', '', ''))
        except ValueError:
            return '[redacted URL]'
    return re.sub(r'(?:https?|socks4|socks5)://[^\s<>]+', redact, text, flags=re.IGNORECASE)

# 默认下载路径
def get_default_downloads():
    home = os.path.expanduser("~")
    if os.name == 'nt':
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders")
            path = winreg.QueryValueEx(key, "{374DE290-123F-4565-9164-39C4925E467B}")[0]
            winreg.CloseKey(key)
            return path
        except:
            return os.path.join(home, "Downloads")
    else:
        return os.path.join(home, "Downloads")

class ConfigManager:
    @staticmethod
    def _read():
        try:
            with open(CONFIG_FILE, 'rb') as f:
                content = f.read(MAX_CONFIG_BYTES + 1)
            if len(content) > MAX_CONFIG_BYTES:
                return {}
            data = json.loads(content)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError, RecursionError):
            return {}

    @staticmethod
    def load():
        data = ConfigManager._read()
        path = data.get('download_path')
        quality = data.get('last_quality')
        return (path if isinstance(path, str) and path else get_default_downloads(),
                quality if isinstance(quality, str) else "最高质量（推荐）")

    @staticmethod
    def save(key, value):
        ConfigManager.save_many({key: value})

    @staticmethod
    def save_many(values):
        data = ConfigManager._read()
        data.update(values)
        temporary = None
        try:
            directory = os.path.dirname(CONFIG_FILE)
            os.makedirs(directory, mode=0o700, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='w', dir=directory, encoding='utf-8', delete=False) as f:
                temporary = f.name
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary, CONFIG_FILE)
            temporary = None
        except:
            pass
        finally:
            if temporary and os.path.exists(temporary):
                os.remove(temporary)

    @staticmethod
    def load_connection_settings():
        return ConnectionSettings.from_config(ConfigManager._read())

    @staticmethod
    def save_connection_settings(settings):
        ConfigManager.save_many(settings.to_config())

    @staticmethod
    def save_download_path(path):
        ConfigManager.save('download_path', path)

    @staticmethod
    def save_quality(quality):
        ConfigManager.save('last_quality', quality)

class VersionChecker:
    @staticmethod
    def get_latest_version():
        try:
            return EngineManager.latest_release()['tag_name']
        except Exception:
            pass
        return None

class MainWindow(AuroraWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube 下载工具")
        self.resize(1120, 820)
        self.setMinimumSize(1000, 760)

        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.download_path, last_quality = ConfigManager.load()
        self.connection = ConfigManager.load_connection_settings()
        self.cookie_file = self.connection.cookie_file
        self.current_connection = self.connection
        self._settings_ready = False
        self.worker = None
        self.pending_urls = []
        self.total_count = 0
        self.finished_count = 0
        self.current_url = None
        self.current_quality = None
        self.current_playlist = False
        self.is_paused = False
        self.engine_manager = EngineManager()
        self.update_worker = None
        self._cancel_requested = False
        self.current_version = self.engine_manager.installed_version() or '未安装'
        self.latest_version = "检查中..."

        self.init_ui()
        self._settings_ready = True
        index = self.combo_quality.findText(last_quality)
        if index >= 0:
            self.combo_quality.setCurrentIndex(index)
        self.combo_quality.currentTextChanged.connect(ConfigManager.save_quality)

        self.check_latest_version()
        self.version_timer = QTimer(self)
        self.version_timer.setInterval(86400000)
        self.version_timer.timeout.connect(self.check_latest_version)
        self.version_timer.start()

    def init_ui(self):
        build_interface(self)

    def open_latest_release(self, event):
        webbrowser.open(GITHUB_RELEASES_URL)

    def connection_from_controls(self):
        return ConnectionSettings(
            cookie_file=self.cookie_file, use_cookie=self.cb_cookie.isChecked(),
            use_proxy=self.cb_proxy.isChecked(), proxy_ip=self.proxy_ip_edit.text().strip(),
            proxy_port=self.proxy_port_edit.text().strip(), proxy_type=self.proxy_type_combo.currentText())

    def save_connection_preferences(self):
        if self._settings_ready:
            ConfigManager.save_connection_settings(self.connection_from_controls())

    def on_proxy_check_changed(self):
        enabled = self.cb_proxy.isChecked()
        for control in (self.proxy_ip_edit, self.proxy_port_edit, self.proxy_type_combo, self.btn_proxy_confirm):
            control.setEnabled(enabled)
        self.save_connection_preferences()

    def save_proxy_settings(self):
        settings = self.connection_from_controls()
        try:
            settings.proxy_url()
        except ValueError as exc:
            QMessageBox.warning(self, "代理设置", str(exc))
            return
        ConfigManager.save_connection_settings(settings)
        self.append_log("代理设置已保存。")

    def import_cookie(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 Cookie 文件", "", "Cookie 文件 (*.txt *.json);;所有文件 (*.*)")
        if not path:
            return
        try:
            with private_cookie_file(path):
                pass
        except ValueError as exc:
            QMessageBox.warning(self, "Cookie 文件", str(exc))
            return
        self.cookie_file = os.path.abspath(path)
        self.cb_cookie.blockSignals(True)
        self.cb_cookie.setChecked(True)
        self.cb_cookie.blockSignals(False)
        self.lbl_cookie_file.setText("已加载：" + os.path.basename(path))
        self.save_connection_preferences()
        self.append_log("Cookie 文件已导入；下载时使用临时副本。")

    def set_engine_version(self, version):
        self.current_version = version
        self.lbl_current.setText(version)

    def update_engine(self):
        if (self.worker and self.worker.isRunning()) or (self.update_worker and self.update_worker.isRunning()):
            return
        self.btn_update.setEnabled(False)
        self.btn_main.setEnabled(False)
        self.lbl_status.setText("正在安装／更新 yt-dlp...")
        self.update_worker = EngineUpdateWorker(self.engine_manager)
        self.update_worker.log.connect(self.append_log)
        self.update_worker.completed.connect(self.on_engine_updated)
        self.update_worker.start()

    def on_engine_updated(self, success, message):
        self.update_worker.wait()
        self.append_log(message)
        version = self.engine_manager.installed_version()
        if version:
            self.set_engine_version(version)
        self.btn_update.setEnabled(True)
        self.btn_main.setEnabled(True)
        self.lbl_status.setText("引擎更新完成" if success else "引擎更新未完成，可重试")

    def closeEvent(self, event):
        for worker in (self.worker, self.update_worker):
            if worker and worker.isRunning():
                worker.request_stop()
                if not worker.wait(5000):
                    self.append_log("正在停止后台操作，请稍后再次关闭窗口。")
                    event.ignore()
                    return
        event.accept()

    def check_latest_version(self):
        def fetch():
            latest = VersionChecker.get_latest_version()
            if latest:
                QApplication.instance().postEvent(self, UpdateVersionEvent(latest))
        from threading import Thread
        Thread(target=fetch, daemon=True).start()

    def customEvent(self, event):
        if isinstance(event, UpdateVersionEvent):
            self.update_version_label(event.latest)

    def update_version_label(self, latest):
        self.latest_version = latest
        text = latest
        style = "font-weight:bold; color:#80ead9;"
        if self.current_version != latest:
            text += " （点击查看更新）"
            style = "font-weight:bold; color:#f5cc8b;"
        self.lbl_latest.setStyleSheet(style)
        self.lbl_latest.setText(text)

    def _connect_worker(self):
        if not self.worker:
            return
        self.worker.log.connect(self.append_log)
        self.worker.status.connect(self.lbl_status.setText)
        self.worker.current_file.connect(lambda f: self.lbl_file.setText(f"当前文件：{f}"))
        self.worker.completed.connect(self.on_one_finished)
        self.worker.engine_version.connect(self.set_engine_version)

    def choose_path(self):
        folder = QFileDialog.getExistingDirectory(
            self, "选择保存文件夹", self.download_path,
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )
        if folder:
            self.download_path = folder
            self.lbl_path.setText(folder)
            self.lbl_path.setToolTip(folder)
            ConfigManager.save_download_path(folder)
            self.append_log(f"保存路径已更新：{folder}")

    def open_folder(self):
        path = os.path.abspath(self.download_path)
        if not os.path.isdir(path):
            QMessageBox.warning(self, "提示", f"文件夹不存在：\n{path}")
            return
        try:
            if platform.system() == 'Windows':
                os.startfile(path)
            elif platform.system() == 'Darwin':
                subprocess.call(['open', path])
            else:
                subprocess.call(['xdg-open', path])
            self.append_log(f"已打开文件夹：{path}")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"无法打开文件夹：\n{str(e)}")

    def toggle_main(self):
        if self.update_worker and self.update_worker.isRunning():
            return
        if self.worker and self.worker.isRunning():
            self.is_paused = True
            self.worker.request_stop()
            self.btn_main.setEnabled(False)
            self.lbl_status.setText("正在暂停...")
            return
        if self.is_paused and self.current_url:
            self.is_paused = False
            self.start_next_download(self.current_url, self.current_quality, self.current_playlist)
            return
        raw_text = self.edit_url.toPlainText().strip()
        if not raw_text:
            QMessageBox.warning(self, "提示", "请至少输入一个链接")
            return

        urls = [line.strip() for line in raw_text.splitlines() if line.strip() and line.strip().startswith(('http://', 'https://'))]

        if not urls:
            QMessageBox.warning(self, "提示", "没有找到有效的 YouTube 链接")
            return

        # 频道 + 批量警告（只针对单个频道链接）
        is_channel = any(x in urls[0].lower() for x in ['/channel/', '/@', '/c/', '/user/'])
        if is_channel and self.cb_playlist.isChecked() and len(urls) == 1:
            reply = QMessageBox.question(
                self, "频道批量下载警告",
                "检测到频道链接 + 已勾选“下载整个播放列表”，\n"
                "这将下载该频道**所有**上传视频（可能几百上千个），确定继续吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        quality = self.combo_quality.currentText()
        playlist = self.cb_playlist.isChecked()
        settings = self.connection_from_controls()
        try:
            settings.proxy_url()
            if settings.use_cookie:
                if not settings.cookie_file:
                    raise ValueError("请先导入 Cookie 文件，或取消勾选使用 Cookie。")
                with private_cookie_file(settings.cookie_file):
                    pass
        except ValueError as exc:
            QMessageBox.warning(self, "下载设置", str(exc))
            return
        self.current_connection = settings
        ConfigManager.save_connection_settings(settings)

        # 新任务开始
        self.pending_urls = urls[1:]
        self.total_count = len(urls)
        self.finished_count = 0
        self._cancel_requested = False

        self.start_next_download(urls[0], quality, playlist)

    def start_next_download(self, url, quality, playlist):
        self.current_url = url
        self.current_quality = quality
        self.current_playlist = playlist

        if self.worker and self.worker.isRunning():
            self.worker.quit()
            self.worker.wait(3000)

        self.worker = DownloadWorker(url, self.download_path, quality, playlist, manager=self.engine_manager,
                                     connection=self.current_connection)
        self._connect_worker()

        self.append_log(f"───── 开始 ({self.finished_count + 1}/{self.total_count}) ─────")
        self.append_log(f"链接：{url}")
        self.lbl_progress.setText(f"进度：{self.finished_count + 1} / {self.total_count}")

        self.worker.start()

        self.btn_update.setEnabled(False)
        self.btn_main.setEnabled(True)
        self.btn_main.setText("暂停当前")
        self.btn_main.setIcon(line_icon('pause'))
        self.download_progress.setValue(0)
        self.lbl_percent.setText('0%')
        self.lbl_speed.setText('速度：—')
        self.btn_cancel.setEnabled(True)
        self.lbl_status.setText(f"正在下载 ({self.finished_count + 1}/{self.total_count})")

    def on_one_finished(self, success, msg):
        self.worker.wait()
        self.append_log(f"───── {msg} ─────")
        self.btn_main.setEnabled(True)
        if self._cancel_requested:
            self._cancel_requested = False
            self.reset_ui()
            return
        if self.is_paused:
            self.btn_main.setText("继续下载")
            self.btn_main.setIcon(line_icon('download'))
            self.btn_update.setEnabled(True)
            self.lbl_status.setText("已暂停")
            return

        self.finished_count += 1
        self.lbl_progress.setText(f"进度：{self.finished_count} / {self.total_count}")

        if self.finished_count >= self.total_count:
            self.append_log("所有任务处理完毕")
            self.lbl_status.setText("全部完成")
            if success:
                QMessageBox.information(self, "完成", f"已处理 {self.total_count} 个任务")
            self.reset_ui()
            self.pending_urls = []
        else:
            if self.pending_urls:
                next_url = self.pending_urls.pop(0)
                self.start_next_download(next_url, self.current_quality, self.current_playlist)
            else:
                self.reset_ui()

    def cancel_all(self):
        self.pending_urls = []
        if self.worker and self.worker.isRunning():
            self._cancel_requested = True
            self.is_paused = False
            self.worker.request_stop()
            self.btn_main.setEnabled(False)
            self.btn_cancel.setEnabled(False)
            self.lbl_status.setText("正在取消...")
            return
        self.reset_ui()
        self.append_log("全部任务已取消")

    def reset_ui(self):
        self.btn_update.setEnabled(True)
        self.btn_main.setEnabled(True)
        self.total_count = 0
        self.btn_main.setText("开始下载")
        self.btn_main.setIcon(line_icon('download'))
        self.download_progress.setValue(0)
        self.lbl_percent.setText('0%')
        self.lbl_speed.setText('速度：—')
        self.btn_cancel.setEnabled(False)
        self.lbl_status.setText("就绪")
        self.lbl_progress.setText("进度： - / - ")
        self.lbl_file.setText("当前文件： - ")
        self.is_paused = False

    def append_log(self, text):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        progress = re.match(r'^\[download\]\s+(\d{1,3}(?:\.\d+)?)%\s+at\s+(.{1,32}?)\s+ETA\b', text)
        if progress:
            percent = float(progress.group(1))
            if 0 <= percent <= 100:
                self.download_progress.setValue(round(percent))
                self.lbl_percent.setText(f'{percent:g}%')
                self.lbl_speed.setText('速度：' + progress.group(2).strip())
        # QTextEdit.append auto-detects HTML, including local image references.
        self.log_area.append(html.escape(f"[{ts}] {redact_urls(text)}"))
        if any(kw in text for kw in ["[download]", "完成", "错误", "暂停", "─────"]):
            self.log_area.verticalScrollBar().setValue(self.log_area.verticalScrollBar().maximum())

class UpdateVersionEvent(QEvent):
    def __init__(self, latest):
        super().__init__(QEvent.Type.User)
        self.latest = latest

if __name__ == "__main__":
    import ctypes
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('com.yt.downloader.v3')
    except:
        pass
    app = QApplication(sys.argv)
    os.makedirs(CONFIG_DIR, mode=0o700, exist_ok=True)
    instance_lock = QLockFile(LOCK_FILE)
    if not instance_lock.tryLock(0):
        print("程序已经在运行中，或无法取得单实例锁。")
        sys.exit(1)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    try:
        exit_code = app.exec()
    finally:
        instance_lock.unlock()
    sys.exit(exit_code)
