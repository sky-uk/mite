FROM python:3.7.3-alpine3.9 as base

RUN apk add --no-cache gnupg libressl tar ca-certificates gcc cmake make libc-dev coreutils g++ libzmq zeromq zeromq-dev git curl-dev

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
RUN pip install --no-cache-dir -e .

# We can't dockerignore the .git directory because we need it for calculating
# the scm-version
RUN rm -r /mite/.git

RUN apk del -r gnupg tar gcc cmake make libc-dev g++ zeromq-dev git

FROM python:3.7.3-alpine3.9

COPY --from=base / /
