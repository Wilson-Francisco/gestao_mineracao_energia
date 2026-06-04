import streamlit as st
import psycopg2 
import pandas as pd
import numpy as np
import time

# 1. Configuração estrita do Layout Web da página do Streamlit
st.set_page_config(
    page_title="ПАКУЭ - Painel de Controle BelAZ-75306",
    page_icon=" ",
    layout="wide"  # Força os painéis e tabelas a ocuparem a tela cheia do navegador
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

# --- CONSTRUÇÃO DA INTERFACE VISUAL ---
st.title("Sistema ПАКУЭ — Monitoramento Energético BelAZ-75306")
st.markdown("Gestão contínua da eficiência e consumo de combustível da frota integrada à Inteligência Artificial.")

# Barra lateral (Sidebar) para filtro analítico de turnos operacionais
st.sidebar.header("Configurações de Auditoria")
filtro_tempo = st.sidebar.selectbox(
    "Selecione o Escopo de Consolidação:",
    ["Consolidado Diário (Сутки)", "1º Turno (Smena 1 - Diurno)", "2º Turno (Smena 2 - Noturno)"]
)

st.sidebar.markdown("---")
st.sidebar.info("Interface com atualização automática contínua sincronizada a cada 5 segundos com a Hypertable.")

# Teste básico de leitura para verificar se a estrutura web renderiza dados
try:
    df_teste = buscar_dados_brutos()
    st.success(f"Conexão ativa! {len(df_teste)} telemetrias localizadas em tempo real no TimescaleDB.")
except Exception as e:
    st.error(f"Falha ao conectar interface com a Hypertable: {e}")
