"""Install and run the official standalone yt-dlp independently of the GUI."""
import contextlib
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests
from PyQt6.QtCore import QLockFile

API_URL = 'https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest'
RELEASE_ROOT = 'https://github.com/yt-dlp/yt-dlp/releases/download'
MIN_VERSION = (2026, 7, 4)
MAX_BINARY_BYTES = 150 * 1024 * 1024


class EngineError(RuntimeError):
    pass


class Cancelled(EngineError):
    pass


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}\.\d{1,2}\.\d{1,2}', value):
        raise EngineError('Invalid yt-dlp release version')
    result = tuple(map(int, value.split('.')))
    if result < MIN_VERSION:
        raise EngineError('yt-dlp is older than the minimum safe version')
    return result


def asset_name(system=None, machine=None):
    system = system or platform.system()
    machine = (machine or platform.machine()).lower()
    if system == 'Windows':
        return {'amd64': 'yt-dlp.exe', 'x86_64': 'yt-dlp.exe',
                'arm64': 'yt-dlp_arm64.exe', 'aarch64': 'yt-dlp_arm64.exe',
                'x86': 'yt-dlp_x86.exe', 'i386': 'yt-dlp_x86.exe'}.get(machine) or _unsupported()
    if system == 'Darwin':
        return 'yt-dlp_macos'
    if system == 'Linux':
        return {'x86_64': 'yt-dlp_linux', 'amd64': 'yt-dlp_linux',
                'aarch64': 'yt-dlp_linux_aarch64', 'arm64': 'yt-dlp_linux_aarch64'}.get(machine) or _unsupported()
    return _unsupported()


def _unsupported():
    raise EngineError('No supported standalone yt-dlp binary for this platform')


def child_environment():
    env = os.environ.copy()
    # A frozen Python/Qt parent's search paths must not leak into another binary.
    for key in ('PYTHONHOME', 'PYTHONPATH', 'QT_PLUGIN_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH'):
        env.pop(key, None)
    for key in tuple(env):
        if key.startswith('_PYI_') or key == '_MEIPASS2':
            env.pop(key, None)
    env['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
    if getattr(sys, 'frozen', False):
        original = env.pop('LD_LIBRARY_PATH_ORIG', None)
        env.pop('LD_LIBRARY_PATH', None)
        if original:
            env['LD_LIBRARY_PATH'] = original
    env['PYTHONIOENCODING'] = 'utf-8'
    return env


def process_options():
    options = {'env': child_environment()}
    if os.name == 'nt':
        options['creationflags'] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options['start_new_session'] = True
    return options


def check_cancel(cancel):
    if cancel and cancel():
        raise Cancelled('Operation cancelled')


class EngineManager:
    def __init__(self, root=None):
        self.root = Path(root or Path.home() / '.youtube_downloader' / 'engine').absolute()
        self.asset = asset_name()

    def _manifest(self):
        try:
            data = json.loads((self.root / 'active.json').read_text(encoding='utf-8'))
            version_tuple(data['version'])
            if data['asset'] != self.asset or not re.fullmatch(r'[0-9a-f]{64}', data['sha256']):
                return None
            return data
        except (OSError, ValueError, KeyError, TypeError, EngineError):
            return None

    def installed_version(self):
        data = self._manifest()
        return data['version'] if data and self._path(data['version']).is_file() else None

    def _path(self, version):
        version_tuple(version)
        return self.root / version / self.asset

    def installed_path(self):
        data = self._manifest()
        if not data:
            raise EngineError('yt-dlp is not installed; use the install/update button')
        path = self._path(data['version'])
        try:
            digest = self._hash(path)
        except OSError as exc:
            raise EngineError('Cannot read the installed yt-dlp binary') from exc
        if digest != data['sha256']:
            raise EngineError('Installed yt-dlp failed its integrity check; reinstall it')
        return path

    @staticmethod
    def _hash(path):
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        return digest.hexdigest()

    @contextlib.contextmanager
    def exclusive(self):
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock = QLockFile(str(self.root / 'engine.lock'))
        if not lock.tryLock(0):
            raise EngineError('yt-dlp is busy downloading or updating; try again afterwards')
        try:
            yield
        finally:
            lock.unlock()

    @staticmethod
    def latest_release():
        with requests.get(API_URL, timeout=(10, 20), headers={'Accept': 'application/vnd.github+json'}) as response:
            response.raise_for_status()
            release = response.json()
        version_tuple(release.get('tag_name'))
        if release.get('prerelease') or release.get('draft'):
            raise EngineError('Expected an official stable release')
        return release

    def ensure(self, log=lambda message: None, cancel=None, update=False):
        """Caller holds exclusive(); switch active metadata only after verification."""
        check_cancel(cancel)
        if self.installed_version() and not update:
            return self.installed_path()
        release = self.latest_release()
        version = release['tag_name']
        current = self.installed_version()
        if current and version_tuple(version) < version_tuple(current):
            raise EngineError('Refusing to downgrade the installed yt-dlp')
        assets = [a for a in release.get('assets', []) if a.get('name') == self.asset]
        if len(assets) != 1:
            raise EngineError('Official release does not contain the required binary')
        asset = assets[0]
        digest = asset.get('digest', '')
        if not re.fullmatch(r'sha256:[0-9a-f]{64}', digest):
            raise EngineError('Official release has no usable SHA-256 digest; update cancelled')
        expected = digest.removeprefix('sha256:')
        size = asset.get('size')
        if type(size) is not int or not 0 < size <= MAX_BINARY_BYTES:
            raise EngineError('Invalid official binary size')
        url = f'{RELEASE_ROOT}/{version}/{self.asset}'
        if asset.get('browser_download_url') != url:
            raise EngineError('Unexpected release download location')
        destination = self._path(version)
        if current == version:
            try:
                return self.installed_path()
            except EngineError:
                pass  # Reinstall a damaged current binary from the verified source.
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = None
        try:
            log(f'Downloading official yt-dlp {version} ({self.asset})...')
            start = time.monotonic()
            with tempfile.NamedTemporaryFile(dir=destination.parent, suffix='.exe' if os.name == 'nt' else '.part', delete=False) as stream:
                temporary = Path(stream.name)
                actual = hashlib.sha256()
                count = 0
                with requests.get(url, stream=True, timeout=(10, 20)) as response:
                    response.raise_for_status()
                    if not response.url.startswith('https://'):
                        raise EngineError('Refusing an insecure download redirect')
                    for chunk in response.iter_content(1024 * 256):
                        check_cancel(cancel)
                        if time.monotonic() - start > 300:
                            raise EngineError('yt-dlp download exceeded its time limit')
                        count += len(chunk)
                        if count > size or count > MAX_BINARY_BYTES:
                            raise EngineError('Downloaded binary exceeds the expected size')
                        stream.write(chunk)
                        actual.update(chunk)
                stream.flush()
                os.fsync(stream.fileno())
            if count != size or actual.hexdigest() != expected:
                raise EngineError('yt-dlp size or SHA-256 verification failed; old version retained')
            check_cancel(cancel)
            temporary.chmod(0o700)
            from processes import start_process, ProcessTree
            with start_process([str(temporary), '--ignore-config', '--no-plugin-dirs', '--version'],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               encoding='utf-8', errors='replace') as probe:
                tree = ProcessTree(probe)
                try:
                    stdout, _ = probe.communicate(timeout=30)
                    if probe.returncode or stdout.strip() != version:
                        raise EngineError('New yt-dlp failed its startup/version check; old version retained')
                finally:
                    tree.close()
            check_cancel(cancel)
            os.replace(temporary, destination)
            temporary = None
            metadata = {'version': version, 'asset': self.asset, 'sha256': expected}
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.root, delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(metadata, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.root / 'active.json')
            temporary = None
            log(f'yt-dlp {version} installed and verified.')
            return destination
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)
