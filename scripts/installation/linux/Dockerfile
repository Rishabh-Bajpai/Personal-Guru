FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies for building
# Using Ubuntu 22.04 builds binary compatible with Ubuntu 22.04+ (GLIBC 2.35)
RUN apt-get update && apt-get install -y \
    software-properties-common \
    build-essential \
    wget \
    file \
    fuse \
    libfuse2 \
    gpg-agent \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    git \
    pkg-config \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
    libavfilter-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python 3.11 via deadsnakes PPA
RUN add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y python3.11 python3.11-venv python3.11-dev python3-pip && \
    rm -rf /var/lib/apt/lists/*

# Alias python3 to python3.11
RUN rm -f /usr/bin/python3 && ln -s /usr/bin/python3.11 /usr/bin/python3

WORKDIR /app

# We expect the project to be mounted at /app
# The build script will be run from here
CMD ["/app/scripts/installation/linux/build_appimage.sh"]
