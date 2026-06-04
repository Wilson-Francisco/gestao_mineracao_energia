import streamlit as st
import psycopg2
import pandas as pd
import numpy as np
import mlflow
import mlflow.sklearn
import matplotlib.pyplot as plt
import seaborn as sns
import time

# 1. Configuração estrita do Layout Web da página do Streamlit
st.set_page_config(
    page_title="ПАКУЭ - Painel de Controle BelAZ-75306",
    page_icon="🚚",
    layout="wide"
)

def conectar_banco():
    """Conecta de forma segura ao banco TimescaleDB local no Docker (Fase 1)"""
    return psycopg2.connect(
        host="localhost", database="energy_management",
        user="admin", password="mineracao_secure_2026", port="5432"
    )

def buscar_dados_brutos(escopo_filtro):
    """Fase 7 Concluída: Filtra e extrai os dados das Views de Turno para os gráficos"""
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
    """Parte 2 Concluída: Busca os KPIs agregados das views do banco"""
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
    """Parte 2 Concluída: Conta as anomalias gravadas no banco"""
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM anomaly_alerts;")
    total = cursor.fetchone()
    cursor.close()
    conn.close()
    return int(total[0]) if total and total[0] is not None else 0

def buscar_tabela_alertas():
    """Parte 4 Concluída: Extrai os últimos 5 logs de alertas"""
    conn = conectar_banco()
    query = "SELECT timestamp, asset_id, metric_type, description, severity FROM anomaly_alerts ORDER BY timestamp DESC LIMIT 5;"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

@st.cache_resource
def carregar_modelo_dashboard_mlflow():
    """Parte 3 Concluída: Baixa o cérebro preditivo diretamente do MLflow"""
    try:
        mlflow.set_tracking_uri("http://localhost:5000")
        run_id_campeao = "3952bcc5c570464fb557f75b64aee39d"
        return mlflow.sklearn.load_model(f"runs:/{run_id_campeao}/modelo_linear_misis")
    except Exception:
        return None

# --- CONSTRUÇÃO DA INTERFACE VISUAL (PADRÃO INTERATIVO ПАКУЭ) ---
st.title("🚚 Sistema ПАКУЭ — Monitoramento Energético BelAZ-75306")
st.markdown("Análise gráfica interativa de indicadores industriais de transporte conforme o padrão regulatório **МИСИС**.")

st.sidebar.header("⚙️ Configurações de Auditoria")
filtro_tempo = st.sidebar.selectbox(
    "Selecione o Escopo de Consolidação:",
    ["Consolidado Diário (Сутки)", "1º Turno (Smena 1 - Diurno)", "2º Turno (Smena 2 - Noturno)"]
)
st.sidebar.markdown("---")

try:
    producao_kpi, consumo_kpi, eficiencia_kpi = buscar_metricas_consolidadas(filtro_tempo)
    total_alertas = buscar_total_alertas_ia()
    modelo_linear = carregar_modelo_dashboard_mlflow()
    dados_planta = buscar_dados_brutos(filtro_tempo)
    df_alertas_logs = buscar_tabela_alertas()
    
    # Renderização dos Cards de KPIs
    st.subheader(f"📊 Indicadores Consolidados: {filtro_tempo.upper()}")
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric(label="TRABALHO DE TRANSPORTE ACUMULADO", value=f"{producao_kpi:,.2f} t·km")
    with col2: st.metric(label="MASSA DE DIESEL CONSUMIDA", value=f"{consumo_kpi:,.4f} t")
    with col3: st.metric(label="CONSUMO ESPECÍFICO REAL", value=f"{eficiencia_kpi:,.2f} g/t·km")
    with col4: st.metric(label="ANOMALIAS CAPTURADAS POR I.A.", value=f"{total_alertas} Eventos")
        
    st.markdown("---")
    
    # -----------------------------------------------------------------
    # SELEÇÃO DINÂMICA DE GRÁFICOS POR ABAS NO TOPO
    # -----------------------------------------------------------------
    st.subheader("📈 Gráfico Analítico de Performance")
    
    # Cria as 3 opções interativas em formato de abas horizontais no topo do gráfico
    aba_especifico, aba_energetico, aba_volume = st.tabs([
        "⚡ Consumo Específico", 
        "🛢️ Consumo Energético", 
        "🏋️ Volume de Trabalho"
    ])
    
    if len(dados_planta) > 0:
        dados_planta['timestamp'] = pd.to_datetime(dados_planta['timestamp'])
        eixo_x_datas = dados_planta['timestamp'].dt.strftime('%d.%m').to_numpy()
        
        Q_bruto = dados_planta['production_q'].to_numpy()
        W_bruto = dados_planta['consumption_w'].to_numpy()
        w_spec_real = dados_planta['efficiency_w_spec'].to_numpy()
        
        # Inferência da I.A. para a linha alvo
        matriz_entrada = dados_planta[['production_q', 'consumption_w']].to_numpy()
        w_spec_predito = modelo_linear.predict(matriz_entrada) if modelo_linear is not None else np.zeros_like(w_spec_real)
        
        sns.set_theme(style="whitegrid")
        
        # --- SELEÇÃO DE VISUALIZAÇÃO BASEADA NO CLIQUE DO USUÁRIO ---
        with aba_especifico:
            fig, ax = plt.subplots(figsize=(11, 4.2))
            ax.plot(eixo_x_datas, w_spec_real, color="#1E90FF", marker='o', linewidth=2, label="Real (Факт)")
            ax.plot(eixo_x_datas, w_spec_predito, color="#FF4500", marker='o', linewidth=2, label="Alvo I.A. (Плановое)")
            ax.set_ylabel("Específico [g/t·km]", fontsize=10)
            ax.set_xlabel("Data do Ciclo (Dia.Mês)", fontsize=10)
            ax.legend(loc="upper right", frameon=True, facecolor="white")
            st.pyplot(fig)
            
        with aba_energetico:
            fig, ax = plt.subplots(figsize=(11, 4.2))
            ax.plot(eixo_x_datas, W_bruto, color="#1E90FF", marker='o', linewidth=2, label="Gasto de Óleo Diesel [t]")
            ax.set_ylabel("Consumo Absoluto [t]", fontsize=10)
            ax.set_xlabel("Data do Ciclo (Dia.Mês)", fontsize=10)
            ax.legend(loc="upper right", frameon=True, facecolor="white")
            st.pyplot(fig)
            
        with aba_volume:
            fig, ax = plt.subplots(figsize=(11, 4.2))
            ax.plot(eixo_x_datas, Q_bruto, color="#1E90FF", marker='o', linewidth=2, label="Trabalho de Transporte (Произв. показатель)")
            ax.axhline(0, color="#FF4500", linestyle='-', linewidth=1.5)
            ax.set_ylabel("Volume Trabalho [t·km]", fontsize=10)
            ax.set_xlabel("Data do Ciclo (Dia.Mês)", fontsize=10)
            ax.legend(loc="upper right", frameon=True, facecolor="white")
            st.pyplot(fig)
    else:
        st.info("Aguardando novas inserções nas Views do banco para iniciar a plotagem.")
        
    st.markdown("---")
    
    # Central de Alertas e Tabela Geral
    b_col1, b_col2 = st.columns(2)
    with b_col1:
        st.subheader("🚨 Central de Alertas Críticos de Ineficiência")
        if len(df_alertas_logs) == 0:
            st.info("Nenhuma anomalia de sobreconsumo registrada pelo modelo de I.A.")
        else:
            for idx, row in df_alertas_logs.iterrows():
                st.error(f"⚠️ **Ativo BelAZ ID: {row['asset_id']}** | {row['timestamp']} | **{row['severity']}**\n\n{row['description']}")
    with b_col2:
        st.subheader("📋 Últimas Telemetrias Recebidas (Visão Geral):")
        st.dataframe(dados_planta.tail(5), use_container_width=True)

    time.sleep(5)
    st.rerun()
    
except Exception as e:
    st.error(f"Erro ao renderizar a central de auditoria gráfica: {e}")
