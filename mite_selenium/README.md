# mite_selenium

Selenium WebDriver integration for mite: installs a remote WebDriver session
onto the journey context and reports page-load timing metrics automatically.

Install: `pip install mite[selenium]`

`wire=True` (request capture via `selenium-wire`) does not work on a stock
install today. A `blinker` version conflict with mite's own `flask` pin. See
the full documentation for details before relying on it.

Full documentation:
https://github.com/sky-uk/mite/blob/master/docs/plugins/selenium.md
</content>
