import docker
import datetime
import re

client = docker.from_env()

LOG_PATTERN = re.compile(
    r'\[(?P<time>\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2})\s+[+-]\d{4}\].*?"(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+.*?\s+HTTP/\d\.\d"\s+\d{3}'
)
def count_recent_requests(container_name=None, window_minutes=5, minutes=None):
    if minutes is not None:
        window_minutes = minutes
    try:
        container = client.containers.get(container_name)
        logs = container.logs(tail=200).decode("utf-8", errors="ignore")
        
        now = datetime.datetime.now()
        threshold_time = now - datetime.timedelta(minutes=window_minutes)
        
        valid_requests = 0
        for line in logs.splitlines():
            match = LOG_PATTERN.search(line)
            if match:
                log_time_str = match.group("time")
                log_time = datetime.datetime.strptime(log_time_str, "%d/%b/%Y:%H:%M:%S")
                # Sirf pichle 5 minutes ki valid requests count hongi
                if log_time >= threshold_time:
                    valid_requests += 1
                    
        return valid_requests
    except Exception:
        return 0

get_traffic_count = count_recent_requests

if __name__ == "__main__":
    print(f"Current traffic: {count_recent_requests()} requests")
