# we use a later python and alpine so that the most up to date py3-cryptography can be pulled in
# this stops the requirement for rust be dragged in (causing much "fun" in so far as the image size bloats
# to approx 2Gb!)

FROM python:3.12.14-alpine3.24 AS build

# py3-cryptography is added here as a means to get python cryptography onto the image (prebuilt) and without
# need to install rust compiler
RUN apk add --no-cache gnupg libressl tar ca-certificates gcc cmake make libc-dev coreutils g++ libzmq zeromq zeromq-dev git curl-dev libffi libffi-dev libbz2 bzip2-dev xz-dev libjpeg jpeg-dev py3-cryptography

# Manually upgrade zlib to the latest available version to pick up security fixes
RUN apk upgrade --no-cache zlib

COPY . /mite
WORKDIR /mite

RUN pip wheel --no-cache-dir --wheel-dir /wheels ./acurl
RUN pip wheel --no-cache-dir --wheel-dir /wheels .[all]

FROM python:3.12.14-alpine3.24

# Runtime-only shared libraries for the compiled wheels built in the previous stage.
RUN apk add --no-cache libressl ca-certificates libzmq libffi libbz2 xz libjpeg libcurl py3-cryptography

COPY --from=build /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels acurl mite[all] \
    && rm -rf /wheels

RUN addgroup -S mite && adduser -S mite -G mite
USER mite

WORKDIR /mite
