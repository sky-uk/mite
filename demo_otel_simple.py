import os


from mite.scenario import StopVolumeModel
from mite_http import mite_http
from mite import ensure_average_separation

import mite.otel


def volume_model_factory(n):
    def vm(start, end):
        if start > 60 * 15:  # Will run for 15 mins
            raise StopVolumeModel
        return n

    vm.__name__ = f"volume model {n}"
    return vm

USE_JAEGER = True

# Configure OpenTelemetry BEFORE importing mite
os.environ["MITE_CONF_OTEL_ENABLED"] = "true"
os.environ["MITE_CONF_OTEL_SERVICE_NAME"] = "mite"
os.environ["MITE_CONF_OTEL_SAMPLER_RATIO"] = "1.0"

if USE_JAEGER:
    os.environ["MITE_CONF_OTEL_SPAN_PROCESSOR"] = "otlp"
    os.environ["MITE_CONF_OTEL_OTLP_ENDPOINT"] = "http://localhost:4318/v1/traces"
    print("Exporting traces to Jaeger")
    print("   Endpoint: http://localhost:4318/v1/traces")
    print("   View UI: http://localhost:16686")
    print("   Service: mite-simple-demo")
else:
    os.environ["MITE_CONF_OTEL_SPAN_PROCESSOR"] = "console"
    print("Console mode - traces printed below")



# This is just a regular mite_http scenario - no manual tracing needed!
@mite_http
async def demo_req(ctx):
    """Regular mite HTTP request - automatically traced by OTEL"""
    async with ensure_average_separation(1):
        async with ctx.transaction("Get request"):
            response = await ctx.http.get("https://example.com/")
            print(f"  HTTP {response.status_code}")


# @mite_http 
# async def demo_post(ctx):
#     """Another request - also automatically traced"""
#     async with ensure_average_separation(1):
#         async with ctx.transaction("Post request"):
#             response = await ctx.http.post(
#                 "https://httpbin.org/post",
#                 json={"test": "data", "demo": True}
#             )
#             print(f"  ✅ HTTP {response.status_code}")


def scenario():
    return [
        ["demo_otel_simple:demo_req", None, volume_model_factory(1)],
        # ["demo_otel_simple:demo_post", None, volume_model_factory(1)],
    ]
