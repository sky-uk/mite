import asyncio
import re
from functools import wraps
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup

from mite import ensure_fixed_separation
from mite.exceptions import MiteError
from mite_http import mite_http

EMBEDDED_URL_REGEX = re.compile(
    r"""\(\s*[\]?["']([^"':.]*:)?([^"':.]*\.[^"':.]*)[\]?["']\s*\)""", re.IGNORECASE
)


class OptionError(MiteError):
    def __init__(self, value, options):
        super().__init__(
            f"{value!r} not in options {options!r}", value=value, options=options
        )


class ElementNotFoundError(MiteError):
    def __init__(self, **kwargs):
        text = (kwargs.pop("text") or "").replace("'", "").replace('"', "")
        super().__init__(
            f"Could not find element in page with search terms: {sorted(kwargs.items())}",
            text=text,
            **kwargs,
        )


def url_builder(base_url, *args, **kwargs):
    url = base_url
    for arg in args:
        url = urljoin(url, arg)
    if kwargs:
        url = "".join([url, "?", urlencode(kwargs)])
    return url


def browser_decorator(separation=0, embedded_resources=False):
    def wrapper_factory(func):
        @wraps(func)
        @mite_http
        async def wrapper(context, *args, **kwargs):
            context.browser = Browser(context, embedded_resources)
            async with ensure_fixed_separation(separation):
                result = await func(context, *args, **kwargs)
            del context.browser
            return result

        return wrapper

    return wrapper_factory


class Browser:
    """Browser abstraction wraps a session and provides some behaviour that is closer to a real browser."""

    def __init__(self, context, embedded_res=False):
        self._ctx = context
        self._session = context.http
        self._embedded_res = embedded_res

    async def _download_resource(self, url, origin, type):
        """Download a resource and then register it with the origin it came from."""
        resource = await self._session.request("GET", url)
        origin._register_resource(resource, type)

    async def _download_resources(self, origin):
        """Downloads embedded resources, will do this recursively when content like iframes are present"""
        await asyncio.gather(
            *[
                self._download_resource(url, origin, rtype)
                for url, rtype in origin._embeded_urls
            ]
        )
        await asyncio.gather(
            *[
                self._download_resources(resource)
                for resource in origin._resources_with_embedabbles
            ]
        )

    async def request(self, method, url, *args, **kwargs):
        """Perform a request and return a page object"""
        # Wrap everything in page object
        embedded_res = kwargs.pop("embedded_res", self._embedded_res)
        method_func = getattr(self._session, method.lower())
        resp = await method_func(url, *args, **kwargs)
        page = Page(resp, self)
        if embedded_res:
            async with self._ctx.transaction(
                f"{self._ctx._transaction_name} - embedded resources"
            ):
                await self._download_resources(page)
        return page

    @property
    def headers(self):
        return self._session.headers

    async def get(self, url, *args, **kwargs):
        return await self.request("GET", url, *args, **kwargs)

    async def post(self, url, *args, **kwargs):
        return await self.request("POST", url, *args, **kwargs)

    async def options(self, url, *args, **kwargs):
        return await self.request("OPTIONS", url, *args, **kwargs)

    async def patch(self, url, *args, **kwargs):
        return await self.request("PATCH", url, *args, **kwargs)

    def erase_all_cookies(self):
        self._session.erase_all_cookies()

    def erase_session_cookies(self):
        self._session.erase_session_cookies()

    def get_cookie_list(self):
        return self._session.get_cookie_list()


class Resource:
    """Base class for web resources"""

    def __init__(self, response, browser):
        self.response = response
        self.browser = browser

    @property
    def text(self):
        return self.response.text

    @property
    def _embeded_urls(self):
        """At the moment there is no reason to look for a url inside the resource source code such an image"""
        return []

    @property
    def _resources_with_embedabbles(self):
        """At the moment the resource will not contain their own embedded resources"""
        return []


class Page(Resource):
    """Page object built from a HTML response."""

    def __init__(self, response, browser):
        super().__init__(response, browser)
        self._dom = None
        self.scripts = []
        self.stylesheets = []
        self.resources = []
        self.frames = []

    def assert_element_in(
        self, name=None, attrs=None, recursive=True, text=None, **kwargs
    ):
        if attrs is None:
            attrs = {}
        if self.find(name=name, attrs=attrs, recursive=recursive, text=text, **kwargs):
            return True
        else:
            raise ElementNotFoundError(name=name, attrs=attrs, text=text, **kwargs)

    @property
    def dom(self):
        if self._dom is None:
            self._dom = BeautifulSoup(self.response.text, "html.parser")
        return self._dom

    @property
    def cookies(self):
        return self.response.cookies

    @property
    def text(self):
        return self.response.text

    @property
    def headers(self):
        return self.response.headers

    @property
    def status_code(self):
        return self.response.status_code

    def find_all(self, *args, **kwargs):
        """Calls self.dom.find_all"""
        return self.dom.find_all(*args, **kwargs)

    def find(self, *args, **kwargs):
        """Calls self.dom.find"""
        return self.dom.find(*args, **kwargs)

    @property
    def _resources_with_embedabbles(self):
        """Any sub-resources of a page which might also contain their own embedded resources"""
        return self.frames + self.stylesheets

    def _register_resource(self, response, rtype):
        if rtype == "resource":
            self.resources.append(Resource(response, self.browser))
        elif rtype == "script":
            self.scripts.append(Script(response, self.browser))
        elif rtype == "stylesheet":
            self.stylesheets.append(Stylesheet(response, self.browser))
        elif rtype == "page":
            self.frames.append(Page(response, self.browser))

    @property
    def _embeded_urls(self):
        """Extracts all embedded resources from a page"""
        # TODO: Look into prerender and whether we should be getting these resources.
        base_url = self.response.url
        for burl in self.find_all("base", {"href": True}):
            base_url = burl.attrs["href"]  # reset the base url to the one in the page
        for elem in self.find_all(True, attrs={"background": True}):
            yield url_builder(base_url, elem.attrs["background"]), "resource"
        for elem in self.find_all(["img", "embed", "bgsound"], attrs={"src": True}):
            yield url_builder(base_url, elem.attrs["src"]), "resource"
        for elem in self.find_all(["script"], attrs={"src": True}):
            yield url_builder(base_url, elem.attrs["src"]), "script"
        for elem in self.find_all(["frame", "iframe"], attrs={"src": True}):
            yield url_builder(base_url, elem.attrs["src"]), "page"
        for elem in self.find_all("link", attrs={"rel": "stylesheet", "href": True}):
            yield url_builder(base_url, elem.attrs["href"]), "stylesheet"
        for elem in self.find_all("input", attrs={"type": "image", "href": True}):
            yield url_builder(base_url, elem.attrs["href"]), "resource"
        for elem in self.find_all("applet", attrs={"code": True}):
            yield url_builder(base_url, elem.attrs["code"]), "resource"
        for elem in self.find_all("object", attrs={"codebase": True}):
            yield url_builder(base_url, elem.attrs["codebase"]), "resource"
        for elem in self.find_all("object", attrs={"data": True}):
            yield url_builder(base_url, elem.attrs["data"]), "resource"
        for elem in self.find_all(True, attrs={"style": True}):
            if elem.attrs["style"].strip().startswith("url("):
                url = elem.attrs["style"].split("url(", 1)[-1].rsplit(")", 1)[0]
                yield url_builder(base_url, url), "resource"

    async def on_dom_ready(self):
        # awaitable dom ready
        pass

    def get_form(self, name=None):
        return [f for f in self.get_forms() if name is None or f.name == name][0]

    def get_forms(self):
        return [Form(e, self) for e in self.find_all("form")]

    async def click_link(self, text):
        elem = self.find("a", text=text)
        href = elem.attrs["href"]
        return await self.browser.get(url_builder(self.response.url, href))

    async def xhr_request(
        self, method, rel_or_abs_url, *, formdata=None, data=None, json=None, **kwargs
    ):
        headers = {"Referer": self.response.url, "X-Requested-With": "XMLHttpRequest"}
        if formdata is not None:
            assert data is None
            data = urlencode(formdata)
            headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        return await self.browser._session.request(
            method,
            url_builder(self.response.url, rel_or_abs_url),
            data=data,
            json=json,
            headers=headers,
        )

    async def xhr_post(
        self, rel_or_abs_url, *, formdata=None, data=None, json=None, **kwargs
    ):
        return await self.xhr_request(
            "POST", rel_or_abs_url, formdata=formdata, data=data, json=json, **kwargs
        )

    def __repr__(self):
        return str(self.dom)


class Script(Resource):
    def __init__(self, response, browser):
        super().__init__(response, browser)

    @property
    def text(self):
        return self.response.text


class Stylesheet(Resource):
    """Stylesheet object"""

    def __init__(self, response, browser):
        super().__init__(response, browser)
        self.resources = []

    @property
    def text(self):
        return self.response.text

    @property
    def _embeded_urls(self):
        """Extracts embedded resources from a stylesheet"""
        for match in EMBEDDED_URL_REGEX.finditer(self.response.text):
            yield url_builder(self.response.url, match[2]), "resource"

    def _register_resource(self, response, rtype):
        self.resources.append(Resource(response, self.browser))

    @property
    def _resources_with_embedabbles(self):
        """Any sub-resources of a stylesheet which might also contain their own embedded resources"""
        return self.resources


class Form:
    def __init__(self, element, page):
        self._page = page
        self.element = element
        self.method = element.get("method", "POST").upper()
        self.action = element.get("action")
        self.name = element.get("name", element.get("id"))
        self.fields = {}
        self.files = {}
        self._set_fields()

    def _set_fields(self):
        for f in self._extract_fields_as_subtype():
            if isinstance(f, FileInputField):
                self.files[f.name] = f
            else:
                self.fields[f.name] = f

    def _serialize(self):
        """Serializing should get files and data ready for submission. However acurl backend not currently
        supporting files so just data will be submitted.

        TODO: Add file support back in when we have acurl sorted"""
        return {
            "data": urlencode(
                {name: f.value for name, f in self.fields.items() if not f.disabled}
            )
        }

    def _extract_fields_as_subtype(self):
        FIELD_TYPES = ["select", "textarea", "input"]
        fields = self.element.find_all(FIELD_TYPES)
        radio_field_names = set()
        for field in fields:
            if field.name == "select":
                yield SelectField(field)
            elif field.name == "textarea":
                yield BaseFormField(field)
            elif field.name == "input":
                if field.attrs["type"] in ["reset", "submit", "button"]:
                    continue
                elif field.attrs["type"] == "file":
                    yield FileInputField(field)
                elif field.attrs["type"] == "radio":
                    radio_field_name = field.attrs["name"]
                    if radio_field_name in radio_field_names:
                        continue
                    radio_field_names.add(radio_field_name)
                    radios = [f for f in fields if f.attrs["name"] == radio_field_name]
                    yield RadioField(radios)
                elif field.attrs["type"] == "checkbox":
                    yield CheckboxField(field)
                else:
                    yield BaseFormField(field)

    def __getitem__(self, item):
        if result := self.fields.get(item) or self.files.get(item):
            return result
        else:
            raise KeyError(f"{item} not in form fields")

    def __delitem__(self, item):
        del self.fields[item]

    def __setitem__(self, item, value):
        if item in self.fields:
            self.fields[item].value = value
        elif item in self.files:
            self.files[item].value = value
        else:
            # Fudge to create a fake form field
            self.fields[item] = FakeFormField(item, value)

    async def submit(self, base_url="", embedded_res=False, **kwargs):
        if base_url == "":
            base_url = self._page.response.url
        return await self._page.browser.request(
            self.method,
            url_builder(base_url, self.action),
            embedded_res=embedded_res,
            **self._serialize(),
            **kwargs,
        )

    def __repr__(self):
        return f"<{self.__class__.__name__} name={self.name} method={self.method} action={self.action} fields={self.fields} files={self.files}>"


def _field_is_disabled(element):
    status = element.attrs.get("disabled")
    return bool(status and status.lower() in ["disabled", "true"])


class BaseFormField:
    def __init__(self, element):
        self.element = element
        self.name = element.attrs.get("name")
        self._value = element.attrs.get("value")
        self._disabled = _field_is_disabled(element)

    @property
    def disabled(self):
        return self._disabled

    def enable(self):
        self._disabled = False

    def disable(self):
        self._disabled = True

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = value

    def __repr__(self):
        return f"<{self.__class__.__name__} name={self.name!r} value={self.value!r} disabled={self.disabled!r}>"


class SelectField(BaseFormField):
    def __init__(self, element):
        super().__init__(element)
        self.options = element.find_all("option")

    def _get_options(self):
        if not self.options[-1].value:
            return [o.text for o in self.options]
        else:
            return [o.value for o in self.options]

    # I want to use this but the existing LR tests are posting values not in the dropdown
    # @BaseFormField.value.setter
    # def value(self, value):
    #    if value in self.options:
    #        self._value = value
    #    else:
    #        raise OptionError(value, self.options)


class CheckboxField(BaseFormField):
    def __init__(self, element):
        super().__init__(element)
        self._checked = False

    def toggle(self):
        self._checked = not self._checked
        return self._checked

    @property
    def disabled(self):
        return self._disabled and (not self._checked)


class RadioField:
    """Radio fields are made up of multiple inputs with the same name but submit only one value."""

    def __init__(self, elements):
        self.elements = elements
        self.name = elements[0].attrs.get("name")
        self._value = elements[0].attrs.get("value")
        self._disabled = _field_is_disabled(elements[0])
        self.options = [e.get("value") for e in self.elements]

    @property
    def disabled(self):
        return self._disabled

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        if value in self.options:
            self._value = value
        else:
            raise OptionError(value, self.options)

    def __repr__(self):
        return f"<{self.__class__.__name__} name={self.name!r} value={self.value!r} options={self.options!r} disabled={self.disabled!r}>"


class FileInputField(BaseFormField):
    def __init__(self, element):
        super().__init__(element)
        self._value = []

    @BaseFormField.value.setter
    def value(self, file):
        self._value.append(file)


class FakeFormField:
    """For adding in fields that don't already exist. Shouldn't be necessary in most cases but loadrunner tests needed
    it."""

    def __init__(self, name, value, disabled=False):
        self.element = None
        self.name = name
        self.value = value
        self.disabled = disabled
