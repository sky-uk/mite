from unittest.mock import Mock

import acurl


def create_request(
    method, url, headers=(), cookies=(), auth=None, data=None, cert=None,
):
    if isinstance(method, str):
        method = method.encode()
    headers = tuple(h.encode("utf-8") if hasattr(h, "encode") else h for h in headers)
    return acurl.Request(method, url, headers, cookies, auth, data, cert)
