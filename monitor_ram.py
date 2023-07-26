#!/bin/python3

import os
import psutil
import requests
import time
import argparse
from datetime import datetime

# Global variables
DEFAULT_EWMA_ALPHA = 0.1   # Default alpha value for EWMA filter
DEFAULT_INTERVAL_SEC = 1    # Time interval in seconds between each RAM usage check
RAM_USAGE_SENSITIVITY = 0.8  # Relative change in RAM usage to trigger pprof capture


def get_cli_args():
    parser = argparse.ArgumentParser(
        description='RAM monitor with pprof capture')
    parser.add_argument('pprof_host', type=str,
                        help='IP address & port for the pprof host')
    parser.add_argument('--ewma_alpha', type=float, default=DEFAULT_EWMA_ALPHA,
                        help='Alpha factor for the EWMA filter (value between 0 and 1)')
    parser.add_argument('--interval', type=int, default=DEFAULT_INTERVAL_SEC,
                        help='Delay between RAM monitor checks')
    return parser.parse_args()


def capture_pprof(url, capture_name):
    pprof_requests = [
        '/debug/pprof/heap',
        '/debug/pprof/goroutine',
        '/debug/pprof/threadcreate',
        '/debug/pprof/block',
        '/debug/pprof/mutex',
        '/debug/pprof/profile?seconds=5',
        '/debug/pprof/trace?seconds=5',
    ]
    outdir = os.path.join("pprof_traces", capture_name)
    for request in pprof_requests:
        # Query the server for pprof data
        trace_name = os.path.basename(request)
        outfile = os.path.join(outdir, f"{trace_name}.pb.gz")
        os.makedirs(outdir, exist_ok=True)
        endpoint = url+request
        logtime = datetime.now().strftime("%H:%M:%S")
        print(f"({logtime}) Capturing {request}...")
        try:
            response = requests.get(endpoint)
        except requests.exceptions.RequestException as e:
            logtime = datetime.now().strftime("%H:%M:%S")
            print(f"({logtime}) Error sending curl request: {e}")

        # Write to file
        with open(outfile, "wb") as file:
            file.write(response.content)


def main():
    # Parse CLI args
    args = get_cli_args()

    # Capture baseline pprof
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    capture_pprof(args.pprof_host, "initial@"+timestamp)

    # Initialize EWMA filter for ram usage
    avg_ram_usage = Ewma(args.ewma_alpha, psutil.virtual_memory().used)

    # Periodically monitor the RAM and capture pprof data as needed
    while True:
        # Get current RAM usage
        curr = psutil.virtual_memory().used
        pprof_threshold = avg_ram_usage.val * (1 + RAM_USAGE_SENSITIVITY)

        # Update the EWMA
        avg_ram_usage.update(curr)

        # Print current RAM stats
        logtime = datetime.now().strftime("%H:%M:%S")
        print(
            f"({logtime}) RAM usage: current={format_bytes(curr)}, avg={format_bytes(avg_ram_usage.val)}")

        # Check for sudden spike in RAM usage
        if curr > pprof_threshold:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            capture_pprof(args.pprof_host, timestamp)

        # Sleep
        time.sleep(args.interval)

# Format number of bytes into a human readable value


def format_bytes(bytes_num):
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
    unit_index = 0

    while bytes_num >= 1000 and unit_index < len(units) - 1:
        bytes_num /= 1000.0
        unit_index += 1

    return f"{bytes_num:.2f} {units[unit_index]}"

# EWMA class defines an exponentially-weighted moving average filter


class Ewma:
    # Initialize a new EWMA instance
    def __init__(self, alpha, initial_value):
        self.alpha = alpha
        self.val = initial_value

    # Update the EWMA filter with a new data sample
    def update(self, new_sample):
        self.val = (1-self.alpha)*self.val + self.alpha*new_sample


if __name__ == '__main__':
    main()
