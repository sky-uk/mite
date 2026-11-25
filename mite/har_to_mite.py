import json
import logging
from datetime import datetime

from jinja2 import Template

logger = logging.getLogger(__name__)

# Methods available on mite_browser.Browser
SUPPORTED_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}

# Values are pre-rendered with repr() so quotes/backslashes in HAR data stay valid Python
TEMPLATE = Template(
    "    async with ensure_fixed_separation({{separation}}):\n"
    "        async with ctx.transaction({{name}}):\n"
    "            resp = await ctx.browser.{{method}}(\n"
    "                {{url}},\n"
    "                headers={{headers}},\n"
    "{{body}}"
    "            )\n"
    "            check_status_code(resp, {{expected_status}})\n"
    "\n",
    keep_trailing_newline=True,
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
    # Replay the recorded bytes unchanged; the recorded Content-Type header is kept
    post_data = page["request"].get("postData")
    if not post_data or "text" not in post_data:
        return ""
    return f"                data={post_data['text']!r},\n"


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
    journey_start = "from mite import ensure_fixed_separation\n"
    journey_start += "from mite_browser import browser_decorator\n"
    journey_start += "from mite_http.checks import check_status_code\n\n\n"
    journey_start += "@browser_decorator()\n"
    journey_start += "async def journey(ctx):\n"
    return journey_start


def _render_journey_transaction(page, req_method, expected_status_code, separation_s):
    """Renders a single transaction with a predefined template for use
    in a mite journey"""
    return TEMPLATE.render(
        name=repr(f"Request {req_method} {page['request']['url']}"),
        method=req_method,
        url=repr(page["request"]["url"]),
        headers=repr(set_request_headers_dict(page)),
        body=set_request_body(page),
        expected_status=repr(expected_status_code),
        separation=separation_s,
    )


def _started_at(entry):
    # HAR timestamps are ISO 8601; fromisoformat() only accepts "Z" from 3.11
    return datetime.fromisoformat(entry["startedDateTime"].replace("Z", "+00:00"))


def har_convert_to_mite(file_name, converted_file_name, separation_s):
    """Convert a HAR file to a mite journey.

    Each request is wrapped in ensure_fixed_separation. With ``separation_s``
    of 0 the separation is the recorded gap to the next request's start,
    otherwise every request gets ``separation_s`` seconds.
    """
    separation_s = float(separation_s)
    with open(file_name, "r") as f:
        temp_pages = json.loads(f.read())
    page_urls = _parse_urls(temp_pages)
    entries = _extract_and_sort_requests(temp_pages)

    selected = []
    # set_expected_status_code removes redirect targets from entries mid-loop
    for cur_page in list(entries):
        if not any(cur_page is entry for entry in entries):
            continue
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
        selected.append((cur_page, req_method, expected_status_code))

    journey_main = ""
    for i, (cur_page, req_method, expected_status_code) in enumerate(selected):
        if separation_s:
            separation = separation_s
        elif i + 1 < len(selected):
            gap = _started_at(selected[i + 1][0]) - _started_at(cur_page)
            separation = round(max(gap.total_seconds(), 0.0), 3)
        else:
            separation = 0
        journey_main += _render_journey_transaction(
            cur_page, req_method, expected_status_code, separation
        )

    journey_start = _create_journey_file_start()

    with open(converted_file_name, "w") as nf:
        nf.write(journey_start + journey_main.rstrip("\n") + "\n")
