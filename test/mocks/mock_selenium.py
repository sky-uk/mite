""" This file doesn't actually have 'mocks' as such but because
setup uses spec import, provides an installed path where they can
be imported from"""

# Current tests don't care about spinning up a real webdrive so
# no need to have real webriver objects like a Proxy
# setting all to True for now

file_detector = True
proxy = True
browser_profile = True
options = True
capabilities = True
