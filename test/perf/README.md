# Mite Performance Tests Guide

Complete guide for running and managing mite performance tests.

## Quick Start

Run all performance tests:
```bash
hatch run perf-test:perf-test
```

The tests automatically clean up when finished or interrupted with Ctrl+C.

## What the Tests Do

The performance tests measure how mite handles different workloads by:
- Starting a test HTTP server on port 9898
- Running mite components (runner, duplicator, collector, controller)
- Sending requests at different rates (1, 10, 100, 1000 concurrent scenarios)
- Collecting CPU and memory usage data
- Generating charts and CSV reports

Tests run for several minutes and output results to the `output/` directory.

## Output Files

After running, you'll find results in `output/YYYY-MM-DD/HH-MM/`:
- `samples.csv` - Raw performance data
- `chart.html` - Interactive charts showing CPU, memory, and throughput

## Common Issues

### "Address already in use" error

This means a previous test didn't shut down properly. Run:
```bash
hatch run perf-test:cleanup
```

### Test hangs or won't stop

Press Ctrl+C once - the test will clean up automatically. If that doesn't work:
```bash
hatch run perf-test:cleanup
```

## Manual Port Management

### Check if a port is in use
```bash
lsof -i:9898    # HTTP server
lsof -i:14303   # Mite duplicator
```

### Kill a specific port manually
```bash
kill -9 $(lsof -ti:9898)
```

## Test Scenarios

The test runs four scenarios automatically:
- **scenario1**: 1 concurrent journey
- **scenario10**: 10 concurrent journeys
- **scenario100**: 100 concurrent journeys
- **scenario1000**: 1000 concurrent journeys

Each scenario measures CPU usage, memory consumption, and request throughput.

## Requirements

All dependencies are managed by Hatch. The test environment includes:
- aiohttp
- sanic
- psutil
- pandas
- altair

## Troubleshooting Commands

If cleanup command fails, manually kill processes:
```bash
# Kill HTTP server
pkill -9 -f "http_server.py"

# Kill all mite processes
pkill -9 -f "mite (runner|duplicator|collector|controller)"

# Check if ports are free
lsof -i:9898
lsof -i:14303
```

## Technical Details

### Automatic Cleanup

The test script uses multiple cleanup mechanisms:
- **atexit handlers**: Clean up on normal exit
- **Signal handlers**: Clean up on Ctrl+C (SIGINT) or termination (SIGTERM)
- **Per-test cleanup**: Each scenario cleans up before moving to the next

### Cleanup Process

When stopping, the script:
1. Tries graceful shutdown (waits 1 second)
2. Force kills any remaining processes
3. Releases all ports (9898, 14303, 14302)

This two-stage approach ensures ports are freed even if processes hang.
