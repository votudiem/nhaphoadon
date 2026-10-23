"""Build distributions from an explicit allowlist, never include user documents."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import hashlib
import json
ROOT=Path(__file__).parent
OUT=ROOT.parent
FILES=['.gitignore','README.md','HUONG_DAN_SU_DUNG.md','TEST_REPORT.md','THIRD_PARTY_NOTICES.md','app.py','engine.py','documents.py','workspace.py','routes.py','launcher.py','requirements.txt','requirements-windows.txt','BAT_DAU_WINDOWS.bat','start.sh','package_release.py']
files=[ROOT/name for name in FILES]
for directory in ['static','assets','tests']:
    files += [p for p in (ROOT/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']
manifest=[]
for windows,name in [(False,'So_Mua_1_0_Source.zip'),(True,'So_Mua_1_0_Windows.zip')]:
    members=files+list((ROOT/'vendor/windows').glob('*.whl')) if windows else files
    if windows and len(list((ROOT/'vendor/windows').glob('*.whl')))!=7:raise RuntimeError('Thiếu bộ dependency Windows')
    target=OUT/name
    with ZipFile(target,'w',ZIP_DEFLATED) as archive:
        for path in sorted(members):archive.write(path,Path('So_Mua')/path.relative_to(ROOT))
    with ZipFile(target) as archive:
        assert archive.testzip() is None
        assert not any('/.data/' in x or '/.git/' in x or '/.venv/' in x for x in archive.namelist())
    record={'file':name,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
    manifest.append(record);print(json.dumps(record))
(OUT/'So_Mua_1_0_SHA256.json').write_text(json.dumps(manifest,indent=2)+'\n')
