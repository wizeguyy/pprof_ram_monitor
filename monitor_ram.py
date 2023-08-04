#!/bin/python3

import os
import psutil
import requests
import time
import argparse
import multiprocessing
from datetime import datetime

DEFAULT_EWMA_ALPHA = 0.1        # Default alpha value for EWMA filter
# Time interval in seconds between each RAM usage check
DEFAULT_INTERVAL_SEC = 1
# Relative increase in RAM usage to trigger a pprof capture (in megabytes)
DEFAULT_TRIGGER_LEVEL_MB = 1024


def get_cli_args():
    parser = argparse.ArgumentParser(
        description='RAM monitor with pprof capture')
    parser.add_argument('pprof_host', type=str,
                        help='IP address & port for the pprof host')
    parser.add_argument('--ewma_alpha', type=float, default=DEFAULT_EWMA_ALPHA,
                        help='Alpha factor for the EWMA filter (value between 0 and 1)')
    parser.add_argument('--interval', type=int, default=DEFAULT_INTERVAL_SEC,
                        help='Delay between RAM monitor checks')
    parser.add_argument('--trigger', type=int, default=DEFAULT_TRIGGER_LEVEL_MB,
                        help='Relative change in RAM usage to trigger a pprof capture (in megabytes)')
    return parser.parse_args()


# Capture pprof profiles from the given server
def capture_pprof(url, outdir):
    pprof_requests = [
        '/debug/pprof/heap',
        '/debug/pprof/goroutine',
        '/debug/pprof/threadcreate',
        '/debug/pprof/block',
        '/debug/pprof/mutex',
        '/debug/pprof/profile?seconds=5',
        '/debug/pprof/trace?seconds=5',
    ]
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


# Capture the list of running processes
def capture_processes(outdir):
    os.makedirs(outdir, exist_ok=True)
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'username']):
        processes.append({
            'name': proc.name(),
            'rss': proc.memory_info().rss,
            'vms': proc.memory_info().vms,
            'shared': proc.memory_info().shared,
            'text': proc.memory_info().text,
            'lib': proc.memory_info().lib,
            'data': proc.memory_info().data,
            'dirty': proc.memory_info().dirty,
        })
    sorted_processes = sorted(
        processes, key=lambda x: x['rss'], reverse=True)
    outfile = os.path.join(outdir, "processes_top100.txt")
    with open(outfile, "wb") as file:
        for proc in sorted_processes[:100]:
            file.write(
                "rss= {: >10},\tvms= {: >10},\tshared= {: >10},\ttext= {: >10},\tlib= {: >10},\tdata= {: >10},\tdirty= {: >10},\tname= {: >10}\n"
                .format(
                    format_bytes(proc['rss']),
                    format_bytes(proc['vms']),
                    format_bytes(proc['shared']),
                    format_bytes(proc['text']),
                    format_bytes(proc['lib']),
                    format_bytes(proc['data']),
                    format_bytes(proc['dirty']),
                    proc['name'],)
                .encode('utf-8'))


# Log the text and optionally print to console
def log(str):
    print(str)


# The primary task of this process
def process():
    # Parse CLI args
    args = get_cli_args()

    # Capture baseline pprof
    curr = psutil.virtual_memory().used
    starttime = datetime.now().strftime("%Y%m%d_%H%M%S")
    # capture_pprof(args.pprof_host,
    #              f"pprof_traces/{starttime}/initial_{int(curr/1024/1024)}MB")
    capture_processes(
        f"pprof_traces/{starttime}/initial_{int(curr/1024/1024)}MB")

    # Initialize EWMA filter for ram usage
    avg_ram_usage = Ewma(args.ewma_alpha, psutil.virtual_memory().used)

    # Periodically monitor the RAM and capture pprof data as needed
    while True:
        # Get current RAM usage
        curr = psutil.virtual_memory().used

        # Update the EWMA
        avg_ram_usage.update(curr)

        # Print current RAM stats
        logtime = datetime.now().strftime("%H:%M:%S")
        print(
            f"({logtime}) RAM usage: current={format_bytes(curr)}, avg={format_bytes(avg_ram_usage.val)}")

        # Check for sudden spike in RAM usage
        trigger = 1024*1024*args.trigger
        delta = curr-avg_ram_usage.val
        if abs(delta) > trigger:
            avg_ram_usage.reset(curr)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # capture_pprof(args.pprof_host,
            #              f"pprof_traces/{starttime}/{timestamp}_{int(curr/1024/1024)}MB")
            capture_processes(
                f"pprof_traces/{starttime}/{timestamp}_{int(curr/1024/1024)}MB")

        # Sleep
        time.sleep(args.interval)


# Main function just kicks off the background process
def main():
    background_process = multiprocessing.Process(target=process)
    background_process.start()
    background_process.join()


def format_bytes(bytes_num):
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
    unit_index = 0

    while bytes_num >= 1000 and unit_index < len(units) - 1:
        bytes_num /= 1000.0
        unit_index += 1

    return f"{bytes_num:.2f} {units[unit_index]}"


class Ewma:
    # Initialize a new EWMA instance
    def __init__(self, alpha, initial_value):
        self.alpha = alpha
        self.val = initial_value

    # Update the EWMA filter with a new data sample
    def update(self, new_sample):
        self.val = (1-self.alpha)*self.val + self.alpha*new_sample

    # Reset the average to a given value
    def reset(self, val):
        self.val = val


if __name__ == '__main__':
    main()
