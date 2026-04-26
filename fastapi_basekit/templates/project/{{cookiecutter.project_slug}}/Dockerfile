FROM python:{{ cookiecutter.python_version }}-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

{% if cookiecutter.server == "gunicorn" -%}
CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000", "--workers", "4"]
{%- else -%}
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
{%- endif %}
