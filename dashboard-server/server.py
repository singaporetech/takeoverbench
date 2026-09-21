"""
server.py
TakeoverBench Flask server.
CARLA connects via dashboard button — no auto-launch on startup.
"""

from flask import Flask, jsonify, request, render_template, Response, redirect, url_for, send_file
import threading
import uuid
import time
import json
import signal
import sys
import os
import config
from datetime import datetime
from collections import deque
import sim as runner
from sim.constants import ExperimentPhase
from sim.mqtt import mqtt_manager
from sim.presets import PRESETS, get_preset, preset_to_scenario_config
print(f"[INIT] CARLA host: {config.CARLA_HOST}:{config.CARLA_PORT}")

app = Flask(__name__)
app.jinja_env.auto_reload = True       # reload HTML templates on every request
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # no cache for static files (JS/CSS)

# ── Embedded MQTT Broker (started deferred in __main__) ──
_broker_info = None
_start_broker = None
try:
    from mqtt_broker import start_broker as _start_broker
except ImportError:
    print("[BROKER] mqtt_broker.py not found — MQTT broker disabled")

# ── Event log (thread-safe ring buffer) ──
_event_log = deque(maxlen=200)
_event_log_lock = threading.Lock()

def _log(msg, level="info"):
    ts = time.strftime("%H:%M:%S")
    with _event_log_lock:
        _event_log.append({"ts": ts, "msg": msg, "level": level})
    print(f"[{ts}] {msg}")

def _on_mqtt_message(client, userdata, message):
    """Handle incoming MQTT messages — routes by JSON src/type fields."""
    payload = message.payload.decode("utf-8", errors="replace")
    _log(f"MQTT ← [{message.topic}] {payload}", "mqtt")

    try:
        data = json.loads(payload)
        src = data.get("src", "")
        msg_type = data.get("type", "")

        if src == "hmi" and msg_type == "pong":
            with runner.state_lock:
                runner.state["hmi_connected"] = True
                runner.state["hmi_design"] = data.get("design", {})
            _log("HMI handshake complete", "ok")
            # Save design JSON
            config_dir = config.RUNS_DIR
            config_dir.mkdir(exist_ok=True)
            with open(config_dir / "session_hmi_config.json", "w") as f:
                json.dump(data.get("design", {}), f, indent=2)

        elif src == "hmi" and msg_type in ("tor_start_ack", "tor_end_ack"):
            _log(f"HMI acknowledged {msg_type}", "mqtt")

        elif src == "hmi" and msg_type == "heartbeat":
            # Track last heartbeat timestamp (used by heartbeat monitor for timeout detection)
            # NOTE: heartbeat does NOT auto-connect — only explicit ping-pong
            #       (via /api/hmi-test or pong message) sets hmi_connected = True
            with runner.state_lock:
                runner.state["last_heartbeat_ts"] = time.time()

    except (json.JSONDecodeError, Exception):
        pass  # non-JSON message (legacy format), ignore or log is enough


# ─────────────────────────────────────────
# SETUP GATE — redirect to /setup if hardware not locked
# ─────────────────────────────────────────
@app.route("/")
def index():
    with runner.state_lock:
        locked = runner.state.get("hardware_locked", False)
    if not locked:
        return redirect(url_for("setup"))
    return render_template("dashboard.html")


@app.route("/setup")
def setup():
    return render_template("setup.html")


# ─────────────────────────────────────────
# VIDEO FEED
# ─────────────────────────────────────────
from sim.video_feed import frame_generator


@app.route("/video_feed")
def video_feed():
    return Response(frame_generator(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")


# ─────────────────────────────────────────
# MANUAL CARLA CONNECT
# ─────────────────────────────────────────
@app.route("/connect-carla", methods=["POST"])
def connect_carla():
    with runner.state_lock:
        if runner.state["connected"]:
            return jsonify({"status": "ok", "message": "Already connected"})

    def _do_connect():
        _log("Connecting to CARLA...", "accent")
        success = runner.connect_to_carla()
        if success:
            _log("CARLA connected.", "ok")
        else:
            _log("CARLA connection failed.", "error")
        return success

    result = {"success": False}
    def _thread():
        result["success"] = _do_connect()
    t = threading.Thread(target=_thread, daemon=True)
    t.start()
    t.join(timeout=120)

    if result["success"]:
        return jsonify({"status": "ok", "message": "CARLA connected"})
    else:
        return jsonify({"status": "error", "error": "Could not connect to or launch CARLA. Check terminal for details."}), 500


# ─────────────────────────────────────────
# DISCONNECT ROUTES — allow reconnection from setup page
# ─────────────────────────────────────────
@app.route("/disconnect-carla", methods=["POST"])
def disconnect_carla():
    with runner.state_lock:
        runner.state["connected"] = False
    _log("CARLA disconnected via setup page", "warn")
    return jsonify({"status": "ok"})


@app.route("/disconnect-hmi", methods=["POST"])
def disconnect_hmi():
    with runner.state_lock:
        runner.state["hmi_connected"] = False
    _log("HMI disconnected via setup page", "warn")
    return jsonify({"status": "ok"})


# ─────────────────────────────────────────
# STATUS
# ─────────────────────────────────────────
@app.route("/status")
def status():
    with runner.state_lock:
        s = runner.state
        return jsonify({
            "connected":           s["connected"],
            "scenario_running":    s["scenario_running"],
            "recording":           s["recording"],
            "run_id":              s["run_id"],
            "tor_triggered":       s["tor_triggered"],
            "tor_timestamp":       s["tor_timestamp"],
            "tor_phase":           s.get("tor_phase", "idle"),
            "tor_countdown_s":     s.get("tor_countdown_s", 0),
            "autopilot_engaged":   s["autopilot_engaged"],
            "telemetry":           s["latest_telemetry"],
            "available_vehicles":  s["available_vehicles"],
            "scenario_config":     s["scenario_config"],
            "hardware_locked":     s["hardware_locked"],
            "hardware_config":     s["hardware_config"],   # always include
            "preset_queue":        s["preset_queue"],
            "active_preset_index": s["active_preset_index"],
            "session_run_count":   len(s["session_runs"]),
            "participant_id":      s.get("participant_id", ""),
            "active_set_id":       s.get("active_set_id"),
            "active_set_name":     s.get("active_set_name"),
            "next_preset":         _get_next_preset(s),
            "experiment_phase":    s.get("experiment_phase", ExperimentPhase.IDLE),
            "hmi_connected":       s.get("hmi_connected", False),
        })

def _get_next_preset(state):
    """Return the next preset in the queue (or None).

    While a run is active, ``active_preset_index`` points at the *current*
    preset, so the next is ``idx + 1``. Once a run auto-ends, telemetry
    advances the index to the *next* preset, so the next is ``idx``.
    """
    queue = state.get("preset_queue", [])
    idx = state.get("active_preset_index", 0)
    if state.get("scenario_running"):
        idx += 1
    if queue and 0 <= idx < len(queue):
        return get_preset(queue[idx])
    return None


# ─────────────────────────────────────────
# HARDWARE / FIDELITY CONFIG
# ─────────────────────────────────────────
@app.route("/fidelity-rules")
def fidelity_rules():
    """Return shared fidelity data for client-side rendering.

    Returns score maps, warning rules, and tier thresholds so the
    setup page can evaluate warnings locally without duplicating
    the logic from :mod:`sim.fidelity`.
    """
    from sim.fidelity import VISUAL_SCORES, MOTION_SCORES, PHYSICAL_SCORES, WARNING_RULES

    return jsonify({
        "score_maps": {
            "visual": VISUAL_SCORES,
            "motion": MOTION_SCORES,
            "physical": PHYSICAL_SCORES,
        },
        "warning_rules": WARNING_RULES,
        "tiers": {"low_max": 7, "medium_max": 11},
    })


@app.route("/configure-hardware", methods=["POST"])
def configure_hardware():
    from sim.fidelity import calculate_fidelity
    hw_config = request.get_json()
    if not hw_config:
        return jsonify({"error": "No JSON body"}), 400

    result = calculate_fidelity(hw_config)

    with runner.state_lock:
        runner.state["hardware_config"] = result
        runner.state["hardware_locked"] = True
        # Fresh hardware config = fresh session — clear previous runs
        runner.state["session_runs"] = []
        runner.state["session_dir"] = None
        runner.state["preset_queue"] = []
        runner.state["active_preset_index"] = 0
        runner.state["active_set_id"] = None
        runner.state["active_set_name"] = None
        # Also save participant ID if provided
        pid = hw_config.get("participant_id", "").strip()
        if pid:
            runner.state["participant_id"] = pid

    _log("Hardware config locked in.", "ok")
    return jsonify({**result, "hardware_locked": True})


@app.route("/reset-hardware", methods=["POST"])
def reset_hardware():
    """Allow researcher to go back to setup page and re-select hardware."""
    with runner.state_lock:
        if runner.state["recording"]:
            return jsonify({"error": "Cannot reset hardware mid-run"}), 409
        runner.state["hardware_locked"] = False
        runner.state["hardware_config"] = {}
        runner.state["session_dir"] = None
    return jsonify({"status": "reset"})


# ─────────────────────────────────────────
# SCENARIO SETS
# ─────────────────────────────────────────
@app.route("/presets")
def get_presets():
    from sim.presets import PRESETS
    return jsonify(PRESETS)


@app.route("/scenario-sets")
def get_scenario_sets():
    from sim.presets import BUILTIN_SETS
    return jsonify([{**s, "builtin": True} for s in BUILTIN_SETS])


@app.route("/load-scenario-set", methods=["POST"])
def load_scenario_set():
    data = request.get_json()
    set_id = data.get("set_id", "")
    from sim.presets import BUILTIN_SETS
    found = None
    for s in BUILTIN_SETS:
        if s["id"] == set_id:
            found = s
            break
    if not found:
        return jsonify({"error": f"Scenario set '{set_id}' not found"}), 404

    with runner.state_lock:
        runner.state["preset_queue"] = list(found["preset_ids"])
        runner.state["active_preset_index"] = 0
        runner.state["active_set_id"] = found["id"]
        runner.state["active_set_name"] = found["name"]
        runner.state["session_runs"] = []       # fresh set = fresh session
    _log(f"Loaded scenario set: {found['name']} ({len(found['preset_ids'])} runs)", "accent")
    return jsonify({"status": "loaded", "queue": found["preset_ids"], "name": found["name"], "set_id": found["id"]})


# ─────────────────────────────────────────
# CLEAR QUEUE — BUG-01 fix: this route was missing, causing 404 on every Clear Queue click
# ─────────────────────────────────────────
@app.route("/clear-queue", methods=["POST"])
def clear_queue():
    with runner.state_lock:
        if runner.state.get("scenario_running"):
            return jsonify({"error": "Cannot clear queue while a scenario is running."}), 409
        runner.state["preset_queue"] = []
        runner.state["active_preset_index"] = 0
        runner.state["active_set_id"] = None
        runner.state["active_set_name"] = None
    _log("Scenario queue cleared", "info")
    return jsonify({"status": "ok"})


# ─────────────────────────────────────────
# SCENARIO CONFIG (direct, used internally)
# ─────────────────────────────────────────
@app.route("/configure-scenario", methods=["POST"])
def configure_scenario():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400
    with runner.state_lock:
        runner.state["scenario_config"].update(data)
        cfg = dict(runner.state["scenario_config"])
    return jsonify({"status": "ok", "config": cfg})


@app.route("/change-map", methods=["POST"])
def change_map():
    data = request.get_json()
    map_name = data.get("map", "Town06")
    runner.load_map(map_name)
    return jsonify({"status": "ok", "map": map_name})


# ─────────────────────────────────────────
# START SCENARIO
# ─────────────────────────────────────────
@app.route("/start-scenario", methods=["POST"])
def start_scenario():
    with runner.state_lock:
        if not runner.state["connected"]:
            return jsonify({"error": "CARLA not connected."}), 400
        if not runner.state["hardware_locked"]:
            return jsonify({"error": "Hardware not configured. Complete setup first."}), 403
        if runner.state["scenario_running"]:
            return jsonify({"error": "Scenario already running. End it first."}), 409

        # If queue is active, load the next preset config
        queue = runner.state["preset_queue"]
        idx   = runner.state["active_preset_index"]
        active_preset = None

        if queue and idx < len(queue):
            preset = get_preset(queue[idx])
            if preset:
                runner.state["scenario_config"].update(preset_to_scenario_config(preset))
                active_preset = preset
                _log(f"Loading queued preset {idx+1}/{len(queue)}: {preset['name']}", "ok")

    result_container = {"success": False, "run_id": None}

    def _do_setup():
        run_id = str(uuid.uuid4())[:8]
        runner.clear_message()  # clear the participant-facing CARLA message
        success = runner.setup_scenario()
        if success:
            # Ensure session folder exists (creates once, reuses)
            with runner.state_lock:
                if "session_dir" not in runner.state or not runner.state["session_dir"]:
                    from config import get_session_dir
                    pid = runner.state.get("participant_id", "unknown")
                    runner.state["session_dir"] = get_session_dir(pid)
            # Copy HMI config into the session folder if it exists
            import shutil
            hmi_config = config.RUNS_DIR / "session_hmi_config.json"
            if hmi_config.exists():
                shutil.copy2(hmi_config, runner.state["session_dir"] / "session_hmi_config.json")
            runner.start_recording(run_id)
            # Training presets (is_training=True): don't record data
            if active_preset and active_preset.get("is_training"):
                with runner.state_lock:
                    runner.state["recording"] = False
            result_container["success"] = True
            result_container["run_id"] = run_id

    t = threading.Thread(target=_do_setup)
    t.start()
    t.join(timeout=30)

    if result_container["success"]:
        _log(f"Scenario started: {result_container['run_id']}", "ok")
        return jsonify({
            "status":         "recording",
            "run_id":         result_container["run_id"],
            "active_preset":  active_preset,
            "scenario_running": True,
        })
    else:
        return jsonify({"error": "Failed to start scenario. Check terminal."}), 500


# ─────────────────────────────────────────
# HMI (Human-Machine Interface)
# ─────────────────────────────────────────
@app.route("/api/hmi-test", methods=["POST"])
def hmi_test():
    """3-step HMI connection test.

    Step 1: Ping → wait for pong (max 15s)
    Step 2: Publish tor_start → wait for ack
    Step 3: Wait 5s → publish tor_end → wait for ack
    """
    if not mqtt_manager.available:
        return jsonify({"error": "MQTT not available"}), 503

    results = {"ping": False, "tor_start": False, "tor_end": False}
    ping_design = None

    # Clear any old ack state
    with runner.state_lock:
        runner.state["_hmi_test_pong"] = None
        runner.state["_hmi_test_tor_start_ack"] = None
        runner.state["_hmi_test_tor_end_ack"] = None

    # Override message handler temporarily to capture test responses
    original_handler = mqtt_manager.client.on_message if mqtt_manager.client else None

    def _test_handler(client, userdata, message):
        """Capture test responses while preserving normal logging."""
        payload = message.payload.decode("utf-8", errors="replace")
        _log(f"MQTT ← [{message.topic}] {payload}", "mqtt")
        try:
            data = json.loads(payload)
            if data.get("src") == "hmi" and data.get("type") == "pong":
                with runner.state_lock:
                    runner.state["_hmi_test_pong"] = data
            elif data.get("src") == "hmi" and data.get("type") == "tor_start_ack":
                with runner.state_lock:
                    runner.state["_hmi_test_tor_start_ack"] = data
            elif data.get("src") == "hmi" and data.get("type") == "tor_end_ack":
                with runner.state_lock:
                    runner.state["_hmi_test_tor_end_ack"] = data
        except Exception:
            pass

    mqtt_manager.set_message_handler(_test_handler)

    try:
        # Step 1: Ping → wait for pong
        mqtt_manager.publish_ping()
        for _ in range(15):
            time.sleep(1)
            with runner.state_lock:
                pong = runner.state.get("_hmi_test_pong")
            if pong:
                results["ping"] = True
                ping_design = pong.get("design")
                break

        if not results["ping"]:
            return jsonify({"error": "No pong from HMI within 15s"}), 408

        # Step 2: Publish tor_start test → wait for ack
        mqtt_manager.publish_tor_start("test", ttc=3.0, extra={"timestamp": datetime.now().isoformat()})
        for _ in range(5):
            time.sleep(1)
            with runner.state_lock:
                ack = runner.state.get("_hmi_test_tor_start_ack")
            if ack:
                results["tor_start"] = True
                break

        # Step 3: Wait 5s, publish tor_end → wait for ack
        time.sleep(5)
        mqtt_manager.publish_tor_end("test", extra={"timestamp": datetime.now().isoformat()})
        for _ in range(5):
            time.sleep(1)
            with runner.state_lock:
                ack = runner.state.get("_hmi_test_tor_end_ack")
            if ack:
                results["tor_end"] = True
                break

    finally:
        mqtt_manager.set_message_handler(original_handler)

    all_ok = all(results.values())
    if all_ok and ping_design:
        with runner.state_lock:
            runner.state["hmi_connected"] = True
            runner.state["hmi_design"] = ping_design
        config_dir = config.RUNS_DIR
        config_dir.mkdir(exist_ok=True)
        with open(config_dir / "session_hmi_config.json", "w") as f:
            json.dump(ping_design, f, indent=2)
        _log("HMI test passed — design saved", "ok")

    return jsonify({
        "status": "ok" if all_ok else "partial",
        "results": results,
        "design": ping_design,
    })


@app.route("/api/hmi-status")
def hmi_status():
    with runner.state_lock:
        return jsonify({
            "connected": runner.state.get("hmi_connected", False),
            "last_heartbeat_ts": runner.state.get("last_heartbeat_ts"),
            "design": runner.state.get("hmi_design", {}),
        })


# ── Heartbeat monitor ──
def _start_heartbeat_monitor():
    """Background thread: monitors HMI heartbeat, disconnects after 15s silence."""
    from sim.constants import HMI_HEARTBEAT_TIMEOUT_S, HMI_HEARTBEAT_INTERVAL_S

    def _monitor():
        while True:
            time.sleep(HMI_HEARTBEAT_INTERVAL_S)
            with runner.state_lock:
                last_ts = runner.state.get("last_heartbeat_ts")
                connected = runner.state.get("hmi_connected", False)
            if connected and last_ts is not None:
                elapsed = time.time() - last_ts
                if elapsed > HMI_HEARTBEAT_TIMEOUT_S:
                    with runner.state_lock:
                        runner.state["hmi_connected"] = False
                    _log("HMI heartbeat lost — disconnected", "warn")

    threading.Thread(target=_monitor, daemon=True).start()


# ─────────────────────────────────────────
# EVENT LOG
# ─────────────────────────────────────────
@app.route("/event-log")
def event_log():
    with _event_log_lock:
        return jsonify(list(_event_log))


# ─────────────────────────────────────────
# PDF REPORT
# ─────────────────────────────────────────
@app.route("/download-report")
def download_report():
    from sim.report import generate_session_report

    with runner.state_lock:
        session_runs = list(runner.state["session_runs"])
        hw           = dict(runner.state.get("hardware_config", {}))
        output_dir   = runner.state.get("session_dir")

    if not session_runs:
        return jsonify({"error": "No runs completed this session"}), 400

    path = generate_session_report(session_runs, hw, output_dir=output_dir)
    return send_file(
        path,
        as_attachment=True,
        download_name="takeoverbench_session_report.pdf",
    )


# ─────────────────────────────────────────
# GRACEFUL SHUTDOWN
# ─────────────────────────────────────────
def _cleanup():
    print("[Server] Cleaning up...")
    def _do():
        runner.disconnect_carla()
    t = threading.Thread(target=_do, daemon=True)
    t.start()
    t.join(timeout=5)
    mqtt_manager.stop()


# ─────────────────────────────────────────
# PORT / LAUNCH HELPERS
# ─────────────────────────────────────────
from sim.port_utils import ensure_port_free


# ─────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────
if __name__ == "__main__":
    import atexit
    atexit.register(_cleanup)

    def _signal_handler(signum, frame):
        sys.exit(0)
    signal.signal(signal.SIGINT,  _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    try:
        import ctypes
        _kernel32 = ctypes.windll.kernel32
        _handler = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)(
            lambda event: (_cleanup(), True)[1] if event == 2 else False
        )
        _kernel32.SetConsoleCtrlHandler(_handler, True)
    except Exception:
        pass

    print("=" * 50)
    print("  TakeoverBench Server")
    print("=" * 50)

    # Free MQTT port
    ensure_port_free(config.MQTT_HOST, config.MQTT_PORT,
                     config.MQTT_PORT_KILL_MODE, "MQTT")

    # Start MQTT broker. The broker binds to config.MQTT_HOST (set 0.0.0.0 in .env
    # for LAN access). The MQTT client always connects via localhost.
    _broker_info = None
    if _start_broker:
        _broker_info = _start_broker(config.MQTT_HOST, config.MQTT_PORT)

    if _broker_info:
        mqtt_manager.connect("127.0.0.1", _broker_info[2])
        mqtt_manager.set_message_handler(_on_mqtt_message)
        print(f"[MQTT] Broker listening on {_broker_info[1]}:{_broker_info[2]}")
    _start_heartbeat_monitor()

    # Start Flask (CARLA connects later via dashboard button)
    app.run(host=config.FLASK_HOST, port=config.FLASK_PORT, debug=False, threaded=True)
