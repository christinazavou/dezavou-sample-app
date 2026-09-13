# ------------------------------GLOBAL ARGS-------------------------------
# ------------------------------------------------------------------------
ARG PYTHON_VERSION=3.12

# ------------------------------BUILD STAGE-------------------------------
# ------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS builder

# Install security updates to avoid known vulnerabilities in the base image.
RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

# Pin the package manager version to make image builds reproducible.
# Don't keep downloaded uv package files (--no-cache-dir) to reduce the size of the intermediate image; 
# if speed is more important, remove the flag.
ARG UV_VERSION=0.12.13
RUN python -m pip install --no-cache-dir "uv==${UV_VERSION}"

# Create a Python virtual environment that will be copied into the runtime image.
ENV VIRTUAL_ENV=/opt/venv
RUN uv venv "${VIRTUAL_ENV}"

# Copy dependencies before source code; to reuse docker layers as much as possible 
# (when dependencies haven't changed). Note that README.md is referenced in pyproject.toml
WORKDIR /build
COPY pyproject.toml README.md ./


# Install production only dependencies. Note that to run this python app, there's no need to build any package.
# Just install the dependencies in a virtual environment, copy it to the runtime image, and run the app.
RUN uv pip compile pyproject.toml \
	--no-header \
	--no-annotate \
	--output-file /tmp/requirements.txt
RUN uv pip install \
    --python "${VIRTUAL_ENV}/bin/python" \
	--requirement /tmp/requirements.txt


# ------------------------------RUNTIME STAGE-----------------------------
# ------------------------------------------------------------------------
# In the runtime image uv, pip, build metadata, and compiler tools are excluded.
FROM python:${PYTHON_VERSION}-slim AS runtime

# Provide defaults consumed by main.py, that are overridable at docker runtime.
# PYTHONDONTWRITEBYTECODE is added to avoid writing .pyc files to disk;
# PYTHONUNBUFFERED is added to avoid buffering stdout/stderr.
ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1 \
	PATH="/opt/venv/bin:${PATH}" \
	HOST=0.0.0.0 \
	PORT=8000 \
	DEV_MODE=false

# Create an unprivileged Linux user (named "app-runner") to run the application. 
# Use fixed UID/GID (both as "10001") to avoid collisions with other users in the container.
RUN groupadd --system --gid 10001 app-runner \
	&& useradd --system --uid 10001 --gid app-runner --create-home --home-dir /home/app-runner app-runner


# Copy the minimal requirements from the builder stage (i.e. virtual env), performing the command as "app" user, 
# and giving ownership of the folder to that user.
COPY --from=builder --chown=app-runner:app-runner /opt/venv /opt/venv
# Use the home directory of the unprivileged user as the working directory, and copy source code into it.
WORKDIR /app
COPY --chown=app-runner:app-runner main.py ./main.py

# Expose the port on which the application listens.
EXPOSE 8000

# Probe to orchestrators a health signal from the application every 30 seconds.
HEALTHCHECK \
    --interval=30s --timeout=5s --start-period=10s --retries=3 \
	CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"


# Drop privileges before starting the service for security reasons.
USER app-runner
CMD ["python", "main.py"]
