FROM debian:bookworm-slim@sha256:7c7b2c966bc9ee8cedfeef67e0e279108992c77681fa595db4a9d65c06ccc587 AS build
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl build-essential perl && rm -rf /var/lib/apt/lists/*
WORKDIR /build
RUN curl --fail --location --retry 3 https://github.com/openssl/openssl/releases/download/openssl-3.5.9/openssl-3.5.9.tar.gz -o openssl.tar.gz && echo '603f5602e2eef00d77fbd429d34dcd5822bb301757a1bc9cdb24c670f1eb859a  openssl.tar.gz' | sha256sum -c - && tar xzf openssl.tar.gz
WORKDIR /build/openssl-3.5.9
RUN ./Configure --prefix=/opt/openssl --openssldir=/opt/openssl/ssl no-tests no-shared && make -j4 && make install_sw
RUN mkdir -p /opt/openssl/ssl && cp apps/openssl.cnf /opt/openssl/ssl/openssl.cnf
COPY fixture/server.c fixture/probe.c /build/
RUN gcc -std=c11 -Wall -Wextra -Werror -O2 -fstack-protector-strong -D_FORTIFY_SOURCE=2 -I/opt/openssl/include /build/server.c -L/opt/openssl/lib64 -lssl -lcrypto -ldl -pthread -o /opt/openssl/bin/invaris-server && gcc -std=c11 -Wall -Wextra -Werror -O2 -fstack-protector-strong -D_FORTIFY_SOURCE=2 -I/opt/openssl/include /build/probe.c -L/opt/openssl/lib64 -lssl -lcrypto -ldl -pthread -o /opt/openssl/bin/invaris-probe
FROM debian:bookworm-slim@sha256:7c7b2c966bc9ee8cedfeef67e0e279108992c77681fa595db4a9d65c06ccc587
RUN apt-get update && apt-get install -y --no-install-recommends python3 ca-certificates && rm -rf /var/lib/apt/lists/* && useradd --uid 10001 --no-create-home fixture
COPY --from=build /opt/openssl /opt/openssl
COPY --from=build /build/openssl-3.5.9/LICENSE.txt /usr/share/doc/invaris/openssl-LICENSE.txt
COPY fixture/control.py /opt/invaris/control.py
ENV PATH=/opt/openssl/bin:$PATH
USER 10001:10001
WORKDIR /work
ENTRYPOINT ["python3", "/opt/invaris/control.py"]
CMD ["serve"]
