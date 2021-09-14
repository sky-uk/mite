import acurl_ng


def create_request(
    method,
    url,
    headers=(),
    cookies=(),
    auth=None,
    data=None,
    cert=None,
):
    # Cookies should be the byte string representation of the cookie
    if isinstance(method, str):
        method = method.encode()
    headers = tuple(h.encode("utf-8") if hasattr(h, "encode") else h for h in headers)
    return acurl_ng.Request(method, url, headers, cookies, auth, data, cert)
