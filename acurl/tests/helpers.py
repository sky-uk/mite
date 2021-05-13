from unittest.mock import Mock

import acurl


def create_request(
    method, url, headers=(), cookies=(), auth=None, data=None, cert=None,
):
    if isinstance(method, str):
        method = method.encode()
    return acurl.Request(method, url, headers, cookies, auth, data, cert)
