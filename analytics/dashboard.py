import streamlit as st
import psycopg2
import pandas as pd
import numpy as np

# 1. Configuração estrita do Layout Web da página do Streamlit
st.set_page_config(
    page_title="ПАКУЭ - Painel de Controle BelAZ-75306",
    page_icon=" ",
    layout="wide"
)

def conectar_banco():
    """Conecta de forma segura ao banco TimescaleDB local no Docker"""
    return psycopg2.connect(
        host="localhost",
        database="energy_management",
        user="admin",
        password="mineracao_secure_2026",
        port="5432"
    )

def buscar_dados_brutos():
    """Busca as últimas telemetrias da Hypertable para os gráficos de dispersão"""
    conn = conectar_banco()
    query = """
        SELECT timestamp, production_q, consumption_w, efficiency_w_spec 
        FROM measurements 
        ORDER BY timestamp DESC 
        LIMIT 200;
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df.iloc[::-1].reset_index(drop=True)

# =============================================================================
# EXTRAÇÃO DE INDICADORES CONSOLIDADOS POR TURNO E DIÁRIO
# =============================================================================
def buscar_metricas_consolidadas(escopo_filtro):
    """Mapeia o filtro do painel e extrai os acumulados diretamente das views do banco"""
    conn = conectar_banco()
    
    # Define qual view ler com base na seleção do usuário na tela
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
    
    # Trata valores nulos caso o turno selecionado ainda não tenha dados injetados
    prod_q = float(resultado[0]) if resultado and resultado[0] is not None else 0.0
    cons_w = float(resultado[1]) if resultado and resultado[1] is not None else 0.0
    
    # Calcula a eficiência específica real consolidada do período em [g/t·km]
    w_spec = (cons_w * 1000000.0) / prod_q if prod_q > 0 else 0.0
    return prod_q, cons_w, w_spec

def buscar_total_alertas_ia():
    """Busca o número acumulado de anomalias críticas na tabela de logs"""
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM anomaly_alerts;")
    total = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return int(total)

# --- CONSTRUÇÃO DA INTERFACE VISUAL ---
st.title("Sistema De Monitoramento Energético BelAZ-75306")
st.markdown("Gestão contínua da eficiência e consumo de combustível da frota integrada à Inteligência Artificial")

# Barra lateral (Sidebar) para filtro analítico
st.sidebar.header("Configurações de Auditoria")
filtro_tempo = st.sidebar.selectbox(
    "Selecione o Escopo de Consolidação:",
    ["Consolidado Diário (Сутки)", "1º Turno (Smena 1 - Diurno)", "2º Turno (Smena 2 - Noturno)"]
)
st.sidebar.markdown("---")
st.sidebar.info(" Interface integrada a nível de banco com atualizações contínuas.")

try:
    # Executa as consultas agregadas
    producao_kpi, consumo_kpi, eficiencia_kpi = buscar_metricas_consolidadas(filtro_tempo)
    total_alertas = buscar_total_alertas_ia()
    
    # -----------------------------------------------------------------
    # COMPONENTE VISUAL: RENDERIZAÇÃO DOS CARDS DE MÉTRICAS (KPIs)
    # -----------------------------------------------------------------
    st.subheader(f" Indicadores Consolidados: {filtro_tempo.upper()}")
    
    # Divide a tela do navegador em 4 colunas alinhadas lado a lado
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="TRABALHO DE TRANSPORTE ACUMULADO", 
            value=f"{producao_kpi:,.2f} t·km",
            delta="Fechamento Turno"
        )
        
    with col2:
        st.metric(
            label="MASSA DE DIESEL CONSUMIDA", 
            value=f"{consumo_kpi:,.4f} t",
            delta="Gasto de Massa",
            delta_color="inverse"
        )
        
    with col3:
        st.metric(
            label="CONSUMO ESPECÍFICO REAL", 
            value=f"{eficiencia_kpi:,.2f} g/t·km",
            delta="w = (W * 10⁶) / Q"
        )
        
    with col4:
        status_frota = "Estável" if total_alertas == 0 else "Crítico"
        st.metric(
            label="ANOMALIAS CAPTURADAS POR I.A.", 
            value=f"{total_alertas} Eventos",
            delta=f"Status da Frota: {status_frota}",
            delta_color="off" if total_alertas == 0 else "inverse"
        )
        
    st.markdown("---")
    
    # Exibe a tabela bruta de telemetria logo abaixo para auditoria visual
    st.subheader("Últimas Telemetrias Recebidas (Visão Geral):")
    dados_brutos = buscar_dados_brutos()
    st.dataframe(dados_brutos.tail(5), use_container_width=True)
    
except Exception as e:
    st.error(f"Erro ao carregar os cards analíticos de turnos: {e}")
