@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo.
echo  SO MUA - TRO LY HOA DON MUA VAO
echo  Du lieu chi xu ly va luu tren may nay.
echo.
if exist ".venv\Scripts\python.exe" goto check_python
where py >nul 2>nul
if errorlevel 1 goto need_python
py -3.12 -c "import sys; assert sys.maxsize > 2**32" >nul 2>nul
if errorlevel 1 goto need_python
py -3.12 -m venv .venv
if errorlevel 1 goto fail
:check_python
".venv\Scripts\python.exe" -c "import sys; assert sys.version_info[:2] == (3,12) and sys.maxsize > 2**32" >nul 2>nul
if errorlevel 1 goto wrong_venv
echo Dang kiem tra thu vien cuc bo...
".venv\Scripts\python.exe" -m pip install --no-index --find-links="vendor\windows" --require-hashes -r requirements-windows.txt
if errorlevel 1 goto fail
".venv\Scripts\python.exe" launcher.py
if errorlevel 1 goto fail
goto end
:need_python
echo Can cai Python 3.12 ban 64-bit tu python.org truoc khi chay.
echo Khi cai, bat Python Launcher. Sau do bam lai BAT_DAU_WINDOWS.bat.
goto end
:wrong_venv
echo Moi truong .venv khong phai Python 3.12 64-bit.
echo Hay giai nen goi vao thu muc moi. Khong xoa thu muc .data chua chung tu.
goto end
:fail
echo.
echo Khong khoi dong duoc. Giu cua so nay de xem loi; xem HUONG_DAN_SU_DUNG.md.
:end
pause
