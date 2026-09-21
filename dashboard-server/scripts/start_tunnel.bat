@echo off
setlocal enabledelayedexpansion
REM Expose the local dashboard (http://localhost:5000) on a public URL so
REM participants can scan the report QR on ANY network.
REM
REM It tries, in order:
REM   1. cloudflared.exe in this folder
REM   2. cloudflared.exe in the project root (dashboard-server\)
REM   3. cloudflared on PATH
REM   4. ssh -R via localhost.run (no install needed; needs outbound SSH)
REM
REM After it starts, copy the https://... URL, append /results if needed, and
REM paste it into the dashboard "Results link" box.

set "ROOT=%~dp0.."
set "CF="
if exist "%~dp0cloudflared.exe" set "CF=%~dp0cloudflared.exe"
if not defined CF if exist "%ROOT%\cloudflared.exe" set "CF=%ROOT%\cloudflared.exe"
if not defined CF (
    where cloudflared >nul 2>&1 && set "CF=cloudflared"
)

if defined CF (
    echo Starting Cloudflare tunnel with "!CF!" ...
    echo Copy the https://...trycloudflare.com URL into the dashboard "Results link" box.
    echo.
    "!CF!" tunnel --url http://localhost:5000
    goto :eof
)

where ssh >nul 2>&1
if %errorlevel%==0 (
    echo cloudflared not found - using an SSH tunnel via localhost.run ...
    echo Copy the https://... URL into the dashboard "Results link" box.
    echo.
    ssh -R 80:localhost:5000 nokey@localhost.run
    goto :eof
)

echo No tunnel tool found.
echo   - Put cloudflared.exe in this folder or in dashboard-server\, or
echo   - install cloudflared (https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/), or
echo   - enable the Windows OpenSSH Client optional feature and re-run this script.
pause
