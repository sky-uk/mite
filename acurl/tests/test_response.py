import acurl


class MockRawResponse:
    def __init__(self, header):
        self._header = header

    def get_header(self):
        return self._header


def test_response_headers():
    r = acurl.Response(
        "Some Request",
        MockRawResponse(
            [
                b'HTTP/1.1 200 OK\r\n',
                b'Foo: bar\r\n',
                b'Baz: quux\r\n',
                b'Baz: quuz\r\n',
                b'\r\n',
            ]
        ),
        0,
    )
    assert "Foo" in r.headers
    assert r.headers["Foo"] == "bar"
    assert "Baz" in r.headers
    assert r.headers["Baz"] == "quux, quuz"
