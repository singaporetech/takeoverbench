@echo off
setlocal
REM Allow inbound connections to TakeoverBench:
REM   5000 - dashboard + participant results page (HTTP)
REM   1883 - embedded MQTT broker (HMI tablet)
REM Run this ONCE, as Administrator.

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Please right-click this file and choose "Run as administrator".
    pause
    exit /b 1
)

echo Adding inbound firewall rules for TakeoverBench...
netsh advfirewall firewall add rule name="TakeoverBench HTTP" dir=in action=allow protocol=TCP localport=5000
netsh advfirewall firewall add rule name="TakeoverBench MQTT" dir=in action=allow protocol=TCP localport=1883

echo.
echo Done. The dashboard/results page and MQTT broker are now reachable from other devices on the LAN.
pause
