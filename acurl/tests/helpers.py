from unittest.mock import Mock

import acurl


def create_request(
    method, url, headers=(), cookies=(), auth=None, data=None, cert=None, session=None
):
    if session is None:
        session = Mock()
        session.get_cookie_list.return_value = ()
    return acurl.Request(method, url, headers, cookies, auth, data, cert, session)
