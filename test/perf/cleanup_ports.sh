#!/usr/bin/env bash
# Helper script to clean up ports used by mite performance tests

echo "Cleaning up mite performance test ports..."

# Kill processes using port 9898 (HTTP server)
if lsof -ti:9898 >/dev/null 2>&1; then
    echo "Killing processes on port 9898..."
    kill -9 $(lsof -ti:9898) 2>/dev/null || true
fi

# Kill processes using port 14303 (duplicator)
if lsof -ti:14303 >/dev/null 2>&1; then
    echo "Killing processes on port 14303..."
    kill -9 $(lsof -ti:14303) 2>/dev/null || true
fi

# Kill processes using port 14302 (message socket)
if lsof -ti:14302 >/dev/null 2>&1; then
    echo "Killing processes on port 14302..."
    kill -9 $(lsof -ti:14302) 2>/dev/null || true
fi

# Kill any remaining mite processes
echo "Killing any remaining mite processes..."
pkill -9 -f "mite (runner|duplicator|collector|controller)" 2>/dev/null || true

# Kill any remaining http_server.py processes
pkill -9 -f "http_server.py" 2>/dev/null || true

echo "Cleanup complete!"
