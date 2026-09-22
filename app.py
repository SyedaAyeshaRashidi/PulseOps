from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from collector import get_metrics
from docker_health import check_containers
from traffic_monitor import count_recent_requests
from alerts import send_alert
from database import db, MetricHistory, AlertHistory
import docker
import threading
import time
import os

app = Flask(__name__)

# 1. Database Path VM Fix
DB_DIR = os.getenv('DATA_DIR', '/home/vboxuser/pulseops-data')
os.makedirs(DB_DIR, exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(DB_DIR, "pulseops.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

socketio = SocketIO(app)
client = docker.from_env()

monitored_containers = set()
recent_events = []

sys_streak = {"cpu": 0, "ram": 0, "disk": 0}
sys_alerted = {"cpu": False, "ram": False, "disk": False}
container_mem_warned = {}
container_cpu_warned = {}
previously_running = set()
already_alerted_crash = set()
manually_stopped = set()

def log_event(msg, is_alert=False):
    t = time.strftime("%H:%M:%S")
    prefix = "ALERT" if is_alert else "INFO"
    recent_events.insert(0, f"[{t}] [{prefix}] {msg}")
    if len(recent_events) > 5:
        recent_events.pop()

def alert(subject, body, log_msg):
    send_alert(subject, body)
    log_event(log_msg, is_alert=True)
    with app.app_context():
        db.session.add(AlertHistory(subject=subject, message=body))
        db.session.commit()

def check_system_alerts(metrics):
    checks = {
        "cpu":  (metrics["cpu_percent"],  85, "System CPU critical"),
        "ram":  (metrics["ram_percent"],  80, "System RAM critical"),
        "disk": (metrics["disk_percent"], 90, "System Disk critical"),
    }
    for key, (val, threshold, msg) in checks.items():
        if val >= threshold:
            sys_streak[key] += 1
            if sys_streak[key] >= 3 and not sys_alerted[key]:
                alert(msg, f"{msg} at {val}%.\n\nCheck running processes immediately.", f"{msg} ({val}%) — email sent")
                sys_alerted[key] = True
        else:
            sys_streak[key] = 0
            sys_alerted[key] = False

def check_container_alerts(containers):
    global previously_running
    currently_running = set()

    for c in containers:
        name = c["name"]
        if c["status"] == "running":
            currently_running.add(name)
            already_alerted_crash.discard(name)
            manually_stopped.discard(name)

            mem = c.get("mem_percent")
            if mem is not None:
                if mem >= 90 and not container_mem_warned.get(name + "_critical"):
                    alert(f"Container memory critical — {name}", f"Container '{name}' memory at {mem}%.\n\nRisk: Crash imminent.", f"{name} memory CRITICAL ({mem}%)")
                    container_mem_warned[name + "_critical"] = True
                    container_mem_warned[name + "_warning"] = True
                elif mem >= 80 and not container_mem_warned.get(name + "_warning"):
                    alert(f"Container memory warning — {name}", f"Container '{name}' memory at {mem}%.\n\nRisk: May crash soon.", f"{name} memory WARNING ({mem}%)")
                    container_mem_warned[name + "_warning"] = True
                elif mem < 80:
                    container_mem_warned[name + "_warning"] = False
                    container_mem_warned[name + "_critical"] = False

            cpu = c.get("cpu_percent")
            if cpu is not None:
                if cpu >= 85 and not container_cpu_warned.get(name):
                    alert(f"Container CPU spike — {name}", f"Container '{name}' CPU at {cpu}%.\n\nRisk: App may freeze.", f"{name} CPU spike ({cpu}%)")
                    container_cpu_warned[name] = True
                elif cpu < 85:
                    container_cpu_warned[name] = False

        elif c["status"] in ("exited", "restarting"):
            was_running = name in previously_running
            if was_running and name not in already_alerted_crash and name not in manually_stopped:
                alert(f"Container crashed — {name}", f"Container '{name}' crashed.\n\nService is DOWN. Restart immediately.", f"{name} CRASHED — service down")
                already_alerted_crash.add(name)

    previously_running = currently_running

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/alerts')
def alerts_page():
    return render_template('alerts.html')

@app.route('/api/metrics')
def metrics():
    return jsonify(get_metrics())

@app.route('/api/containers')
def containers():
    all_c = check_containers()
    running = [c for c in all_c if c["status"] == "running"]
    exited = [c for c in all_c if c["status"] != "running"]
    return jsonify((running + exited)[:5])

@app.route('/api/containers/available')
def available_containers():
    all_containers = client.containers.list(all=True)
    return jsonify([{"name": c.name, "status": c.status} for c in all_containers])

@app.route('/api/containers/attach', methods=['POST'])
def attach_container():
    name = request.json.get('name')
    try:
        container = client.containers.get(name)
        if container.status != "running":
            container.start()
        monitored_containers.add(name)
        manually_stopped.discard(name)
        log_event(f"Container started — {name}")
        return jsonify({"success": True, "message": f"{name} started"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/containers/stop', methods=['POST'])
def stop_container():
    name = request.json.get('name')
    try:
        container = client.containers.get(name)
        container.stop()
        manually_stopped.add(name)
        log_event(f"Container stopped — {name}")
        return jsonify({"success": True, "message": f"{name} stopped"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/containers/run', methods=['POST'])
def run_container():
    image = request.json.get('image')
    name = request.json.get('name')
    try:
        try:
            container = client.containers.get(name)
            if container.status != "running":
                container.start()
            monitored_containers.add(name)
            manually_stopped.discard(name)
            log_event(f"Container started — {name}")
            return jsonify({"success": True, "message": f"{name} started"})
        except docker.errors.NotFound:
            client.containers.run(image, name=name, detach=True)
            monitored_containers.add(name)
            log_event(f"New container launched — {name} ({image})")
            return jsonify({"success": True, "message": f"{name} launched"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/containers/volume-check', methods=['POST'])
def check_volume_info():
    name = request.json.get('name')
    try:
        container = client.containers.get(name)
        mounts = container.attrs.get('Mounts', [])
        volumes = [m.get('Destination', '') for m in mounts if m.get('Type') in ('volume', 'bind')]
        return jsonify({"has_volume": len(volumes) > 0, "volumes": volumes})
    except Exception as e:
        return jsonify({"has_volume": False, "error": str(e)})

@app.route('/api/containers/remove', methods=['POST'])
def remove_container():
    name = request.json.get('name')
    try:
        container = client.containers.get(name)
        container.remove(force=True)
        manually_stopped.discard(name)
        already_alerted_crash.discard(name)
        monitored_containers.discard(name)
        log_event(f"Container removed — {name}")
        return jsonify({"success": True, "message": f"{name} removed"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# History Metrics API - Critical CPU spikes history
@app.route('/api/history/metrics')
def metric_history():
    records = MetricHistory.query.order_by(MetricHistory.timestamp.desc()).limit(20).all()
    return jsonify([{
        "time": r.timestamp.strftime("%H:%M:%S"),
        "cpu": r.cpu,
        "ram": r.ram,
        "disk": r.disk
    } for r in reversed(records)])

@app.route('/api/history/alerts')
def alert_history():
    records = AlertHistory.query.order_by(AlertHistory.timestamp.desc()).limit(50).all()
    return jsonify([{
        "id": r.id,
        "time": r.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "subject": r.subject,
        "message": r.message
    } for r in records])

@app.route('/api/events')
def events():
    return jsonify(recent_events)

def background_emit():
    while True:
        metrics = get_metrics()
        all_c = check_containers()

        check_system_alerts(metrics)
        check_container_alerts(all_c)

        # Sirf jab CPU critical threshold (85%+) cross kare tab hi database me save hoga
        if metrics["cpu_percent"] >= 85:
            with app.app_context():
                db.session.add(MetricHistory(
                    cpu=metrics["cpu_percent"],
                    ram=metrics["ram_percent"],
                    disk=metrics["disk_percent"]
                ))
                db.session.commit()

        running = [c for c in all_c if c["status"] == "running"]
        exited = [c for c in all_c if c["status"] != "running"]
        combined = (running + exited)[:5]

        traffic = []
        for c in running:
            try:
                count = count_recent_requests(container_name=c["name"], minutes=5)
            except Exception:
                count = 0
            traffic.append({"name": c["name"], "requests": count})

        history = []
        with app.app_context():
            records = MetricHistory.query.order_by(MetricHistory.timestamp.desc()).limit(20).all()
            history = [{"time": r.timestamp.strftime("%H:%M:%S"), "cpu": r.cpu, "ram": r.ram, "disk": r.disk} for r in reversed(records)]

        socketio.emit('update', {
            'metrics': metrics,
            'containers': combined,
            'events': recent_events,
            'traffic': traffic,
            'history': history
        })
        time.sleep(10)

thread = threading.Thread(target=background_emit)
thread.daemon = True
thread.start()

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
