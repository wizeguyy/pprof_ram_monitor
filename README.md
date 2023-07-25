# RAM Monitor with pprof capture
This script monitors RAM usage and captures a pprof sample from a specified
pprof server.

## Getting started
Clone this repository
```
git clone https://github.com/dominant-strategies/pprof_ram_monitor.git
```

Run some software which hosts a pprof server.

## Usage
Run `./monitor_ram.py --help` for usage instructions.
```
./monitor_ram.py --help
usage: monitor_ram.py [-h] [--ewma_alpha EWMA_ALPHA] [--interval INTERVAL] pprof_host

RAM monitor with pprof capture

positional arguments:
  pprof_host            IP address & port for the pprof host

options:
  -h, --help            show this help message and exit
  --ewma_alpha EWMA_ALPHA
                        Alpha factor for the EWMA filter (value between 0 and 1)
  --interval INTERVAL   Delay between RAM monitor checks
```
