ARG BASE_IMAGE
FROM ${BASE_IMAGE}

ARG UV_VERSION=0.13.10
RUN dnf install -y libX11 libXext libXrender \
    && dnf clean all \
    && rm -rf /var/cache/dnf

ADD https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-x86_64-unknown-linux-musl.tar.gz /tmp/uv.tar.gz
RUN mkdir -p /tmp/uv-extract \
    && tar -xzf /tmp/uv.tar.gz -C /tmp/uv-extract \
    && find /tmp/uv-extract -type f -name uv -exec cp {} /usr/local/bin/uv \; \
    && chmod +x /usr/local/bin/uv \
    && rm -rf /tmp/uv.tar.gz /tmp/uv-extract \
    && uv --version

WORKDIR /src
COPY pyproject.toml uv.lock .python-version ./
COPY mipi_gui.py gen_sim_case.py sim_flow.py ./
COPY build/linux/common ./build/linux/common
COPY build/linux/rocky-linux8/build-rocky-linux8.sh ./build/linux/rocky-linux8/build-rocky-linux8.sh
RUN chmod +x /src/build/linux/rocky-linux8/build-rocky-linux8.sh /src/build/linux/common/build.sh

CMD ["/src/build/linux/rocky-linux8/build-rocky-linux8.sh"]
