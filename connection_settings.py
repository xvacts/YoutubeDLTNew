"""Downloader connection options; never persist or log cookie contents."""
import contextlib
import ipaddress
import json
import math
import os
import re
import tempfile
import warnings
from dataclasses import asdict, dataclass
from http.cookiejar import Cookie, LoadError, MozillaCookieJar
from pathlib import Path

MAX_COOKIE_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class ConnectionSettings:
    cookie_file: str = ''
    use_cookie: bool = False
    use_proxy: bool = False
    proxy_ip: str = '127.0.0.1'
    proxy_port: str = '7890'
    proxy_type: str = 'http'

    @classmethod
    def from_config(cls, data):
        if not isinstance(data, dict):
            return cls()
        defaults = cls()
        values = {}
        for key in ('cookie_file', 'proxy_ip', 'proxy_port', 'proxy_type'):
            value = data.get(key, getattr(defaults, key))
            values[key] = str(value) if isinstance(value, (str, int)) and not isinstance(value, bool) else getattr(defaults, key)
        values['use_cookie'] = data.get('use_cookie', bool(values['cookie_file'])) is True
        values['use_proxy'] = data.get('use_proxy') is True
        return cls(**values)

    def to_config(self):
        return asdict(self)

    def proxy_url(self):
        if not self.use_proxy:
            return None
        if self.proxy_type not in ('http', 'socks5', 'socks4'):
            raise ValueError('代理类型必须是 HTTP、SOCKS5 或 SOCKS4。')
        host = self.proxy_ip.strip().removeprefix('[').removesuffix(']')
        if not host or any(char.isspace() for char in host) or any(char in host for char in '/\\@?#'):
            raise ValueError('代理 IP／主机名格式不正确；此处不填写协议、路径或账号密码。')
        try:
            address = ipaddress.ip_address(host)
            host = f'[{address}]' if address.version == 6 else str(address)
        except ValueError:
            if len(host) > 253 or not all(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', part)
                                          for part in host.split('.')):
                raise ValueError('代理 IP／主机名格式不正确。') from None
        if not re.fullmatch(r'[0-9]{1,5}', self.proxy_port.strip()):
            raise ValueError('代理端口必须是 1–65535 的整数。')
        port = int(self.proxy_port)
        if not 1 <= port <= 65535:
            raise ValueError('代理端口必须是 1–65535 的整数。')
        return f'{self.proxy_type}://{host}:{port}'


def _json_cookies(text, destination):
    try:
        rows = json.loads(text)
        if isinstance(rows, dict):
            rows = rows.get('cookies')
        if not isinstance(rows, list) or not rows or len(rows) > 20000:
            raise ValueError()
        jar = MozillaCookieJar(str(destination))
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError()
            fields = {key: row.get(key, '/' if key == 'path' else '') for key in ('domain', 'path', 'name', 'value')}
            if any(not isinstance(value, str) or any(char in value for char in '\r\n\t') for value in fields.values()):
                raise ValueError()
            if not fields['domain'] or not fields['name'] or not fields['path'].startswith('/'):
                raise ValueError()
            for key in ('secure', 'httpOnly', 'session', 'hostOnly'):
                if key in row and not isinstance(row[key], bool):
                    raise ValueError()
            expires = row.get('expirationDate', row.get('expires'))
            if expires is not None and (isinstance(expires, bool) or not isinstance(expires, (int, float))
                                        or not math.isfinite(expires) or expires < 0):
                raise ValueError()
            session = row.get('session', expires is None)
            jar.set_cookie(Cookie(
                version=0, name=fields['name'], value=fields['value'], port=None, port_specified=False,
                domain=fields['domain'], domain_specified=fields['domain'].startswith('.'),
                domain_initial_dot=fields['domain'].startswith('.'), path=fields['path'], path_specified=True,
                secure=row.get('secure', False), expires=None if session else int(expires),
                discard=session, comment=None, comment_url=None,
                rest={'HTTPOnly': None} if row.get('httpOnly') else {}, rfc2109=False))
        jar.save(ignore_discard=True, ignore_expires=True)
    except (ValueError, TypeError, KeyError, OverflowError):
        raise ValueError('Cookie JSON 格式无效，请使用浏览器导出的 Cookie 数组或 Netscape 文本文件。') from None


@contextlib.contextmanager
def private_cookie_file(source):
    """Use a private per-task copy; yt-dlp must not overwrite the original export."""
    if not source:
        yield None
        return
    try:
        with Path(source).expanduser().open('rb') as stream:
            data = stream.read(MAX_COOKIE_BYTES + 1)
    except OSError:
        raise ValueError('无法读取 Cookie 文件，请重新导入可访问的文件。') from None
    if len(data) > MAX_COOKIE_BYTES:
        raise ValueError('Cookie 文件过大（上限 10 MB）。')
    try:
        text = data.decode('utf-8-sig')
    except UnicodeError:
        raise ValueError('Cookie 文件应使用 UTF-8 编码。') from None
    with tempfile.TemporaryDirectory(prefix='youtubedlt-cookies-') as directory:
        destination = Path(directory) / 'cookies.txt'
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            if not text.lstrip().startswith(('[', '{')):
                stream.write(text.replace('\r\n', '\n'))
        if text.lstrip().startswith(('[', '{')):
            _json_cookies(text, destination)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                jar = MozillaCookieJar(str(destination))
                jar.load(ignore_discard=True, ignore_expires=True)
        except (LoadError, ValueError, OSError):
            # Cookie parser errors can include the secret line: never echo them.
            raise ValueError('Cookie 文件无效，请导入 Netscape 格式文本或浏览器 Cookie JSON。') from None
        yield str(destination)
