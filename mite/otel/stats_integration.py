"""
Automatic integration with mite's existing stats system
"""
from .tracing import get_meter
from .config import get_otel_config

class AutoStatsCollector:
    """
    Automatically collect existing mite stats and export as OTel metrics
    """
    def __init__(self):
        self.meter = get_meter()
        self.metrics = {}
        self._init_metrics()
    
    def _init_metrics(self):
        if not self.meter:
            return
            
        self.metrics['requests_total'] = self.meter.create_counter(
            "mite_requests_total",
            description="Total HTTP requests"
        )
        
        self.metrics['request_duration'] = self.meter.create_histogram(
            "mite_request_duration_seconds",
            description="HTTP request duration"
        )
        
        self.metrics['active_journeys'] = self.meter.create_up_down_counter(
            "mite_active_journeys",
            description="Currently active journeys"
        )

def record_http_request(method: str, status_code: int, duration: float, error: bool = False):
    """Record HTTP request metrics"""
    # This will be called by acurl integration to record metrics
    if hasattr(record_http_request, '_collector'):
        collector = record_http_request._collector
        if collector.metrics.get('requests_total'):
            collector.metrics['requests_total'].add(1, {
                "method": method,
                "status": str(status_code),
                "error": str(error)
            })
            
        if collector.metrics.get('request_duration'):
            collector.metrics['request_duration'].record(
                duration,
                {"method": method, "status": str(status_code)}
            )

def init_stats_mapping():
    """Initialize automatic stats collection if enabled"""
    config = get_otel_config()
    if config["enabled"]:
        collector = AutoStatsCollector()
        record_http_request._collector = collector
        
        # Try to hook into mite's existing stats system
        try:
            from mite.stats import Stats
            
            # Store original record method if it exists
            if hasattr(Stats, 'record'):
                original_record = Stats.record
                
                def traced_record(self, event_type, **data):
                    # Call original recording
                    result = original_record(self, event_type, **data)
                    
                    # Export to OTel metrics
                    _export_to_otel(event_type, data, collector)
                    
                    return result
                
                Stats.record = traced_record
                
        except (ImportError, AttributeError):
            # Stats system not available or different structure
            pass

def _export_to_otel(event_type: str, data: dict, collector):
    """Export mite stats events to OpenTelemetry metrics"""
    if event_type == "http_request" and collector.metrics.get('requests_total'):
        collector.metrics['requests_total'].add(1, {
            "method": data.get('method', 'unknown'),
            "status": str(data.get('status_code', 0))
        })
        
    if event_type == "http_request" and collector.metrics.get('request_duration'):
        collector.metrics['request_duration'].record(
            data.get('duration', 0),
            {"method": data.get('method', 'unknown')}
        )