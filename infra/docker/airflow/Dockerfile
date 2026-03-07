FROM apache/airflow:2.9.3-python3.11

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

USER airflow

# XGBoost 2.x: no arrastra nvidia_nccl_cu12 (293 MB innecesarios en CPU)
# mlflow sin extras GPU, pinned para estabilidad
RUN pip install --no-cache-dir \
    "pydataxm>=0.3" \
    "minio>=7.2" \
    "pandas>=2.0,<3.0" \
    "scikit-learn>=1.3,<1.6" \
    "xgboost>=2.0,<3.0" \
    "mlflow>=2.13,<3.0" \
    "langchain>=0.3" \
    "langchain-openai>=0.2" \
    "langchain-ollama>=0.2" \
    "langchain-core>=0.3" \
    "psycopg2-binary>=2.9"
