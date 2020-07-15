"""setup of webdriver using wrapper  uses spec import for the args,

so this provides a path where they can be imported from"""


# Current tests don't care about spinning up a real webdriver so
# no need to have real webriver objects like a Proxy
# setting all to True for now
file_detector = True
proxy = True
browser_profile = True
options = True
capabilities = True
