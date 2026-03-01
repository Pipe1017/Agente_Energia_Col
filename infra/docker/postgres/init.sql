-- ============================================================
-- Agente Energia Col — Inicialización PostgreSQL
-- Ejecutado una sola vez al crear el contenedor
-- ============================================================

-- Base de datos para Airflow (la principal la crea POSTGRES_DB)
CREATE DATABASE airflow;

-- Extensiones en la base de datos principal
\c energia_col;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";   -- UUID generation
CREATE EXTENSION IF NOT EXISTS "pg_trgm";     -- búsqueda de texto eficiente

-- Permisos
GRANT ALL PRIVILEGES ON DATABASE energia_col TO energia_user;
GRANT ALL PRIVILEGES ON DATABASE airflow TO energia_user;
