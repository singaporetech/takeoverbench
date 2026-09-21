@echo off
setlocal
REM Expose the local dashboard (http://localhost:5000) on a public URL so
REM participants can scan the report QR on ANY network (no joining a hotspot).
REM
REM Requires cloudflared (recommended, no account) or ngrok:
REM   cloudflared: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
REM   ngrok:       https://ngrok.com/download
REM
REM After it starts, copy the https://... URL, append /results, and paste it
REM into the dashboard "Results link" box (or set REPORT_QR_URL in .env).

where cloudflared >nul 2>&1
if %errorlevel%==0 (
    echo Starting Cloudflare quick tunnel for http://localhost:5000 ...
    echo Copy the https://...trycloudflare.com URL, add /results, and paste it
    echo into the dashboard "Results link" box.
    echo.
    cloudflared tunnel --url http://localhost:5000
    goto :eof
)

where ngrok >nul 2>&1
if %errorlevel%==0 (
    echo Starting ngrok tunnel for port 5000 ...
    echo Copy the https://... URL, add /results, and paste it into the dashboard
    echo "Results link" box.
    echo.
    ngrok http 5000
    goto :eof
)

echo Neither cloudflared nor ngrok was found on PATH.
echo Install cloudflared (no account needed) or ngrok, then run this again.
pause
