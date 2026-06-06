@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   EU4 陪玩军师  启动中...
echo ============================================

REM 用 miniconda 的 python；如不对请改成你的 python 路径
set PY=python

REM 可选：手动指定存档文件夹（默认自动找 Documents / OneDrive）
REM set EU4_SAVE_DIR=C:\Users\你\Documents\Paradox Interactive\Europa Universalis IV\save games

start "" /min %PY% -m uvicorn server:app --host 127.0.0.1 --port 8777

REM 等服务起来
timeout /t 3 /nobreak >nul

REM 用 Chrome 开一个干净的 app 窗口（无地址栏/标签）
set CHROME="C:\Program Files\Google\Chrome\Application\chrome.exe"
if not exist %CHROME% set CHROME="C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if exist %CHROME% (
  start "" %CHROME% --app=http://127.0.0.1:8777 --window-size=480,900
) else (
  start "" http://127.0.0.1:8777
)

echo.
echo 面板已开。想把窗口置顶贴在游戏上，运行同目录的 pin_topmost.ps1
echo 关闭：关掉这个黑窗口即可。
pause
