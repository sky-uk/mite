ARG MITE_DEPENDENCIES_BASE_IMAGE
FROM ${MITE_DEPENDENCIES_BASE_IMAGE}
RUN set -ex \
    && apk add --no-cache curl-dev \
    && pip install -v https://github.com/tonysimpson/acurl/archive/master.zip
