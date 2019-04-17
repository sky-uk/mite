ARG NANOMSG_BASE_IMAGE
FROM ${NANOMSG_BASE_IMAGE} 
RUN set -ex && apk add --no-cache gcc make libc-dev coreutils g++ libzmq zeromq py3-zmq
RUN pip install -v nanomsg cython msgpack-python ujson

