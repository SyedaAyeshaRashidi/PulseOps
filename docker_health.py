import docker

client = docker.from_env()

def calculate_cpu_percent(stats):
    try:
        cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        system_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
        num_cpus = stats["cpu_stats"].get("online_cpus", 1)

        if system_delta > 0 and cpu_delta > 0:
            return round((cpu_delta / system_delta) * num_cpus * 100, 1)
        return 0.0
    except (KeyError, ZeroDivisionError):
        return None

def check_containers():
    containers = client.containers.list(all=True)
    results = []
    for c in containers:
        mem_percent = None
        cpu_percent = None

        if c.status == "running":
            try:
                stats = c.stats(stream=False)
                mem_usage = stats["memory_stats"].get("usage", 0)
                mem_limit = stats["memory_stats"].get("limit", 0)
                if mem_limit:
                    mem_percent = round((mem_usage / mem_limit) * 100, 1)

                cpu_percent = calculate_cpu_percent(stats)
            except Exception:
                pass

        results.append({
            "name": c.name,
            "status": c.status,
            "image": c.image.tags,
            "mem_percent": mem_percent,
            "cpu_percent": cpu_percent,
            "created": c.attrs["Created"],
        })
    return results

if __name__ == "__main__":
    for c in check_containers():
        print(c)
