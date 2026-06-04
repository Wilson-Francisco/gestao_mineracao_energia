import psycopg2
import pandas as pd
import mlflow
import mlflow.sklearn

def conectar_banco():
    """Conecta de forma segura ao banco TimescaleDB local no Docker (Fase 1)"""
    return psycopg2.connect(
        host="localhost", database="energy_management",
        user="admin", password="mineracao_secure_2026", port="5432"
    )

def buscar_dados_brutos(escopo_filtro):
    """Filtra e extrai os dados das Views de Turno para alimentar os gráficos"""
    conn = conectar_banco()
    if escopo_filtro == "1º Turno (Smena 1 - Diurno)":
        query = """
            SELECT periodo_fechamento AS timestamp, total_producao_t_km AS production_q, 
                   total_consumo_t AS consumption_w, consumo_especifico_g_t_km AS efficiency_w_spec 
            FROM v_kpi_primeiro_turno ORDER BY periodo_fechamento DESC LIMIT 30;
        """
    elif escopo_filtro == "2º Turno (Smena 2 - Noturno)":
        query = """
            SELECT periodo_fechamento AS timestamp, total_producao_t_km AS production_q, 
                   total_consumo_t AS consumption_w, consumo_especifico_g_t_km AS efficiency_w_spec 
            FROM v_kpi_segundo_turno ORDER BY periodo_fechamento DESC LIMIT 30;
        """
    else:
        query = """
            SELECT dia_fechamento AS timestamp, total_producao_t_km AS production_q, 
                   total_consumo_t AS consumption_w, consumo_especifico_g_t_km AS efficiency_w_spec 
            FROM v_kpi_diario ORDER BY dia_fechamento DESC LIMIT 30;
        """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df.iloc[::-1].reset_index(drop=True)

def buscar_metricas_consolidadas(escopo_filtro):
    """Busca os KPIs agregados das views do banco para os Cards e Abas"""
    conn = conectar_banco()
    if escopo_filtro == "1º Turno (Smena 1 - Diurno)":
        query = "SELECT SUM(total_producao_t_km), SUM(total_consumo_t) FROM v_kpi_primeiro_turno;"
    elif escopo_filtro == "2º Turno (Smena 2 - Noturno)":
        query = "SELECT SUM(total_producao_t_km), SUM(total_consumo_t) FROM v_kpi_segundo_turno;"
    else:
        query = "SELECT SUM(total_producao_t_km), SUM(total_consumo_t) FROM v_kpi_diario;"
    cursor = conn.cursor()
    cursor.execute(query)
    resultado = cursor.fetchone()
    cursor.close()
    conn.close()
    prod_q = float(resultado[0]) if resultado and resultado[0] is not None else 0.0
    cons_w = float(resultado[1]) if resultado and resultado[1] is not None else 0.0
    w_spec = (cons_w * 1000000.0) / prod_q if prod_q > 0 else 0.0
    return prod_q, cons_w, w_spec

def buscar_total_alertas_ia():
    """Conta a quantidade de anomalias gravadas no banco pela I.A."""
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM anomaly_alerts;")
    total = cursor.fetchone()
    cursor.close()
    conn.close()
    return int(total[0]) if total and total[0] is not None else 0

def buscar_tabela_alertas():
    """Extrai os últimos 5 logs de alertas de sobreconsumo da tabela"""
    conn = conectar_banco()
    query = "SELECT timestamp, asset_id, metric_type, description, severity FROM anomaly_alerts ORDER BY timestamp DESC LIMIT 5;"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def carregar_modelo_dashboard_mlflow():
    """Baixa o cérebro preditivo diretamente do servidor MLflow usando o Run ID"""
    try:
        mlflow.set_tracking_uri("http://localhost:5000")
        run_id_campeao = "3952bcc5c570464fb557f75b64aee39d"
        return mlflow.sklearn.load_model(f"runs:/{run_id_campeao}/modelo_linear_misis")
    except Exception:
        return None