# Image de compilation Meb — construite une fois par architecture puis
# réutilisée grâce au cache de layers Docker. Contrairement à un simple
# `docker run ... apt-get install ...`, un `docker build` met en cache
# chaque étape : tant que ce Dockerfile ne change pas, les apt-get/pip ne
# sont RE-exécutés qu'une fois par machine et par architecture, pas à
# chaque compilation.
FROM python:3.13-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CCACHE_DIR=/root/.ccache \
    PATH="/usr/lib/ccache:${PATH}"

RUN apt-get update -qq \
    && apt-get install -y -qq --no-install-recommends \
        build-essential ccache patchelf gcc ca-certificates git \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /usr/lib/ccache \
    && for tool in gcc cc g++ c++; do ln -sf /usr/bin/ccache "/usr/lib/ccache/$tool"; done

# nuitka[onefile] embarque zstandard -> --onefile compresse correctement
# (sans ça Nuitka retombe sur un mode non compressé, plus lent à créer).
RUN pip install --no-cache-dir --upgrade pip uv "nuitka[onefile]"

WORKDIR /workspace
