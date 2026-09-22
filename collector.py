import psutil
import time
import json
from datetime import datetime

def get_metrics():
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "cpu_percent": psutil.cpu_percent(interval=1),
        "ram_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage('/').percent,
        "network": {
            "bytes_sent": psutil.net_io_counters().bytes_sent,
            "bytes_recv": psutil.net_io_counters().bytes_recv,
        }
    }

if __name__ == "__main__":
    while True:
        metrics = get_metrics()
        print(json.dumps(metrics, indent=2))
        time.sleep(10)
