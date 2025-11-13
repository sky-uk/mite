"""
Example: HTTP load testing with memory tuning

This example demonstrates how to configure the HTTP connection pool
for different memory constraints.
"""

import asyncio
from mite_http import mite_http


# Example 1: Default configuration (100 connections)
# Good for most scenarios with adequate memory (1GB+)
@mite_http
async def journey_default(ctx):
    """Default HTTP journey - uses 100 max connections"""
    async with ctx.transaction('http_request'):
        response = await ctx.http.get("https://httpbin.org/get")
        assert response.status_code == 200


# Example 2: Memory-constrained configuration
# Suitable for 512MB containers or environments with limited memory
@mite_http(max_connects=50)
async def journey_low_memory(ctx):
    """Memory-efficient HTTP journey - uses 50 max connections"""
    async with ctx.transaction('http_request'):
        response = await ctx.http.get("https://httpbin.org/get")
        assert response.status_code == 200


# Example 3: High-throughput configuration
# For scenarios with many unique hosts or very high concurrency
@mite_http(max_connects=200)
async def journey_high_throughput(ctx):
    """High-throughput HTTP journey - uses 200 max connections"""
    async with ctx.transaction('http_request'):
        response = await ctx.http.get("https://httpbin.org/get")
        assert response.status_code == 200


# Example 4: Very memory-constrained
# For extreme memory limits (256-512MB containers)
@mite_http(max_connects=25)
async def journey_minimal_memory(ctx):
    """Minimal memory HTTP journey - uses 25 max connections"""
    async with ctx.transaction('http_request'):
        response = await ctx.http.get("https://httpbin.org/get")
        assert response.status_code == 200


def scenario():
    """
    Choose one of the journey configurations based on your environment:
    
    - journey_default: Most scenarios (1GB+ memory)
    - journey_low_memory: Containerized with 512MB-1GB
    - journey_minimal_memory: Very constrained (256-512MB)
    - journey_high_throughput: Many hosts, high concurrency
    """
    return [
        # Default - comment out others
        ['mite_http_example:journey_default', None, lambda start, end: 10],
        
        # Memory-constrained - uncomment if needed
        # ['mite_http_example:journey_low_memory', None, lambda start, end: 10],
        
        # Minimal memory - uncomment if needed
        # ['mite_http_example:journey_minimal_memory', None, lambda start, end: 10],
        
        # High-throughput - uncomment if needed
        # ['mite_http_example:journey_high_throughput', None, lambda start, end: 10],
    ]
