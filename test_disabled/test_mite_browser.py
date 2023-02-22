from unittest.mock import Mock

import pytest
from mocks.mock_context import MockContext

from mite_browser import (
    BaseFormField,
    Browser,
    CheckboxField,
    FakeFormField,
    FileInputField,
    _field_is_disabled,
    browser_decorator,
)


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
