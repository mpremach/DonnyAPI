import datetime

def get_current_time():
    """Returns the current date and exact time."""
    return datetime.datetime.now().strftime("%A, %B %d, %Y at %I:%M:%S %p")

