import json
import logging
import time

from jinja2 import Template

logger = logging.getLogger(__name__)

# Methods available on mite_browser.Browser
SUPPORTED_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}

# Values are pre-rendered with repr() so quotes/backslashes in HAR data stay valid Python
TEMPLATE = Template(
    "    async with ctx.transaction({{name}}):\n"
    "        resp = await ctx.browser.{{method}}(\n"
    "            {{url}},\n"
    "            headers={{headers}},\n"
    "{{body}}"
    "        )\n"
    "        check_status_code(resp, {{expected_status}})\n"
    "    await sleep({{sleep}})\n\n\n"
)


def set_expected_status_code(cur_page, entries):
    code = cur_page["response"]["status"]
    if code == 302 and cur_page["response"]["redirectURL"]:
        for other_page in entries:
            if cur_page["response"]["redirectURL"] == other_page["request"]["url"]:
                cur_page["response"]["redirectURL"] = other_page["response"][
                    "redirectURL"
                ]
                cur_page["response"]["status"] = other_page["response"]["status"]
                entries.remove(other_page)
                code = set_expected_status_code(cur_page, entries)
    elif code == 304:
        # a recorded 304 depends on browser cache state; a replay may get 200
        code = (200, 304)
    return code


def set_request_headers_dict(page):
    # Content-Length is recomputed for the replayed body; ":"-prefixed are HTTP/2 pseudo-headers
    return {
        header["name"]: header["value"]
        for header in page["request"]["headers"]
        if header["name"].lower() not in ("cookie", "content-length")
        and not header["name"].startswith(":")
    }


def set_request_body(page):
    post_data = page["request"].get("postData")
    if not post_data or "text" not in post_data:
        return ""
    text = post_data["text"]
    if "json" in post_data.get("mimeType", "").lower():
        try:
            return f"            json={json.loads(text)!r},\n"
        except ValueError:
            pass
    return f"            data={text!r},\n"


def _parse_urls(pages):
    """Parses urls from pages in hard file"""
    return [page["title"] for page in pages["log"]["pages"]]


def _extract_and_sort_requests(pages):
    """Pull entries from har text and sort into chronological order"""
    entries = pages["log"]["entries"]
    entries.sort(key=lambda n: n["startedDateTime"])
    return entries


def _create_journey_file_start():  # pragma: no cover
    """The lines needed for imports and journey signature needed for
    a working mite script. pragma ensures this is not counted for code
    coverage"""
    journey_start = "from asyncio import sleep\n\n"
    journey_start += "from mite_browser import browser_decorator\n"
    journey_start += "from mite_http.checks import check_status_code\n\n\n"
    journey_start += "@browser_decorator()\n"
    journey_start += "async def journey(ctx):\n"
    return journey_start


def _render_journey_transaction(page, req_method, expected_status_code, sleep_s):
    """Renders a single transaction with a predefined template for use
    in a mite journey"""
    return TEMPLATE.render(
        name=repr(f"Request {req_method} {page['request']['url']}"),
        method=req_method,
        url=repr(page["request"]["url"]),
        headers=repr(set_request_headers_dict(page)),
        body=set_request_body(page),
        expected_status=repr(expected_status_code),
        sleep=sleep_s,
    )


def har_convert_to_mite(file_name, converted_file_name, sleep_s):
    with open(file_name, "r") as f:
        temp_pages = json.loads(f.read())
    journey_main = ""
    page_urls = _parse_urls(temp_pages)
    entries = _extract_and_sort_requests(temp_pages)
    timestamp = time.strptime(
        temp_pages["log"]["pages"][0]["startedDateTime"], "%Y-%m-%dT%H:%M:%S.%fZ"
    )
    previous_timestamp = time.mktime(timestamp)
    sleep_period = 0

    for cur_page in entries:
        if (
            not cur_page["response"]["status"]
            or cur_page["request"]["url"] not in page_urls
        ):
            continue

        expected_status_code = set_expected_status_code(cur_page, entries)
        req_method = cur_page["request"]["method"].lower()
        if req_method not in SUPPORTED_METHODS:
            logger.warning(
                "Skipping unsupported method %s %s",
                req_method.upper(),
                cur_page["request"]["url"],
            )
            continue

        if sleep_s != 0:
            sleep_period = sleep_s
        else:
            timestamp = time.strptime(
                cur_page["startedDateTime"], "%Y-%m-%dT%H:%M:%S.%fZ"
            )
            timestamp = time.mktime(timestamp)
            sleep_period = int(timestamp - previous_timestamp)
            previous_timestamp = timestamp

        # main part of the journey
        journey_main += _render_journey_transaction(
            cur_page, req_method, expected_status_code, sleep_period
        )

    journey_start = _create_journey_file_start()

    with open(converted_file_name, "w") as nf:
        nf.write(journey_start + journey_main)
