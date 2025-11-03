"""
Automatic integration with mite's existing stats system
"""
from .tracing import get_meter
from .config import get_otel_config

# Module-level metrics registry
_metrics = {}
_collector_initialized = False


def _init_metrics():
    """Initialize OTel metrics lazily"""
    global _metrics, _collector_initialized
    if _collector_initialized:
        return
    
    meter = get_meter()
    if not meter:
        return
    
    _metrics['requests_total'] = meter.create_counter(
        "mite_requests_total", description="Total HTTP requests")
    _metrics['request_duration'] = meter.create_histogram(
        "mite_request_duration_seconds", description="HTTP request duration")
    _metrics['active_journeys'] = meter.create_up_down_counter(
        "mite_active_journeys", description="Currently active journeys")
    
    _collector_initialized = True


def record_http_request(method: str, status_code: int, duration: float, error: bool = False):
    """Record HTTP request metrics"""
    if not _collector_initialized:
        return
    
    if _metrics.get('requests_total'):
        _metrics['requests_total'].add(1, {
            "method": method,
            "status": str(status_code),
            "error": str(error)
        })
    
    if _metrics.get('request_duration'):
        _metrics['request_duration'].record(
            duration, {"method": method, "status": str(status_code)})


def _export_to_otel(event_type: str, data: dict):
    """Export mite stats events to OpenTelemetry metrics"""
    if event_type == "http_request":
        method = data.get('method', 'unknown')
        status = str(data.get('status_code', 0))
        
        if _metrics.get('requests_total'):
            _metrics['requests_total'].add(1, {"method": method, "status": status})
        
        if _metrics.get('request_duration'):
            _metrics['request_duration'].record(
                data.get('duration', 0), {"method": method})


def init_stats_mapping():
    """Initialize automatic stats collection if enabled"""
    if not get_otel_config()["enabled"]:
        return
    
    _init_metrics()
    
    # Try to hook into mite's existing stats system
    try:
        from mite.stats import Stats
        
        if hasattr(Stats, 'record'):
            original_record = Stats.record
            
            def traced_record(self, event_type, **data):
                result = original_record(self, event_type, **data)
                _export_to_otel(event_type, data)
                return result
            
            Stats.record = traced_record
    except (ImportError, AttributeError):
        pass  # Stats system not available