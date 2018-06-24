FROM python:3.6-alpine

# dns模块使用ares
ENV GEVENT_RESOLVER = 'ares'

WORKDIR /app/src


COPY ./requirements /app/requirements
RUN apk add --no-cache --virtual .build-deps g++ \
    && pip3 install --no-cache-dir -r /app/requirements/production.txt


#    && apk add --no-cache libstdc++
#ADD requirements /app/requirements

#RUN apk add --no-cache --virtual .build-deps \
#      mariadb-dev curl-dev build-base \
#      && export PYCURL_SSL_LIBRARY=openssl \
#      && pip3 install --no-cache-dir -r /app/requirements/production.txt \
#      && apk del .build-deps
#RUN apk add --no-cache mariadb-client-libs libcurl

#ADD docker /app/docker
COPY . /app

