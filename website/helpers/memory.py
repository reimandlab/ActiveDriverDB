import os
import psutil

# remember to `set global max_allowed_packet=1073741824;` (it's max - 1GB)
# (otherwise MySQL server will be gone)
MEMORY_LIMIT = 2e9  # it can be greater than sql ma packet, since we will be
# counting a lot of overhead into the current memory usage. Adjust manually.

MEMORY_PERCENT_LIMIT = 80


def system_memory_percent():
    return psutil.virtual_memory().percent


def memory_usage():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss


