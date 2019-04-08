FROM python:3.7.3-alpine3.9 
RUN set -ex \ 
    && apk add --no-cache gnupg libressl tar ca-certificates gcc cmake make libc-dev coreutils g++ libzmq zeromq zeromq-dev py3-zmq \
    && pip install -v cython msgpack-python ujson

