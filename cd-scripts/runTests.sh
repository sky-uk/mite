#!/bin/sh

# Stolen from https://github.com/sky-uk/core-platform/blob/c33c0edd0dab0b529ba49abc672c7c3e1fe607c0/core-jenkins-slave/Dockerfile#L32
curl -L https://github.com/pyenv/pyenv-installer/raw/master/bin/pyenv-installer | bash
export PATH="/home/jenkins/.pyenv/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"
pyenv install 3.7.4

pyenv shell 3.7.4

which python3.7

which pip

pip --version

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
