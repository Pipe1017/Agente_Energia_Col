# ============================================================
# Agente Energia Col — Makefile
# ============================================================

COMPOSE     = docker compose -f infra/docker-compose.yml --env-file .env
COMPOSE_DEV = $(COMPOSE) -f infra/docker-compose.dev.yml

.DEFAULT_GOAL := help

.PHONY: help up down dev dev-down infra infra-down \
        logs logs-api logs-airflow ps \
        migrate migration test test-unit \
        shell-api shell-db shell-airflow \
        build dag-list dag-trigger clean

# ------------------------------------------------------------
# Ayuda
# ------------------------------------------------------------
help: ## Mostrar este menú de ayuda
	@echo ""
	@echo "  Agente Energia Col"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ------------------------------------------------------------
# Servicios
# ------------------------------------------------------------
up: ## Levantar todos los servicios (producción)
	$(COMPOSE) up -d

down: ## Detener todos los servicios
	$(COMPOSE) down

dev: ## Levantar en modo desarrollo (hot reload + JupyterLab)
	$(COMPOSE_DEV) up -d

dev-down: ## Detener servicios de desarrollo
	$(COMPOSE_DEV) down

infra: ## Levantar solo infraestructura base (postgres, redis, minio)
	$(COMPOSE) up -d postgres redis minio minio-init

infra-down: ## Detener solo infraestructura base
	$(COMPOSE) stop postgres redis minio

# ------------------------------------------------------------
# Logs y estado
# ------------------------------------------------------------
logs: ## Ver todos los logs en tiempo real
	$(COMPOSE) logs -f

logs-api: ## Ver logs del API
	$(COMPOSE) logs -f api

logs-airflow: ## Ver logs de Airflow (scheduler + worker)
	$(COMPOSE) logs -f airflow-scheduler airflow-worker

ps: ## Estado de todos los servicios
	$(COMPOSE) ps

# ------------------------------------------------------------
# Base de datos
# ------------------------------------------------------------
migrate: ## Ejecutar migraciones Alembic (upgrade head)
	$(COMPOSE) exec api alembic upgrade head

migration: ## Crear nueva migración automática (MSG requerido)
	@test -n "$(MSG)" || (echo "ERROR: usar  make migration MSG='descripcion'" && exit 1)
	$(COMPOSE) exec api alembic revision --autogenerate -m "$(MSG)"

# ------------------------------------------------------------
# Tests
# ------------------------------------------------------------
test: ## Ejecutar todos los tests
	$(COMPOSE_DEV) exec api pytest tests/ -v --tb=short

test-unit: ## Solo tests unitarios
	$(COMPOSE_DEV) exec api pytest tests/unit/ -v

# ------------------------------------------------------------
# Shells de acceso
# ------------------------------------------------------------
shell-api: ## Shell en el contenedor del API
	$(COMPOSE) exec api bash

shell-db: ## Consola PostgreSQL interactiva
	$(COMPOSE) exec postgres psql -U $${POSTGRES_USER} -d $${POSTGRES_DB}

shell-airflow: ## Shell en el scheduler de Airflow
	$(COMPOSE) exec airflow-scheduler bash

# ------------------------------------------------------------
# Airflow DAGs
# ------------------------------------------------------------
dag-list: ## Listar todos los DAGs registrados
	$(COMPOSE) exec airflow-scheduler airflow dags list

dag-trigger: ## Disparar un DAG manualmente  (DAG=nombre_del_dag)
	@test -n "$(DAG)" || (echo "ERROR: usar  make dag-trigger DAG=xm_ingestion" && exit 1)
	$(COMPOSE) exec airflow-scheduler airflow dags trigger $(DAG)

# ------------------------------------------------------------
# Build multi-arquitectura
# ------------------------------------------------------------
build: ## Construir imágenes para amd64 + arm64 (requiere buildx)
	docker buildx build --platform linux/amd64,linux/arm64 \
		-t energia-col/api:latest backend/ --push
	docker buildx build --platform linux/amd64,linux/arm64 \
		-t energia-col/frontend:latest frontend/ --push

# ------------------------------------------------------------
# Limpieza
# ------------------------------------------------------------
clean: ## ⚠️  Eliminar contenedores, redes y VOLÚMENES (borra datos)
	@echo "ADVERTENCIA: esto eliminará todos los datos persistentes."
	@read -p "¿Continuar? [s/N] " confirm && [ "$$confirm" = "s" ]
	$(COMPOSE) down -v --remove-orphans
