"""
Setup of webdriver using wrapper uses spec import for the args,
so this provides a path where they can be imported from
"""


# Current tests don't care about spinning up a real webdriver so
# no need to have real webriver objects like a Proxy
# setting all to True for now
file_detector = True
proxy = True
browser_profile = True
options = True
capabilities = True

mock_paint_times = [
    {"name": "first-paint", "entryType": "paint", "startTime": 537, "duration": 0},
    {
        "name": "first-contentful-paint",
        "entryType": "paint",
        "startTime": 537,
        "duration": 0,
    },
]

mock_performance_times = [
    {
        "name": "https://google.com",
        "entryType": "navigation",
        "startTime": 0,
        "duration": 2000,
        "initiatorType": "navigation",
        "nextHopProtocol": "h2",
        "workerStart": 0,
        "redirectStart": 0,
        "redirectEnd": 0,
        "fetchStart": 8,
        "domainLookupStart": 19,
        "domainLookupEnd": 36,
        "connectStart": 36,
        "connectEnd": 111,
        "secureConnectionStart": 67,
        "requestStart": 112,
        "responseStart": 226,
        "responseEnd": 334,
        "transferSize": 36487,
        "encodedBodySize": 36187,
        "decodedBodySize": 139051,
        "serverTiming": [],
        "workerTiming": [],
        "unloadEventStart": 0,
        "unloadEventEnd": 0,
        "domInteractive": 656,
        "domContentLoadedEventStart": 656,
        "domContentLoadedEventEnd": 807,
        "domComplete": 1967,
        "loadEventStart": 1967,
        "loadEventEnd": 1968,
        "type": "navigate",
        "redirectCount": 0,
    }
]
