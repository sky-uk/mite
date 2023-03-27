# we use a later python and alpine so that the most up to date py3-cryptography can be pulled in
# this stops the requirement for rust be dragged in (causing much "fun" in so far as the image size bloats
# to approx 2Gb!)

FROM python:3.11-alpine3.16

# py3-cryptography is added here as a means to get python cryptography onto the image (prebuilt) and without
# need to install rust compiler
RUN apk add --no-cache gnupg libressl tar ca-certificates gcc cmake make libc-dev coreutils g++ libzmq zeromq zeromq-dev git curl-dev libffi libffi-dev libbz2 bzip2-dev xz-dev libjpeg jpeg-dev py3-cryptography

# This little bit of magic caches the dependencies in a docker layer, so that
# rebuilds locally are not so expensive 
COPY acurl/setup.cfg /acurl-setup.cfg
COPY setup.cfg /mite-setup.cfg

RUN python3 -c "import configparser; c = configparser.ConfigParser(); c.read('/mite-setup.cfg'); print(c['options']['install_requires'])" | grep -v acurl | xargs pip install

RUN python3 -c "import configparser; c = configparser.ConfigParser(); c.read('/acurl-setup.cfg'); print(c['options']['install_requires'])" | xargs pip install

ADD . / /mite/

WORKDIR /mite/acurl
RUN pip install --no-cache-dir -e .

WORKDIR /mite
RUN pip install --no-cache-dir -e .[amqp]

# We can't dockerignore the .git directory because we need it for calculating
# the scm-version
RUN rm -r /mite/.git

RUN apk del -r gnupg tar gcc cmake make libc-dev g++ zeromq-dev git
