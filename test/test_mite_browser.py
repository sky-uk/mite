import importlib
import subprocess
import sys
from unittest.mock import Mock

import pytest
from mocks.mock_context import MockContext

import mite_browser as mite_browser_pkg
from mite_browser import (
    BaseFormField,
    Browser,
    CheckboxField,
    FakeFormField,
    FileInputField,
    _field_is_disabled,
    browser_decorator,
)

# Runs in a subprocess - see test_mite_http.py's test_raises_when_acurl_missing
# for why this isn't done via importlib.reload() in-process.
_BLOCK_ACURL_AND_IMPORT = """
import builtins
real_import = builtins.__import__
def fake_import(name, *args, **kwargs):
    if name == "acurl":
        raise ModuleNotFoundError(name)
    return real_import(name, *args, **kwargs)
builtins.__import__ = fake_import
import mite_browser
"""


def test_raises_when_acurl_missing():
    # mite_browser imports mite_http at module level, so a missing acurl -
    # mite_http's own optional dependency - propagates transitively.
    result = subprocess.run(
        [sys.executable, "-c", _BLOCK_ACURL_AND_IMPORT],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "pip install mite[http]" in result.stderr


def test_fake_form_field_create():
    name = "foo"
    value = "bar"
    disabled = True
    field = FakeFormField(name, value, disabled)
    assert field.name == name
    assert field.value == value
    assert field.disabled == disabled


def test_fake_form_field_defaults():
    name = "foo"
    value = "bar"
    field = FakeFormField(name, value)
    assert field.disabled is False
    assert field.element is None


def _create_element():
    element = Mock()
    element.attrs = {"name": "foo", "value": "bar"}
    return element


def test_disabled_element_parsing_true():
    element = _create_element()
    element.attrs['disabled'] = 'true'
    assert _field_is_disabled(element) is True


def test_disabled_element_parsing_disabled():
    element = _create_element()
    element.attrs['disabled'] = 'disabled'
    assert _field_is_disabled(element) is True


def test_base_form_field_create():
    field = BaseFormField(_create_element())
    assert field.name == "foo"
    assert field._value == "bar"
    assert field.disabled is False


def test_base_form_value_setter():
    """Might be a terrible looking test but can't think of a
    better way to trigger the setter logic"""
    field = BaseFormField(_create_element())
    field.value = "baz"
    assert field.value == "baz"


def test_base_form_repr():
    field = BaseFormField(_create_element())
    assert repr(field) == "<BaseFormField name='foo' value='bar' disabled=False>"


def test_base_form_enable_disable():
    field = BaseFormField(_create_element())
    field.disable()
    assert field.disabled is True
    field.enable()
    assert field.disabled is False


def test_checkbox_field():
    field = CheckboxField(_create_element())
    assert field._checked is False
    field.toggle()
    assert field._checked is True


def test_file_input_field():
    field = FileInputField(_create_element())
    assert field._value == []
    field.value = "foo"
    assert field._value == ["foo"]


@pytest.mark.asyncio
async def test_decorator():
    @browser_decorator()
    async def journey(ctx):
        assert isinstance(ctx.browser, Browser)

    await journey(MockContext())


# Deliberately last in the file - importlib.reload() rebinds module
# attributes and creates new class objects, so anything defined after it
# could be affected. Only mite_browser's own warning is expected here:
# reloading mite_browser re-runs `from mite_http import mite_http`, but
# mite_http itself is already in sys.modules and isn't reloaded, so its
# module-level warning doesn't refire.
def test_warns_on_import():
    with pytest.warns(FutureWarning, match="mite_browser will require"):
        importlib.reload(mite_browser_pkg)
