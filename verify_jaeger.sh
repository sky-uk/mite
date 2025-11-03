#!/bin/bash
# Quick script to verify Jaeger integration is working

echo "🔍 Checking Jaeger Status"
echo "=========================="
echo ""

# Check if Jaeger is running
if ! docker ps | grep -q jaeger; then
    echo "❌ Jaeger container is not running!"
    echo "   Start it with: docker-compose -f docker-compose-otel.yml up -d"
    exit 1
fi

echo "✅ Jaeger container is running"
echo ""

# Check services
echo "📊 Services in Jaeger:"
SERVICES=$(curl -s http://localhost:16686/api/services | python3 -c "import sys, json; data = json.load(sys.stdin); print('\n'.join(data['data']))" 2>/dev/null)

if [ -z "$SERVICES" ]; then
    echo "   ⚠️  No services found yet"
else
    echo "$SERVICES" | sed 's/^/   - /'
fi
echo ""

# Check traces for mite-demo
if echo "$SERVICES" | grep -q "mite-demo"; then
    TRACE_COUNT=$(curl -s "http://localhost:16686/api/traces?service=mite-demo&limit=100" | python3 -c "import sys, json; data = json.load(sys.stdin); print(len(data['data']))" 2>/dev/null)
    echo "✅ Found $TRACE_COUNT traces for mite-demo"
    echo ""
    echo "🌐 View traces at: http://localhost:16686"
    echo "   1. Select 'mite-demo' from the Service dropdown"
    echo "   2. Adjust time range to 'Last Hour'"
    echo "   3. Click 'Find Traces'"
else
    echo "ℹ️  No mite-demo traces yet. Run:"
    echo "   python demo_otel.py jaeger"
fi
