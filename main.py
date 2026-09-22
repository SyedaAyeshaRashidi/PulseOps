import time
import os
from datetime import datetime, timezone
from dateutil import parser as dateparser
from collector import get_metrics
from docker_health import check_containers
from traffic_monitor import count_recent_requests
from alerts import send_alert

WARNING_THRESHOLD = 75
CRITICAL_THRESHOLD = 90
SUSTAINED_CHECKS = 3
CHECK_INTERVAL = 10
TRAFFIC_THRESHOLD = 100
CONTAINER_MEM_WARNING = 80
CONTAINER_CPU_WARNING = 80

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

SCRIPT_START = datetime.now(timezone.utc)

previously_running = set()
tracked_containers = set()
already_alerted_crash = set()
high_usage_streak = {"cpu": 0, "ram": 0, "disk": 0}
alerted_critical = {"cpu": False, "ram": False, "disk": False}
container_mem_warned = {}
container_cpu_warned = {}
recent_events = []

RECOMMENDATIONS = {
    "cpu": "Check for runaway processes with 'top' or 'htop'.",
    "ram": "Check for memory leaks with 'free -h'.",
    "disk": "Run 'df -h' and clear old Docker images with 'docker system prune'.",
}

def log_event(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    recent_events.insert(0, f"[{timestamp}] {message}")
    if len(recent_events) > 5:
        recent_events.pop()

def alert_and_log(message, log_message):
    success = send_alert(message)
    if success:
        log_event(f"EMAIL SENT - {log_message}")
    else:
        log_event(f"EMAIL FAILED - {log_message}")

def evaluate_resource(name, value):
    if value >= CRITICAL_THRESHOLD:
        high_usage_streak[name] += 1
        if high_usage_streak[name] >= SUSTAINED_CHECKS and not alerted_critical[name]:
            alert_and_log(
                f"CRITICAL: {name.upper()} at {value}%.\n\nRecommendation: {RECOMMENDATIONS[name]}",
                f"{name.upper()} critical ({value}%)"
            )
            alerted_critical[name] = True
    else:
        high_usage_streak[name] = 0
        alerted_critical[name] = False

def check_system(metrics):
    evaluate_resource("cpu", metrics["cpu_percent"])
    evaluate_resource("ram", metrics["ram_percent"])
    evaluate_resource("disk", metrics["disk_percent"])

def check_docker():
    global previously_running
    currently_running = set()
    container_display = []

    for c in check_containers():
        name = c["name"]
        created_time = dateparser.parse(c["created"])
        is_new_container = created_time > SCRIPT_START

        if is_new_container:
            tracked_containers.add(name)

        is_relevant = (c["status"] == "running") or (name in tracked_containers) or (name in previously_running)

        if is_relevant:
            mem_display = f"{c['mem_percent']}%" if c["mem_percent"] is not None else "N/A"
            cpu_display = f"{c['cpu_percent']}%" if c["cpu_percent"] is not None else "N/A"
            container_display.append((name, c["status"], mem_display, cpu_display))

        if c["status"] == "running":
            currently_running.add(name)
            already_alerted_crash.discard(name)

            if c["mem_percent"] is not None and c["mem_percent"] >= CONTAINER_MEM_WARNING:
                if not container_mem_warned.get(name):
                    alert_and_log(
                        f"WARNING (predictive): '{name}' is using {c['mem_percent']}% of its memory limit.",
                        f"{name} memory warning ({c['mem_percent']}%)"
                    )
                    container_mem_warned[name] = True
            else:
                container_mem_warned[name] = False

            if c["cpu_percent"] is not None and c["cpu_percent"] >= CONTAINER_CPU_WARNING:
                if not container_cpu_warned.get(name):
                    alert_and_log(
                        f"WARNING: '{name}' CPU usage at {c['cpu_percent']}%.",
                        f"{name} CPU warning ({c['cpu_percent']}%)"
                    )
                    container_cpu_warned[name] = True
            else:
                container_cpu_warned[name] = False

        elif c["status"] in ("exited", "restarting"):
            should_alert = name in previously_running or name in tracked_containers
            if should_alert and name not in already_alerted_crash:
                alert_and_log(
                    f"CRASHED: Container '{name}' is now {c['status']}.",
                    f"{name} CRASHED"
                )
                already_alerted_crash.add(name)

    previously_running = currently_running
    return container_display

def check_traffic():
    traffic_display = []
    for name in previously_running:
        try:
            count = count_recent_requests(container_name=name, minutes=5)
            traffic_display.append((name, count))
            if count > TRAFFIC_THRESHOLD:
                alert_and_log(
                    f"Traffic spike on '{name}': {count} requests in last 5 min.",
                    f"{name} traffic spike ({count} req)"
                )
        except Exception:
            pass
    return traffic_display

def color_for_metric(value):
    if value >= CRITICAL_THRESHOLD:
        return RED
    elif value >= WARNING_THRESHOLD:
        return YELLOW
    return GREEN

def color_for_status(status):
    if status == "running":
        return GREEN
    elif status == "restarting":
        return YELLOW
    return RED

def render_dashboard(metrics, containers, traffic):
    os.system("clear")
    print(f"{CYAN}{BOLD}{'='*65}")
    print(f"{'SERVER MONITOR':^65}")
    print(f"{'='*65}{RESET}")
    print(f"{CYAN}  {datetime.now().strftime('%Y-%m-%d %H:%M:%S'):^61}{RESET}\n")

    print(f"{CYAN}{BOLD}OVERALL SYSTEM (whole VM){RESET}")
    print(f"  CPU:   {color_for_metric(metrics['cpu_percent'])}{metrics['cpu_percent']:>5.1f}%{RESET}")
    print(f"  RAM:   {color_for_metric(metrics['ram_percent'])}{metrics['ram_percent']:>5.1f}%{RESET}")
    print(f"  Disk:  {color_for_metric(metrics['disk_percent'])}{metrics['disk_percent']:>5.1f}%{RESET}\n")

    print(f"{CYAN}{BOLD}ACTIVE CONTAINERS{RESET}")
    if containers:
        print(f"  {'NAME':<20}{'STATUS':<12}{'CPU':<10}{'MEM':<10}")
        for name, status, mem, cpu in containers:
            color = color_for_status(status)
            print(f"  {color}{name:<20}{status:<12}{cpu:<10}{mem:<10}{RESET}")
    else:
        print("  No active containers")
    print()

    print(f"{CYAN}{BOLD}TRAFFIC (last 5 min){RESET}")
    if traffic:
        for name, count in traffic:
            color = RED if count > TRAFFIC_THRESHOLD else GREEN
            print(f"  {color}{name:<20} {count} requests{RESET}")
    else:
        print("  No running containers to check")
    print()

    print(f"{CYAN}{BOLD}RECENT EVENTS{RESET}")
    if recent_events:
        for event in recent_events:
            print(f"  {event}")
    else:
        print("  No alerts sent yet")

    print(f"\n{CYAN}{'='*65}{RESET}")
    print(f"Next check in {CHECK_INTERVAL}s | Press Ctrl+C to stop")

if __name__ == "__main__":
    while True:
        metrics = get_metrics()
        check_system(metrics)
        containers = check_docker()
        traffic = check_traffic()

        render_dashboard(metrics, containers, traffic)

        time.sleep(CHECK_INTERVAL)
