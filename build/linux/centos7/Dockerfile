ARG BASE_IMAGE
FROM ${BASE_IMAGE}

RUN yum install -y libX11 libXext libXrender \
    && yum clean all \
    && rm -rf /var/cache/yum

ADD https://github.com/astral-sh/uv/releases/download/0.13.10/uv-x86_64-unknown-linux-musl.tar.gz /tmp/uv.tar.gz
RUN ls -l /tmp/uv.tar.gz \
    && mkdir -p /tmp/uv-extract \
    && tar -tzf /tmp/uv.tar.gz \
    && tar -xzf /tmp/uv.tar.gz -C /tmp/uv-extract \
    && uvbin="$(find /tmp/uv-extract \( -type f -o -type l \) -name uv -print -quit)" \
    && test -n "${uvbin}" \
    && cp -f "${uvbin}" /usr/local/bin/uv \
    && chmod 755 /usr/local/bin/uv \
    && if command -v uv >/dev/null 2>&1; then cp -f /usr/local/bin/uv "$(command -v uv)"; fi \
    && rm -rf /tmp/uv.tar.gz /tmp/uv-extract \
    && /usr/local/bin/uv --version \
    && /usr/local/bin/uv --version | grep -F "uv 0.13.10" \
    && /usr/local/bin/uv --version | grep -F "musl"

ENV PATH="/usr/local/bin:${PATH}"

WORKDIR /src
COPY pyproject.toml uv.lock .python-version ./
COPY mipi_gui.py gen_sim_case.py sim_flow.py sim_top_gen.py ./
COPY templates/rffe_base.v ./templates/rffe_base.v
COPY build/linux/common ./build/linux/common
COPY build/linux/centos7/build-centos7.sh ./build/linux/centos7/build-centos7.sh
RUN chmod +x /src/build/linux/centos7/build-centos7.sh /src/build/linux/common/build.sh

CMD ["/src/build/linux/centos7/build-centos7.sh"]
