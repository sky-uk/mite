# TODO: this and the commented lines at the end of the file are for multistage
# builds, which we can use once core platform pull their finger out.
# FROM python:3.7.3-alpine3.9 as base

FROM python:3.7.3

RUN apt-get update
RUN apt-get install -y ca-certificates gcc cmake make libc-dev g++ git libcurl4-openssl-dev

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

RUN apt-get remove -y gcc cmake make libc-dev g++ git libcurl4-openssl-dev

# FROM python:3.7.3-alpine3.9
# COPY --from=base / /
