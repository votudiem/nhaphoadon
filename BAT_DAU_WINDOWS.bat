@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo.
echo  SO MUA - TU CHUAN BI MOI TRUONG RIENG
echo  Khong can ha phien ban Python he thong.
echo.
if not exist ".runtime\venv\Scripts\python.exe" goto system_python
".runtime\venv\Scripts\python.exe" -c "import sys; assert sys.version_info >= (3,10)" >nul 2>nul
if errorlevel 1 goto system_python
".runtime\venv\Scripts\python.exe" bootstrap.py
goto result
:system_python
where py >nul 2>nul
if errorlevel 1 goto plain_python
py -3 -c "import sys; assert sys.version_info >= (3,10)" >nul 2>nul
if errorlevel 1 goto plain_python
py -3 bootstrap.py
goto result
:plain_python
where python >nul 2>nul
if errorlevel 1 goto python3
python -c "import sys; assert sys.version_info >= (3,10)" >nul 2>nul
if errorlevel 1 goto python3
python bootstrap.py
goto result
:python3
where python3 >nul 2>nul
if errorlevel 1 goto need_python
python3 -c "import sys; assert sys.version_info >= (3,10)" >nul 2>nul
if errorlevel 1 goto need_python
python3 bootstrap.py
:result
if errorlevel 1 goto fail
goto end
:need_python
echo Can Python 3.10 tro len de mo bo khoi tao. Neu da co 3.15, khong can cai lai.
echo Co the chay truc tiep: py -3 bootstrap.py
goto end
:fail
echo.
echo Giu cua so nay de xem loi. Lan dau co the can Internet de tai Python rieng.
echo Khong xoa thu muc .data. Xem HUONG_DAN_SU_DUNG.md.
:end
pause
