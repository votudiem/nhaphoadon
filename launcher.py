"""Reuse the local app if already running, otherwise open a new instance."""
import json
from urllib.request import build_opener,ProxyHandler
import webbrowser
import subprocess
import sys
from pathlib import Path

# Loopback is intentionally local; tax sites and remote traffic keep normal proxy settings.
try:
    opener=build_opener(ProxyHandler({}))
    with opener.open('http://127.0.0.1:8765/api/health',timeout=2) as response:health=json.load(response)
    if health.get('app')!='So Mua':raise RuntimeError('Cổng 8765 đang do ứng dụng khác sử dụng.')
except (OSError,ValueError):
    raise SystemExit(subprocess.call([sys.executable,str(Path(__file__).with_name('app.py')),'--open']))
else:
    webbrowser.open('http://127.0.0.1:8765')
    print('Đã mở Sổ Mua đang chạy. Giữ cửa sổ ứng dụng ban đầu để tiếp tục sử dụng.')
