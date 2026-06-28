FROM postgres:16-alpine

# Install pgvector extension from local source (avoids network issues during build)
RUN apk add --no-cache --virtual .build-deps \
        build-base clang llvm-dev \
    && mkdir -p /tmp/pgvector

COPY pgvector-0.7.4.tar.gz /tmp/pgvector/
RUN cd /tmp/pgvector \
    && tar xzf pgvector-0.7.4.tar.gz --strip-components=1 \
    && make PG_CONFIG=/usr/local/bin/pg_config OPTFLAGS="" \
    && make install PG_CONFIG=/usr/local/bin/pg_config \
    && apk del .build-deps \
    && rm -rf /tmp/pgvector
