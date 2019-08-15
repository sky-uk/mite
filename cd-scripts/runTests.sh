#!/bin/sh

#apt update
#apt list | grep python

cat > script.py <<EOF
import pty
pty.spawn(["su", "-c" "echo 'i am root'"])
EOF
python script.py

# Sort out the broken-ass python
# curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
# python3 get-pip.py --user
# ~/.local/bin/pip install virtualenv
# ~/.local/bin/virtualenv mite-tests
# source mite-tests/bin/activate
# Now the python environment is sane

# pip3 install -r requirements.txt || exit 1
# pip3 install -r dev-requirements.txt || exit 1

# tox; TOX_EXIT_CODE=$?
# coverage html

# flake8; FLAKE8_EXIT_CODE=$?

# Further ideas for jobs to run: license check, black (once we're sure that
# the repo is integration/performance tests, ...

# [ $TOX_EXIT_CODE -eq 0 -a $FLAKE8_EXIT_CODE -eq 0 ] || exit 1
