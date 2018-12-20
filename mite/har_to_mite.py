from jinja2 import Template
import json
import os


TEMPLATE = Template(
            '    async with ctx.transaction("Request {{method}} {{url}}"):\n'
            '        resp = await ctx.browser.{{method}}(\n'
            '            \'{{url}}\',\n'
            '            headers={{headers}},\n'
            '            {{json}}'
            '            )\n'
            '        check_status_code{{check_groups}}(resp, {{expected_status}})\n'
            '    await sleep({{sleep}})\n\n\n'
        )


def set_expected_status_code(cur_page, entries):
    code = cur_page['response']['status']
    status_groups = ""
    if code == 302 and cur_page['response']['redirectURL']:
        for other_page in entries:
            if cur_page['response']['redirectURL'] == other_page['request']['url']:
                cur_page['response']['redirectURL'] = other_page['request']['url']
                cur_page['response']['status'] = other_page['response']['status']
                pages.remove(other_page)
                code, status_groups = set_sexpected_status_code(cur_page, entries)
    elif code == 304:
        code = "200, 304"
        status_groups = "_in_groups"
    return code, status_groups


def set_request_headers_dict(page):
    return {header['name']:header['value'] for header in page['request']['headers'] if header['name'] != 'Cookie'}


def set_request_body(method, page):
    if method == 'post':
        # the body need to be studied more
        return "json={}\n".format(page['request']['postData'])
    return ""


def har_convert_to_mite(file_name, converted_file_name, sleep_s):
    # TODO: accurate sleep times should be made possible by extracting the timestamps from the har file
    base_path = os.getcwd()
    with open(base_path + '/' + file_name.lstrip('/'), 'r') as f:
        temp_pages = json.loads(f.read())
    journey_main = ""
    page_urls = [page['title'] for page in temp_pages['log']['pages']] 
    entries = temp_pages['log']['entries']
    # Sort based on start time, may not be necessary. Review HAR spec 
    entries.sort(key=lambda n: n["startedDateTime"])

    while entries:
        cur_page = entries.pop()
        
        if not cur_page['response']['status'] or not cur_page['request']['url'] in page_urls:
            continue

        expected_status_code, check_groups_status = set_expected_status_code(cur_page, entries)
        req_method = cur_page['request']['method'].lower()

        # main part of the journey
        journey_main += TEMPLATE.render(
            date_time=cur_page['startedDateTime'],
            method=req_method,
            url=cur_page['request']['url'],
            headers=set_request_headers_dict(cur_page),
            json=set_request_body(req_method, cur_page),
            check_groups=check_groups_status,
            expected_status=expected_status_code,
            sleep=sleep_s)


    # first part of the journey
    journey_start = "from .utils import check_status_code, check_status_code_in_groups\n"
    journey_start += "from mite_browser import browser_decorator\n"
    journey_start += "from mite.exceptions import MiteError\n"
    journey_start += "from asyncio import sleep\n\n"
    journey_start += "@browser_decorator()\n"
    journey_start += "async def journey(ctx):\n"
    #journey_start += "    # import ipdb; ipdb.set_trace()\n\n"

    with open(base_path + '/' + converted_file_name.lstrip('/'), 'w') as nf:
        nf.write(journey_start + journey_main)
