# Dockerfile
FROM ubuntu:24.04 

WORKDIR /bkp/knowledge

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/bkp/knowledge/venv_knowledge/bin:$PATH"

RUN apt-get update && apt-get install -y \
    python3-full \
    python3-pip \
    python3-venv \
    python3-setuptools \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3 /usr/bin/python

COPY requirements.txt .

RUN python3 -m venv --copies venv_knowledge && \
    . /bkp/knowledge/venv_knowledge/bin/activate && \
    pip install --upgrade pip && \
    pip install --no-cache-dir streamlit>=1.29.0 && \
    pip install --no-cache-dir torch>=2.0.0 && \
    pip install --no-cache-dir transformers>=4.36.0 && \
    pip install --no-cache-dir sentence-transformers>=2.2.2 && \
    pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p transcriptions

COPY start_knowledge.sh /usr/local/bin/start_knowledge.sh
RUN chmod +x /usr/local/bin/start_knowledge.sh

RUN chmod -R 755 /bkp/knowledge/venv_knowledge/bin

EXPOSE 8501

CMD ["/usr/local/bin/start_knowledge.sh"]
