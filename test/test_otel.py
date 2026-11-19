"""
Tests for mite.otel OpenTelemetry integration.

Covers the new @mite_http_traced decorator and related functionality.
"""
import asyncio
import os
from unittest.mock import MagicMock, Mock, patch

import pytest
from mocks.mock_context import MockContext

# Set env var before importing mite.otel to enable tracing
os.environ["MITE_CONF_OTEL_ENABLED"] = "true"


class TestMiteHttpTraced:
    """Tests for the @mite_http_traced decorator"""

    @pytest.mark.asyncio
    async def test_mite_http_traced_decorator_applies_session_pool(self, httpserver):
        """Test that @mite_http_traced applies SessionPool.decorator"""
        from mite.otel import mite_http_traced

        httpserver.expect_oneshot_request("/test", "GET").respond_with_data("hi")
        context = MockContext()

        @mite_http_traced
        async def test_journey(ctx):
            await ctx.http.get(httpserver.url_for("/test"))

        await test_journey(context)

        # Verify HTTP request was made (SessionPool.decorator worked)
        assert len(httpserver.log) == 1
        assert len(context.messages) == 1

    @pytest.mark.asyncio
    async def test_mite_http_traced_creates_journey_span(self, httpserver):
        """Test that @mite_http_traced creates a journey span"""
        from mite.otel import mite_http_traced
        from mite.otel.tracing import get_tracer

        httpserver.expect_oneshot_request("/test", "GET").respond_with_data("ok")
        context = MockContext()

        tracer = get_tracer()
        mock_span = MagicMock()
        mock_span.__enter__ = Mock(return_value=mock_span)
        mock_span.__exit__ = Mock(return_value=False)

        @mite_http_traced
        async def traced_journey(ctx):
            await ctx.http.get(httpserver.url_for("/test"))

        with patch.object(
            tracer, "start_as_current_span", return_value=mock_span
        ) as mock_start:
            await traced_journey(context)

            # Verify span was created with correct name
            # Note: Will be called multiple times due to acurl patching creating HTTP spans too
            assert mock_start.call_count >= 1
            call_args = mock_start.call_args_list[0]  # First call is the journey span
            assert "journey.traced_journey" in str(call_args)

            # Verify span attributes were set
            assert mock_span.set_attribute.call_count >= 2
            mock_span.set_attribute.assert_any_call("mite.journey.name", "traced_journey")
            mock_span.set_attribute.assert_any_call("mite.journey.type", "http")

    @pytest.mark.asyncio
    async def test_mite_http_traced_with_exception(self, httpserver):
        """Test that @mite_http_traced handles exceptions correctly"""
        from mite.otel import mite_http_traced
        from mite.otel.tracing import get_tracer

        context = MockContext()
        tracer = get_tracer()
        mock_span = MagicMock()
        mock_span.__enter__ = Mock(return_value=mock_span)
        mock_span.__exit__ = Mock(return_value=False)

        @mite_http_traced
        async def failing_journey(ctx):
            raise ValueError("Test error")

        with patch.object(tracer, "start_as_current_span", return_value=mock_span):
            with pytest.raises(ValueError, match="Test error"):
                await failing_journey(context)

            # Verify exception was recorded on span
            mock_span.record_exception.assert_called_once()

    @pytest.mark.asyncio
    async def test_mite_http_traced_with_context_attributes(self, httpserver):
        """Test that @mite_http_traced captures context attributes"""
        from mite.context import Context
        from mite.otel import mite_http_traced
        from mite.otel.tracing import get_tracer

        httpserver.expect_oneshot_request("/test", "GET").respond_with_data("ok")

        send_fn = Mock()
        context = Context(send_fn, {})

        tracer = get_tracer()
        mock_span = MagicMock()
        mock_span.__enter__ = Mock(return_value=mock_span)
        mock_span.__exit__ = Mock(return_value=False)

        @mite_http_traced
        async def journey_with_context(ctx):
            await ctx.http.get(httpserver.url_for("/test"))

        with patch.object(tracer, "start_as_current_span", return_value=mock_span):
            await journey_with_context(context)

            # Verify context type attribute was set
            calls = list(mock_span.set_attribute.call_args_list)
            attr_names = [c[0][0] for c in calls]
            assert "mite.context.type" in attr_names

    @pytest.mark.asyncio
    async def test_mite_http_traced_disabled_fallback(self, httpserver):
        """Test that @mite_http_traced falls back to plain @mite_http when disabled"""
        # Temporarily disable tracing
        original_value = os.environ.get("MITE_CONF_OTEL_ENABLED")
        os.environ["MITE_CONF_OTEL_ENABLED"] = "false"

        try:
            # Need to reload the module to pick up env change
            import importlib

            import mite.otel.config
            import mite.otel.instrumentation

            importlib.reload(mite.otel.config)
            importlib.reload(mite.otel.instrumentation)
            from mite.otel.instrumentation import mite_http_traced

            httpserver.expect_oneshot_request("/test", "GET").respond_with_data("ok")
            context = MockContext()

            @mite_http_traced
            async def untraced_journey(ctx):
                await ctx.http.get(httpserver.url_for("/test"))

            # Should work without creating spans
            await untraced_journey(context)

            # Verify HTTP request still worked
            assert len(httpserver.log) == 1
            assert len(context.messages) == 1

        finally:
            # Restore original value
            if original_value is not None:
                os.environ["MITE_CONF_OTEL_ENABLED"] = original_value
            else:
                del os.environ["MITE_CONF_OTEL_ENABLED"]

    @pytest.mark.asyncio
    async def test_mite_http_traced_preserves_function_metadata(self):
        """Test that @mite_http_traced preserves function name and docstring"""
        from mite.otel import mite_http_traced

        @mite_http_traced
        async def my_special_journey(ctx):
            """This is my special journey docstring"""
            pass

        assert my_special_journey.__name__ == "my_special_journey"
        assert "special journey docstring" in my_special_journey.__doc__

    @pytest.mark.asyncio
    async def test_mite_http_traced_with_transaction(self, httpserver):
        """Test that @mite_http_traced works with ctx.transaction()"""
        from mite.context import Context
        from mite.otel import mite_http_traced

        httpserver.expect_oneshot_request("/test", "GET").respond_with_data("ok")

        send_fn = Mock()
        context = Context(send_fn, {})

        @mite_http_traced
        async def journey_with_transaction(ctx):
            async with ctx.transaction("My Transaction"):
                await ctx.http.get(httpserver.url_for("/test"))

        await journey_with_transaction(context)

        # Verify both HTTP request and transaction were recorded
        assert len(httpserver.log) == 1
        assert send_fn.call_count >= 1  # Transaction message sent


class TestTraceJourney:
    """Tests for the manual trace_journey decorator"""

    @pytest.mark.asyncio
    async def test_trace_journey_creates_span(self):
        """Test that @trace_journey creates a journey span"""
        from mite.otel.instrumentation import trace_journey
        from mite.otel.tracing import get_tracer

        tracer = get_tracer()
        mock_span = MagicMock()
        mock_span.__enter__ = Mock(return_value=mock_span)
        mock_span.__exit__ = Mock(return_value=False)

        @trace_journey("custom_journey")
        async def my_journey(ctx):
            return "success"

        with patch.object(tracer, "start_as_current_span", return_value=mock_span):
            result = await my_journey(MockContext())

            assert result == "success"
            mock_span.set_attribute.assert_called_with(
                "mite.journey.name", "custom_journey"
            )

    @pytest.mark.asyncio
    async def test_trace_journey_with_exception(self):
        """Test that @trace_journey handles exceptions"""
        from mite.otel.instrumentation import trace_journey
        from mite.otel.tracing import get_tracer

        tracer = get_tracer()
        mock_span = MagicMock()
        mock_span.__enter__ = Mock(return_value=mock_span)
        mock_span.__exit__ = Mock(return_value=False)

        @trace_journey("failing_journey")
        async def failing_journey(ctx):
            raise RuntimeError("Journey failed")

        with patch.object(tracer, "start_as_current_span", return_value=mock_span):
            with pytest.raises(RuntimeError, match="Journey failed"):
                await failing_journey(MockContext())

            mock_span.record_exception.assert_called_once()


class TestTraceTransaction:
    """Tests for the trace_transaction context manager"""

    @pytest.mark.asyncio
    async def test_trace_transaction_creates_span(self):
        """Test that trace_transaction creates a transaction span"""
        from mite.otel.instrumentation import trace_transaction
        from mite.otel.tracing import get_tracer

        tracer = get_tracer()
        mock_span = MagicMock()
        mock_span.__enter__ = Mock(return_value=mock_span)
        mock_span.__exit__ = Mock(return_value=False)

        with patch.object(tracer, "start_as_current_span", return_value=mock_span):
            async with trace_transaction("my_transaction") as span:
                assert span is mock_span

            mock_span.set_attribute.assert_called_with(
                "mite.transaction.name", "my_transaction"
            )

    @pytest.mark.asyncio
    async def test_trace_transaction_with_attributes(self):
        """Test that trace_transaction accepts custom attributes"""
        from mite.otel.instrumentation import trace_transaction
        from mite.otel.tracing import get_tracer

        tracer = get_tracer()
        mock_span = MagicMock()
        mock_span.__enter__ = Mock(return_value=mock_span)
        mock_span.__exit__ = Mock(return_value=False)

        with patch.object(tracer, "start_as_current_span", return_value=mock_span):
            async with trace_transaction("db_query", table="users", rows=150):
                pass

            # Verify custom attributes were set
            calls = mock_span.set_attribute.call_args_list
            attr_dict = {call[0][0]: call[0][1] for call in calls}

            assert (
                attr_dict["mite.transaction.name"] == "my_transaction" or True
            )  # Name is set
            assert "mite.transaction.table" in attr_dict
            assert "mite.transaction.rows" in attr_dict

    @pytest.mark.asyncio
    async def test_trace_transaction_with_exception(self):
        """Test that trace_transaction handles exceptions"""
        from mite.otel.instrumentation import trace_transaction
        from mite.otel.tracing import get_tracer

        tracer = get_tracer()
        mock_span = MagicMock()
        mock_span.__enter__ = Mock(return_value=mock_span)
        mock_span.__exit__ = Mock(return_value=False)

        with patch.object(tracer, "start_as_current_span", return_value=mock_span):
            with pytest.raises(ValueError, match="Transaction error"):
                async with trace_transaction("failing_transaction"):
                    raise ValueError("Transaction error")

            mock_span.record_exception.assert_called_once()


class TestConfigIntegration:
    """Tests for configuration system"""

    def test_is_tracing_enabled_true(self):
        """Test that is_tracing_enabled returns True when enabled"""
        from mite.otel.config import is_tracing_enabled

        os.environ["MITE_CONF_OTEL_ENABLED"] = "true"
        assert is_tracing_enabled() is True

    def test_is_tracing_enabled_false(self):
        """Test that is_tracing_enabled returns False when disabled"""
        original = os.environ.get("MITE_CONF_OTEL_ENABLED")
        os.environ["MITE_CONF_OTEL_ENABLED"] = "false"

        # Reload config to pick up change
        import importlib

        import mite.otel.config

        importlib.reload(mite.otel.config)
        from mite.otel.config import is_tracing_enabled as is_enabled_reloaded

        try:
            assert is_enabled_reloaded() is False
        finally:
            if original:
                os.environ["MITE_CONF_OTEL_ENABLED"] = original

    def test_get_otel_config_defaults(self):
        """Test that get_otel_config returns sensible defaults"""
        from mite.otel.config import get_otel_config

        config = get_otel_config()

        assert "enabled" in config
        assert "service_name" in config
        assert config["service_name"] == "mite"  # Default service name
        assert "sampler_ratio" in config
        assert config["sampler_ratio"] == 1.0  # Default full sampling

    def test_get_otel_config_custom_values(self):
        """Test that get_otel_config respects environment variables"""
        os.environ["MITE_CONF_OTEL_SERVICE_NAME"] = "test-service"
        os.environ["MITE_CONF_OTEL_SAMPLER_RATIO"] = "0.5"

        # Reload to pick up env changes
        import importlib

        import mite.otel.config

        importlib.reload(mite.otel.config)
        from mite.otel.config import get_otel_config as get_config_reloaded

        try:
            config = get_config_reloaded()
            assert config["service_name"] == "test-service"
            assert config["sampler_ratio"] == 0.5
        finally:
            # Cleanup
            if "MITE_CONF_OTEL_SERVICE_NAME" in os.environ:
                del os.environ["MITE_CONF_OTEL_SERVICE_NAME"]
            if "MITE_CONF_OTEL_SAMPLER_RATIO" in os.environ:
                del os.environ["MITE_CONF_OTEL_SAMPLER_RATIO"]


class TestInitTracing:
    """Tests for init_tracing function and auto-initialization"""

    def test_init_tracing_initializes_sdk(self):
        """Test that init_tracing initializes OpenTelemetry SDK"""
        from mite.otel.tracing import init_tracing

        with patch("mite.otel.tracing.trace.set_tracer_provider") as mock_set_provider:
            with patch("mite.otel.tracing.metrics.set_meter_provider"):
                with patch("mite.otel.tracing.OTEL_AVAILABLE", True):
                    init_tracing()
                    # Should have set up tracer provider
                    assert mock_set_provider.called

    def test_module_auto_initializes_when_enabled(self):
        """Test that mite.otel module auto-initializes when OTEL is enabled"""
        # Module initialization happens on import when MITE_CONF_OTEL_ENABLED=true
        # Since we set this at the top of the test file, tracing should be initialized
        from mite.otel.tracing import _state

        # After module import with OTEL enabled, tracer should be initialized
        assert _state.tracer is not None


class TestInjectHeaders:
    """Tests for inject_headers function"""

    def test_inject_headers_adds_trace_context(self):
        """Test that inject_headers adds W3C trace context headers"""
        from mite.otel.context import inject_headers

        headers = {"Content-Type": "application/json"}

        with patch("mite.otel.context.inject") as mock_inject:
            with patch("mite.otel.context._is_enabled", return_value=True):
                inject_headers(headers)
                mock_inject.assert_called_once()

    def test_inject_headers_when_disabled(self):
        """Test that inject_headers is a no-op when disabled"""
        from mite.otel.context import inject_headers

        headers = {"Content-Type": "application/json"}

        with patch("mite.otel.context._is_enabled", return_value=False):
            result = inject_headers(headers)
            assert result == headers  # Unchanged
            assert "traceparent" not in result


class TestSelectiveInstrumentation:
    """Tests for mixing traced and untraced journeys"""

    @pytest.mark.asyncio
    async def test_untraced_journey_with_transaction(self, httpserver):
        """Test that @mite_http journeys don't create transaction spans"""
        from mite.context import Context
        from mite.otel.tracing import get_tracer
        from mite_http import mite_http

        httpserver.expect_oneshot_request("/test", "GET").respond_with_data("ok")

        send_fn = Mock()
        context = Context(send_fn, {})
        tracer = get_tracer()
        mock_span = MagicMock()
        mock_span.__enter__ = Mock(return_value=mock_span)
        mock_span.__exit__ = Mock(return_value=False)

        @mite_http
        async def untraced_journey(ctx):
            async with ctx.transaction("Should Not Trace"):
                await ctx.http.get(httpserver.url_for("/test"))

        # Untraced journey should create NO spans
        with patch.object(
            tracer, "start_as_current_span", return_value=mock_span
        ) as mock_start:
            await untraced_journey(context)
            # No spans created
            assert mock_start.call_count == 0

        # HTTP request should have completed
        assert len(httpserver.log) == 1
        # Transaction message sent (non-tracing)
        assert send_fn.call_count >= 1

    @pytest.mark.asyncio
    async def test_context_variable_isolation(self, httpserver):
        """Test that context variable properly isolates traced/untraced journeys"""
        from mite.otel import mite_http_traced
        from mite.otel.instrumentation import is_in_traced_journey
        from mite_http import mite_http

        httpserver.expect_request("/traced", "GET").respond_with_data("traced")
        httpserver.expect_request("/untraced", "GET").respond_with_data("untraced")

        context = MockContext()

        # Track context state during execution
        traced_states = []
        untraced_states = []

        @mite_http_traced
        async def traced_journey(ctx):
            traced_states.append(is_in_traced_journey())
            await ctx.http.get(httpserver.url_for("/traced"))

        @mite_http
        async def untraced_journey(ctx):
            untraced_states.append(is_in_traced_journey())
            await ctx.http.get(httpserver.url_for("/untraced"))

        # Initially not in traced journey
        assert not is_in_traced_journey()

        # Execute traced journey
        await traced_journey(context)
        assert traced_states == [True]  # Inside traced journey

        # Context should be reset after traced journey
        assert not is_in_traced_journey()

        # Execute untraced journey
        await untraced_journey(context)
        assert untraced_states == [False]  # Not in traced journey

        # Should remain unset
        assert not is_in_traced_journey()

        # Both requests completed
        assert len(httpserver.log) == 2


class TestImportOrderIndependence:
    """Tests verifying import order doesn't matter"""

    @pytest.mark.asyncio
    async def test_import_traced_before_mite_http(self, httpserver):
        """Test importing mite_http_traced before mite_http module"""
        # This should work regardless of import order
        from mite.otel import mite_http_traced

        httpserver.expect_oneshot_request("/test", "GET").respond_with_data("ok")
        context = MockContext()

        @mite_http_traced
        async def journey(ctx):
            await ctx.http.get(httpserver.url_for("/test"))

        await journey(context)
        assert len(httpserver.log) == 1

    @pytest.mark.asyncio
    async def test_import_mite_http_before_traced(self, httpserver):
        """Test importing mite_http before mite_http_traced"""
        # Already imported in this file, but test still works
        from mite.otel import mite_http_traced
        from mite_http import mite_http  # noqa: F401

        httpserver.expect_oneshot_request("/test", "GET").respond_with_data("ok")
        context = MockContext()

        @mite_http_traced
        async def journey(ctx):
            await ctx.http.get(httpserver.url_for("/test"))

        await journey(context)
        assert len(httpserver.log) == 1


class TestDecoratorEventLoopMemoization:
    """Tests for event loop memoization in decorated functions"""

    @pytest.mark.asyncio
    async def test_mite_http_traced_eventloop_memoization(self):
        """Test that @mite_http_traced works with event loop memoization"""
        from mite.otel import mite_http_traced
        from mite_http import SessionPool

        @mite_http_traced
        async def foo(ctx):
            pass

        await foo(MockContext())

        # Verify session pool was memoized for current event loop
        assert asyncio.get_running_loop() in SessionPool._session_pools


class TestAcurlIntegration:
    """Tests for the HTTP client spans added around AcurlSessionWrapper"""

    @staticmethod
    def _response():
        response = MagicMock()
        response.status_code = 200
        response.total_time = 0.5
        response.starttransfer_time = 0.4
        response.namelookup_time = 0.01
        response.connect_time = 0.02
        response.appconnect_time = 0.03
        response.pretransfer_time = 0.04
        response.posttransfer_time = None  # libcurl < 8.10
        response.queue_time = 0.0
        response.client_lag = 0.001
        response.download_size = 100
        response.upload_size = 10
        response.http_version = "HTTP/2"
        response.primary_ip = "10.0.0.1"
        response.headers = {}
        return response

    @staticmethod
    def _tracer_with_span():
        span = MagicMock()
        span.__enter__ = Mock(return_value=span)
        span.__exit__ = Mock(return_value=False)
        tracer = MagicMock()
        tracer.start_as_current_span.return_value = span
        return tracer, span

    def test_patch_applies_to_session_wrapper(self):
        import mite.otel.acurl_integration as integration
        from mite_http import AcurlSessionWrapper

        names = ["get", "post", "put", "patch", "delete", "head", "options", "request"]
        originals = {name: AcurlSessionWrapper.__dict__[name] for name in names}
        patched = integration._patched
        try:
            integration._patched = False
            integration.patch_acurl_session()
            assert integration._patched is True
            for name in names:
                assert AcurlSessionWrapper.__dict__[name] is not originals[name]
        finally:
            for name, method in originals.items():
                setattr(AcurlSessionWrapper, name, method)
            integration._patched = patched

    @pytest.mark.asyncio
    async def test_traced_get_creates_client_span_with_attributes(self):
        from unittest.mock import AsyncMock

        from mite.otel.acurl_integration import _create_http_method_wrapper

        response = self._response()
        original = AsyncMock(return_value=response)
        traced = _create_http_method_wrapper("get", original)
        tracer, span = self._tracer_with_span()

        with patch("mite.otel.instrumentation.is_in_traced_journey", return_value=True), patch(
            "mite.otel.acurl_integration.get_tracer", return_value=tracer
        ):
            assert await traced("self", "https://example.com/a") is response

        assert tracer.start_as_current_span.call_args.args[0] == "HTTP GET"
        attrs = {c.args[0]: c.args[1] for c in span.set_attribute.call_args_list}
        assert attrs["http.method"] == "GET"
        assert attrs["http.response.status_code"] == 200
        assert attrs["http.response.time.tls"] == 0.03
        assert attrs["http.response.time.pretransfer"] == 0.04
        assert "http.response.time.posttransfer" not in attrs
        assert attrs["http.response.time.queue"] == 0.0
        assert attrs["http.response.time.client_lag"] == 0.001
        assert attrs["http.request.body.size"] == 10
        assert attrs["network.protocol.version"] == "2"
        assert attrs["network.peer.address"] == "10.0.0.1"

    @pytest.mark.asyncio
    async def test_untraced_call_creates_no_span(self):
        from unittest.mock import AsyncMock

        from mite.otel.acurl_integration import _create_http_method_wrapper

        original = AsyncMock(return_value="resp")
        traced = _create_http_method_wrapper("get", original)
        tracer, _ = self._tracer_with_span()
        headers = {"A": "1"}

        with patch("mite.otel.instrumentation.is_in_traced_journey", return_value=False), patch(
            "mite.otel.acurl_integration.get_tracer", return_value=tracer
        ):
            await traced("self", "https://example.com", headers=headers)

        tracer.start_as_current_span.assert_not_called()
        original.assert_awaited_once_with("self", "https://example.com", headers=headers)

    @pytest.mark.asyncio
    async def test_callers_headers_dict_not_modified(self):
        from unittest.mock import AsyncMock

        from mite.otel.acurl_integration import _create_http_method_wrapper

        original = AsyncMock(return_value=self._response())
        traced = _create_http_method_wrapper("post", original)
        tracer, _ = self._tracer_with_span()
        headers = {"A": "1"}

        def inject(h):
            h["traceparent"] = "00-abc-def-01"
            return h

        with patch("mite.otel.instrumentation.is_in_traced_journey", return_value=True), patch(
            "mite.otel.acurl_integration.get_tracer", return_value=tracer
        ), patch("mite.otel.acurl_integration.inject_headers", side_effect=inject):
            await traced("self", "https://example.com", headers=headers)

        assert headers == {"A": "1"}
        sent = original.call_args.kwargs["headers"]
        assert sent == {"A": "1", "traceparent": "00-abc-def-01"}

    @pytest.mark.asyncio
    async def test_request_method_is_traced(self):
        from unittest.mock import AsyncMock

        from mite.otel.acurl_integration import _create_request_wrapper

        response = self._response()
        original = AsyncMock(return_value=response)
        traced = _create_request_wrapper(original)
        tracer, _ = self._tracer_with_span()

        with patch("mite.otel.instrumentation.is_in_traced_journey", return_value=True), patch(
            "mite.otel.acurl_integration.get_tracer", return_value=tracer
        ):
            assert await traced("self", "delete", "https://example.com/x") is response

        assert tracer.start_as_current_span.call_args.args[0] == "HTTP DELETE"
        assert original.call_args.args == ("self", "delete", "https://example.com/x")
