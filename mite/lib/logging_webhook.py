import logging
from urllib.request import Request as UrlLibRequest
from urllib.request import urlopen

import ujson


def _controller_log_start(scenario_spec, logging_url):
    if not logging_url.endswith("/"):
        logging_url += "/"

    url = logging_url + "start"
    logging.info(f"Logging test start to {url}")
    resp = urlopen(
        UrlLibRequest(
            url,
            data=ujson.dumps(
                {
                    'testname': scenario_spec,
                    # TODO: log other properties as well,
                    # like the endpoint URLs we are
                    # hitting.
                }
            ).encode(),
            method="POST",
        )
    )
    logging.debug("Logging test start complete")
    if resp.status == 200:
        return ujson.loads(resp.read())['newid']
    else:
        logging.warning(
            f"Could not complete test start logging; status was {resp.status_code}"
        )


def _controller_log_end(logging_id, logging_url):
    if logging_id is None:
        return

    if not logging_url.endswith("/"):
        logging_url += "/"

    url = logging_url + "end"
    logging.info(f"Logging test end to {url}")
    resp = urlopen(UrlLibRequest(url, data=ujson.dumps({'id': logging_id}).encode()))
    if resp.status != 204:
        logging.warning(
            f"Could not complete test end logging; status was {resp.status_code}"
        )
    logging.debug("Logging test end complete")


def time_function(scenario_spec, config_manager, start_event, end_event):
    _controller_log_start()
