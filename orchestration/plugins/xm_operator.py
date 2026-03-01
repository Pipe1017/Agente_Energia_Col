"""
Operador Airflow personalizado para llamadas a la API de XM (pydataxm).

Encapsula la lógica de reintentos, validación de datos y normalización
de DataFrames para uso en DAGs como un operador declarativo.

Uso:
    from plugins.xm_operator import XMDataOperator

    fetch = XMDataOperator(
        task_id="fetch_precio",
        metric="PrecioMercado",
        entity="Sistema",
        lookback_days=2,
        granularity="hourly",
        output_key="spot_prices",
    )
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from airflow.models import BaseOperator
from airflow.utils.decorators import apply_defaults

logger = logging.getLogger(__name__)


class XMDataOperator(BaseOperator):
    """
    Operador para descarga de métricas del mercado eléctrico colombiano desde XM.

    Parameters
    ----------
    metric : str
        Nombre de la métrica XM (ej. "PrecioMercado", "DemandaComercial").
    entity : str
        Entidad de agrupación (ej. "Sistema", "Agente").
    lookback_days : int
        Cuántos días hacia atrás descargar (incluye hoy).
    granularity : str
        "hourly" o "daily" — determina el formato de salida.
    output_key : str
        Clave bajo la cual el resultado se guarda en XCom.
    critical : bool
        Si True, falla el task al no obtener datos.
        Si False, retorna {} silenciosamente (ej. métricas opcionales).
    """

    template_fields = ("metric", "entity", "output_key")
    ui_color = "#f0e68c"

    @apply_defaults
    def __init__(
        self,
        metric: str,
        entity: str = "Sistema",
        lookback_days: int = 2,
        granularity: str = "hourly",
        output_key: str | None = None,
        critical: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.metric = metric
        self.entity = entity
        self.lookback_days = lookback_days
        self.granularity = granularity
        self.output_key = output_key or metric.lower()
        self.critical = critical

        if granularity not in ("hourly", "daily"):
            raise ValueError(f"granularity debe ser 'hourly' o 'daily', no '{granularity}'")

    def execute(self, context: dict) -> dict[str, float]:
        """
        Ejecuta la descarga desde la API de XM.

        Returns
        -------
        dict
            "hourly": {pd.Timestamp→str : valor_float}
            "daily":  {date→str : valor_float}
        """
        import sys
        sys.path.insert(0, "/opt/airflow")
        from dags._utils import xm_df_to_hourly, xm_df_to_daily

        end = date.today()
        start = end - timedelta(days=self.lookback_days)

        logger.info("[XMDataOperator] %s (%s) | %s → %s",
                    self.metric, self.entity, start, end)

        try:
            from pydataxm.pydataxm import ReadDB
            api = ReadDB()
            df = api.request_data(self.metric, self.entity, start, end)
        except Exception as exc:
            msg = f"Error descargando {self.metric} desde XM API: {exc}"
            if self.critical:
                raise RuntimeError(msg) from exc
            logger.warning(msg)
            return {}

        if df is None or df.empty:
            msg = f"{self.metric} retornó datos vacíos"
            if self.critical:
                raise ValueError(msg)
            logger.warning(msg)
            return {}

        # Detectar columna de valor (excluir columnas de índice temporal)
        exclude = {"Date", "Hour", "Values"}
        value_cols = [c for c in df.columns if c not in exclude]
        if not value_cols and "Values" in df.columns:
            value_col = "Values"
        elif value_cols:
            value_col = value_cols[0]
        else:
            raise ValueError(f"No se encontró columna de valor en {self.metric}: {list(df.columns)}")

        if self.granularity == "hourly":
            result = xm_df_to_hourly(df, value_col=value_col)
        else:
            result = xm_df_to_daily(df, value_col=value_col)

        logger.info("[XMDataOperator] %s: %d registros descargados", self.metric, len(result))

        # Serializar para XCom (keys como strings)
        serialized = {str(k): v for k, v in result.items()}

        # Guardar en XCom bajo output_key
        context["ti"].xcom_push(key=self.output_key, value=serialized)
        return serialized


class XMBatchOperator(BaseOperator):
    """
    Descarga múltiples métricas de XM en una sola llamada al operador.
    Útil para reducir el overhead de conexión cuando se necesitan
    varias métricas del mismo período.

    Parameters
    ----------
    metrics_config : list[dict]
        Lista de configuraciones de métricas. Cada dict tiene:
        {"metric": str, "entity": str, "granularity": str, "critical": bool}
    lookback_days : int
        Período de descarga compartido para todas las métricas.
    """

    template_fields: tuple[str, ...] = tuple()
    ui_color = "#87ceeb"

    @apply_defaults
    def __init__(
        self,
        metrics_config: list[dict],
        lookback_days: int = 2,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.metrics_config = metrics_config
        self.lookback_days = lookback_days

    def execute(self, context: dict) -> dict[str, dict]:
        """
        Ejecuta la descarga de todas las métricas configuradas.

        Returns
        -------
        dict
            {"metric_name": {ts_str: value, ...}, ...}
        """
        import sys
        sys.path.insert(0, "/opt/airflow")
        from dags._utils import xm_df_to_hourly, xm_df_to_daily
        from datetime import date, timedelta

        end = date.today()
        start = end - timedelta(days=self.lookback_days)

        from pydataxm.pydataxm import ReadDB
        api = ReadDB()
        results = {}

        for config in self.metrics_config:
            metric = config["metric"]
            entity = config.get("entity", "Sistema")
            granularity = config.get("granularity", "hourly")
            critical = config.get("critical", True)

            try:
                df = api.request_data(metric, entity, start, end)
                if df is None or df.empty:
                    if critical:
                        raise ValueError(f"{metric} retornó vacío")
                    results[metric] = {}
                    continue

                exclude = {"Date", "Hour", "Values"}
                value_cols = [c for c in df.columns if c not in exclude]
                value_col = value_cols[0] if value_cols else "Values"

                raw = xm_df_to_hourly(df, value_col) if granularity == "hourly" \
                    else xm_df_to_daily(df, value_col)

                results[metric] = {str(k): v for k, v in raw.items()}
                logger.info("[XMBatchOperator] %s: %d registros", metric, len(results[metric]))

            except Exception as exc:
                if critical:
                    raise
                logger.warning("[XMBatchOperator] %s falló (no crítico): %s", metric, exc)
                results[metric] = {}

        context["ti"].xcom_push(key="batch_results", value=results)
        return results
