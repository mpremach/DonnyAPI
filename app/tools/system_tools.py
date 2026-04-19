import datetime
import psutil

# GET CURRENT TIME
def get_current_time():
    """Returns the current date and exact time."""
    return datetime.datetime.now().strftime("%A, %B %d, %Y at %I:%M:%S %p")

# GET SYSTEM USAGE
def get_system_health():
    """
    Retrieves the real-time status of the computer's hardware.
    Use this tool when the user asks about PC performance, CPU usage, RAM, or disk space.
    """
    try:
        cpu_usage = psutil.cpu_percent(interval=3)
        # RAM Usage
        memory = psutil.virtual_memory()
        ram_usage = memory.percent
        ram_total_gb = round(memory.total / (1024 ** 3), 1)
        ram_used_gb = round(memory.used / (1024 ** 3), 1)

        # Disk Usage
        disk = psutil.disk_usage('C://')
        disk_usage = disk.percent
        disk_free_gb = round(disk.free / (1024 ** 3), 1)

        return {
            "cpu_usage": f"{cpu_usage}%",
            "ram_usage": f"{ram_usage}% ({ram_used_gb}GB / {ram_total_gb}GB)",
            "c_drive_space_remaining": f"{disk_free_gb} GB free",
            "overall_status": "Healthy" if cpu_usage < 80 and ram_usage < 85 else "Under Heavy Load"
        }
    except Exception as e:
        return f"Sir, I am unable to read the system sensors: {str(e)}"

