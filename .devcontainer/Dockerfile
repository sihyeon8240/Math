FROM qmcgaw/latexdevcontainer:latest-full@sha256:4211ea058ce0215c441597670d2c7c80cc395d03c09466b340125032cf1da27d

LABEL org.opencontainers.image.description="Mathematics textbook toolchain (TeX Live 2026)"

RUN apt-get update && \
      DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ghostscript \
      libgl1-mesa-glx \
      make \
      python3 \
      python3-yaml \
      ripgrep \
      tree \
      && rm -rf /var/lib/apt/lists/*

COPY scripts/check-environment.sh /workspace/scripts/check-environment.sh
WORKDIR /workspace
RUN lualatex --version | head -n1 | grep -F 'TeX Live 2026' && \
    CHECK_ENVIRONMENT_TOOLS_ONLY=1 ./scripts/check-environment.sh

ENTRYPOINT []
