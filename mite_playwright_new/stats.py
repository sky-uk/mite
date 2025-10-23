"""
Playwright Stats Module

Performance statistics collection for Playwright automation.
Similar to mite_selenium stats but optimized for Playwright metrics.
"""

import time
from typing import Dict, Any, List, Optional
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PlaywrightStats:
    """
    Container for Playwright performance statistics.
    Similar to Selenium stats but with Playwright-specific metrics.
    """
    
    # Navigation metrics
    navigation_count: int = 0
    total_navigation_time: float = 0.0
    avg_navigation_time: float = 0.0
    min_navigation_time: float = float('inf')
    max_navigation_time: float = 0.0
    
    # Action metrics
    click_count: int = 0
    total_click_time: float = 0.0
    avg_click_time: float = 0.0
    
    fill_count: int = 0
    total_fill_time: float = 0.0
    avg_fill_time: float = 0.0
    
    wait_count: int = 0
    total_wait_time: float = 0.0
    avg_wait_time: float = 0.0
    
    # Network metrics
    network_requests: int = 0
    total_network_time: float = 0.0
    avg_network_time: float = 0.0
    
    # Error metrics
    error_count: int = 0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    
    # Browser metrics
    browser_startup_time: float = 0.0
    page_count: int = 0
    
    # Timing history
    navigation_history: List[Dict[str, Any]] = field(default_factory=list)
    action_history: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary format"""
        return {
            'navigation': {
                'count': self.navigation_count,
                'total_time': self.total_navigation_time,
                'avg_time': self.avg_navigation_time,
                'min_time': self.min_navigation_time if self.min_navigation_time != float('inf') else 0,
                'max_time': self.max_navigation_time
            },
            'actions': {
                'clicks': {
                    'count': self.click_count,
                    'total_time': self.total_click_time,
                    'avg_time': self.avg_click_time
                },
                'fills': {
                    'count': self.fill_count,
                    'total_time': self.total_fill_time,
                    'avg_time': self.avg_fill_time
                },
                'waits': {
                    'count': self.wait_count,
                    'total_time': self.total_wait_time,
                    'avg_time': self.avg_wait_time
                }
            },
            'network': {
                'requests': self.network_requests,
                'total_time': self.total_network_time,
                'avg_time': self.avg_network_time
            },
            'errors': {
                'count': self.error_count,
                'details': self.errors[-10:]  # Last 10 errors
            },
            'browser': {
                'startup_time': self.browser_startup_time,
                'page_count': self.page_count
            }
        }


class PlaywrightStatsCollector:
    """
    Statistics collector for Playwright automation.
    Collects and aggregates performance metrics during test execution.
    """
    
    def __init__(self, max_history: int = 1000):
        """
        Initialize stats collector.
        
        Args:
            max_history: Maximum number of historical entries to keep
        """
        self.stats = PlaywrightStats()
        self.max_history = max_history
        self.start_time = time.time()
        self.session_id = datetime.now().isoformat()
        
        # Rolling averages
        self._navigation_times = deque(maxlen=max_history)
        self._action_times = defaultdict(lambda: deque(maxlen=max_history))
        self._network_times = deque(maxlen=max_history)
        
    def add_navigation_stat(self, metrics: Dict[str, Any]):
        """
        Add navigation timing statistics.
        
        Args:
            metrics: Dictionary containing navigation metrics
        """
        load_time = metrics.get('load_time', 0)
        
        # Update navigation stats
        self.stats.navigation_count += 1
        self.stats.total_navigation_time += load_time
        self.stats.avg_navigation_time = self.stats.total_navigation_time / self.stats.navigation_count
        self.stats.min_navigation_time = min(self.stats.min_navigation_time, load_time)
        self.stats.max_navigation_time = max(self.stats.max_navigation_time, load_time)
        
        # Add to history
        entry = {
            'timestamp': time.time(),
            'url': metrics.get('url', ''),
            'load_time': load_time,
            'status_code': metrics.get('status_code'),
            'title': metrics.get('title', ''),
            'final_url': metrics.get('final_url', '')
        }
        self.stats.navigation_history.append(entry)
        self._navigation_times.append(load_time)
        
        # Trim history if needed
        if len(self.stats.navigation_history) > self.max_history:
            self.stats.navigation_history = self.stats.navigation_history[-self.max_history:]
            
    def add_action_stat(self, action_type: str, timing: float, selector: str = None):
        """
        Add action timing statistics.
        
        Args:
            action_type: Type of action ('click', 'fill', 'wait', etc.)
            timing: Time taken in milliseconds
            selector: CSS selector used (optional)
        """
        # Update specific action stats
        if action_type == 'click':
            self.stats.click_count += 1
            self.stats.total_click_time += timing
            self.stats.avg_click_time = self.stats.total_click_time / self.stats.click_count
        elif action_type == 'fill':
            self.stats.fill_count += 1
            self.stats.total_fill_time += timing
            self.stats.avg_fill_time = self.stats.total_fill_time / self.stats.fill_count
        elif action_type == 'wait':
            self.stats.wait_count += 1
            self.stats.total_wait_time += timing
            self.stats.avg_wait_time = self.stats.total_wait_time / self.stats.wait_count
            
        # Add to history
        entry = {
            'timestamp': time.time(),
            'action': action_type,
            'timing': timing,
            'selector': selector
        }
        self.stats.action_history.append(entry)
        self._action_times[action_type].append(timing)
        
        # Trim history if needed
        if len(self.stats.action_history) > self.max_history:
            self.stats.action_history = self.stats.action_history[-self.max_history:]
            
    def add_network_stat(self, metrics: Dict[str, Any]):
        """
        Add network request statistics.
        
        Args:
            metrics: Dictionary containing network metrics
        """
        timing = metrics.get('timing', 0)
        
        self.stats.network_requests += 1
        self.stats.total_network_time += timing
        self.stats.avg_network_time = self.stats.total_network_time / self.stats.network_requests
        
        self._network_times.append(timing)
        
    def add_error(self, error_type: str, error_message: str, context: Dict[str, Any] = None):
        """
        Add error information.
        
        Args:
            error_type: Type of error
            error_message: Error message
            context: Additional context information
        """
        self.stats.error_count += 1
        
        error_entry = {
            'timestamp': time.time(),
            'type': error_type,
            'message': error_message,
            'context': context or {}
        }
        
        self.stats.errors.append(error_entry)
        
        # Keep only recent errors
        if len(self.stats.errors) > 100:
            self.stats.errors = self.stats.errors[-100:]
            
    def add_stat(self, stat_name: str, value: float):
        """
        Add a general statistic.
        
        Args:
            stat_name: Name of the statistic
            value: Value to record
        """
        if stat_name == 'browser_startup_time':
            self.stats.browser_startup_time = value
        elif stat_name == 'page_count':
            self.stats.page_count = value
            
    def get_all_stats(self) -> Dict[str, Any]:
        """Get all collected statistics"""
        stats_dict = self.stats.to_dict()
        
        # Add session information
        stats_dict['session'] = {
            'id': self.session_id,
            'start_time': self.start_time,
            'duration': time.time() - self.start_time,
            'total_actions': (self.stats.click_count + 
                            self.stats.fill_count + 
                            self.stats.wait_count)
        }
        
        # Add rolling averages
        if self._navigation_times:
            stats_dict['rolling_averages'] = {
                'navigation': sum(self._navigation_times) / len(self._navigation_times)
            }
            
        return stats_dict
        
    def get_summary(self) -> str:
        """Get a formatted summary of statistics"""
        duration = time.time() - self.start_time
        
        summary = f"""
Playwright Performance Summary
=============================
Session Duration: {duration:.2f}s
Browser Startup: {self.stats.browser_startup_time:.2f}ms

Navigation:
  Count: {self.stats.navigation_count}
  Avg Time: {self.stats.avg_navigation_time:.2f}ms
  Min/Max: {self.stats.min_navigation_time:.2f}/{self.stats.max_navigation_time:.2f}ms

Actions:
  Clicks: {self.stats.click_count} (avg: {self.stats.avg_click_time:.2f}ms)
  Fills: {self.stats.fill_count} (avg: {self.stats.avg_fill_time:.2f}ms)
  Waits: {self.stats.wait_count} (avg: {self.stats.avg_wait_time:.2f}ms)

Network:
  Requests: {self.stats.network_requests}
  Avg Time: {self.stats.avg_network_time:.2f}ms

Errors: {self.stats.error_count}
"""
        return summary.strip()
        
    def reset(self):
        """Reset all statistics"""
        self.stats = PlaywrightStats()
        self.start_time = time.time()
        self.session_id = datetime.now().isoformat()
        self._navigation_times.clear()
        self._action_times.clear()
        self._network_times.clear()
        
    def export_to_csv(self, filename: str):
        """Export navigation history to CSV file"""
        import csv
        
        with open(filename, 'w', newline='') as csvfile:
            if self.stats.navigation_history:
                fieldnames = self.stats.navigation_history[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.stats.navigation_history)
                
    def get_percentiles(self, percentiles: List[float] = [50, 90, 95, 99]) -> Dict[str, Dict[str, float]]:
        """
        Calculate percentiles for timing metrics.
        
        Args:
            percentiles: List of percentiles to calculate
            
        Returns:
            Dictionary with percentile data
        """
        import statistics
        
        result = {}
        
        if self._navigation_times:
            sorted_nav = sorted(self._navigation_times)
            result['navigation'] = {}
            for p in percentiles:
                result['navigation'][f'p{p}'] = statistics.quantiles(sorted_nav, n=100)[p-1]
                
        for action_type, times in self._action_times.items():
            if times:
                sorted_times = sorted(times)
                result[action_type] = {}
                for p in percentiles:
                    result[action_type][f'p{p}'] = statistics.quantiles(sorted_times, n=100)[p-1]
                    
        return result