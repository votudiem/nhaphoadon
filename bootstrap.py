"""Start Sổ Mua independently of the user's Python minor version.

This module uses only the Python standard library (Python 3.10+). The application
and native dependencies run on a separate, tested CPython 3.12 runtime.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
import zipfile

IS_WINDOWS=sys.platform=='win32'
ROOT=Path(__file__).resolve().parent
RUNTIME=ROOT/'.runtime'
VENV=RUNTIME/'venv'
RUNTIME_VERSION=(3,12)
UV_VERSION='0.12.23'
DEPENDENCIES=['openpyxl','pypdf','reportlab','PIL','pypdfium2','charset_normalizer']

class SetupError(RuntimeError):
    pass

def environment_python(folder):
    return Path(folder)/('Scripts/python.exe' if IS_WINDOWS else 'bin/python')

def inspect_python(executable):
    script="import json,sys;print(json.dumps({'version':list(sys.version_info[:2]),'bits':64 if sys.maxsize>2**32 else 32,'executable':sys.executable}))"
    try:
        result=subprocess.run([str(executable),'-I','-c',script],capture_output=True,text=True,timeout=20)
        if result.returncode:return None
        return json.loads(result.stdout)
    except (OSError,ValueError,subprocess.TimeoutExpired):return None

def is_runtime(info):
    return bool(info and tuple(info.get('version',[]))==RUNTIME_VERSION and info.get('bits')==64)

def command(args,env=None):
    result=subprocess.run([str(x) for x in args],cwd=ROOT,env=env)
    if result.returncode:raise SetupError('Bước chuẩn bị không thành công. Xem lỗi ở trên; giữ nguyên thư mục .data và thử lại khi kết nối Internet ổn định.')

def runtime_environment():
    env=os.environ.copy()
    env.update(UV_PYTHON_INSTALL_DIR=str(RUNTIME/'python'),UV_PYTHON_BIN_DIR=str(RUNTIME/'bin'),UV_CACHE_DIR=str(RUNTIME/'cache'),UV_SYSTEM_CERTS='true')
    return env

@contextmanager
def setup_lock():
    RUNTIME.mkdir(parents=True,exist_ok=True)
    handle=(RUNTIME/'bootstrap.lock').open('a+b')
    if handle.seek(0,2)==0:handle.write(b'0');handle.flush()
    handle.seek(0)
    locked=False
    try:
        try:
            if IS_WINDOWS:
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            locked=True
        except OSError as exc:raise SetupError('Một cửa sổ khác đang chuẩn bị ứng dụng. Hãy chờ cửa sổ đó hoàn tất.') from exc
        yield
    finally:
        if locked:
            handle.seek(0)
            if IS_WINDOWS:
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(),fcntl.LOCK_UN)
        handle.close()

def bundled_uv():
    """Extract only the executable from a hash-verified official wheel."""
    metadata=json.loads((ROOT/'bootstrap-tools.json').read_text(encoding='utf-8'))
    if metadata['version']!=UV_VERSION:raise SetupError('Metadata công cụ khởi tạo không đúng phiên bản.')
    name=metadata['wheel']
    if Path(name).name!=name:raise SetupError('Đường dẫn công cụ khởi tạo không hợp lệ.')
    wheel=ROOT/'vendor'/'bootstrap'/name
    if not wheel.exists():return None
    if hashlib.sha256(wheel.read_bytes()).hexdigest()!=metadata['sha256']:
        raise SetupError('Checksum công cụ khởi tạo không khớp. Tải lại gói Sổ Mua; không dùng file bị thay đổi.')
    with zipfile.ZipFile(wheel) as archive:
        content=archive.read('uv-'+UV_VERSION+'.data/scripts/uv.exe')
    executable=RUNTIME/'tools'/'uv.exe';executable.parent.mkdir(parents=True,exist_ok=True)
    # Never trust a previously extracted executable without checking against the wheel.
    if not executable.exists() or hashlib.sha256(executable.read_bytes()).digest()!=hashlib.sha256(content).digest():
        temporary=executable.with_suffix('.tmp');temporary.write_bytes(content);temporary.replace(executable)
    return executable

def get_uv():
    if IS_WINDOWS:
        executable=bundled_uv()
        if executable:return executable
    executable=shutil.which('uv')
    if executable:return Path(executable)
    # Source-only packages can install the pinned tool into a separate bootstrap
    # environment, without modifying the user's global Python or pip.
    tools=RUNTIME/('bootstrap-'+sys.implementation.cache_tag)
    python=environment_python(tools)
    if inspect_python(python) is None:
        command([sys.executable,'-m','venv',tools])
    executable=tools/('Scripts/uv.exe' if IS_WINDOWS else 'bin/uv')
    command([python,'-m','pip','install','--only-binary=:all:','uv=='+UV_VERSION])
    return executable

def ensure_runtime():
    python=environment_python(VENV)
    if is_runtime(inspect_python(python)):return python
    if VENV.exists():
        backup=RUNTIME/'backups'/('venv-'+uuid.uuid4().hex[:12]);backup.parent.mkdir(parents=True,exist_ok=True)
        VENV.rename(backup)
        print('Đã giữ lại môi trường cũ trong .runtime/backups; dữ liệu .data không thay đổi.',flush=True)
    current=inspect_python(sys.executable)
    if is_runtime(current):
        command([sys.executable,'-m','venv',VENV])
    else:
        print('Đang chuẩn bị Python riêng cho Sổ Mua. Bạn có thể giữ nguyên Python hệ thống; lần đầu cần Internet.',flush=True)
        uv=get_uv();env=runtime_environment()
        command([uv,'--no-config','--system-certs','python','install','--no-bin','--no-registry','3.12'],env)
        command([uv,'--no-config','--system-certs','venv','--managed-python','--python','3.12','--seed',VENV],env)
    if not is_runtime(inspect_python(python)):raise SetupError('Không tạo được môi trường Python riêng. Xem thông báo ở trên.')
    return python

def dependency_fingerprint():
    digest=hashlib.sha256()
    for name in ['requirements.txt','requirements-windows.txt']:
        digest.update(name.encode());digest.update((ROOT/name).read_bytes())
    digest.update(sys.platform.encode())
    return digest.hexdigest()

def imports_work(python):
    script='import importlib;'+''.join('importlib.import_module('+repr(name)+');' for name in DEPENDENCIES)
    try:return subprocess.run([str(python),'-I','-c',script],cwd=ROOT,capture_output=True,timeout=30).returncode==0
    except (OSError,subprocess.TimeoutExpired):return False

def install_dependencies(python):
    marker=RUNTIME/'ready.json';fingerprint=dependency_fingerprint()
    try:previous=json.loads(marker.read_text(encoding='utf-8'))
    except (OSError,ValueError):previous={}
    if previous.get('fingerprint')==fingerprint and imports_work(python):return
    print('Đang chuẩn bị thư viện ứng dụng…',flush=True)
    wheels=ROOT/'vendor'/'windows'
    if IS_WINDOWS and len(list(wheels.glob('*.whl')))>=7:
        command([python,'-m','pip','install','--no-index','--find-links',wheels,'--require-hashes','-r',ROOT/'requirements-windows.txt'])
    else:
        command([python,'-m','pip','install','--only-binary=:all:','-r',ROOT/'requirements.txt'])
    command([python,'-m','pip','check'])
    if not imports_work(python):raise SetupError('Thư viện chưa tải được. Giữ thông báo lỗi để kiểm tra; không xóa dữ liệu.')
    marker.write_text(json.dumps({'fingerprint':fingerprint,'runtime':'3.12'}),encoding='utf-8')

def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args(argv)
    if sys.version_info<(3,10):
        print('Cần Python 3.10 trở lên để mở bộ khởi tạo. Không cần gỡ hoặc hạ phiên bản Python đang có.');return 1
    try:
        with setup_lock():
            python=ensure_runtime();install_dependencies(python)
        if args.prepare_only:print('Môi trường Sổ Mua đã sẵn sàng.');return 0
        return subprocess.call([str(python),str(ROOT/'launcher.py')],cwd=ROOT)
    except (SetupError,OSError,subprocess.SubprocessError,ValueError,KeyError,zipfile.BadZipFile) as exc:
        print('\nKhông khởi động được Sổ Mua: '+str(exc),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
