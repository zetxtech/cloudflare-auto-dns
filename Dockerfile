FROM python:3.9

WORKDIR /src
COPY . .

RUN python -m venv /opt/venv \
    && . /opt/venv/bin/activate \
    && pip install --no-cache-dir -U pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

WORKDIR /app
ENV PATH="/opt/venv/bin:$PATH"

ENTRYPOINT ["python", "/src/monitor.py"]
