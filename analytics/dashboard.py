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
    """Conecta de forma segura ao banco TimescaleDB local no Docker"""
    return psycopg2.connect(
        host="localhost", database="energy_management",
        user="admin", password="mineracao_secure_2026", port="5432"
    )

def buscar_dados_brutos(escopo_filtro):
    """
    CORREÇÃO DE SINCRONISMO: Altera dinamicamente a origem dos dados dos gráficos 
    apontando para as Views de Turnos 1, 2 ou Diário conforme a seleção na tela.
    """
    conn = conectar_banco()
    
    if escopo_filtro == "1º Turno (Smena 1 - Diurno)":
        query = """
            SELECT periodo_fechamento AS timestamp, total_producao_t_km AS production_q, 
                   total_consumo_t AS consumption_w, consumo_especifico_g_t_km AS efficiency_w_spec 
            FROM v_kpi_primeiro_turno 
            ORDER BY periodo_fechamento DESC LIMIT 30;
        """
    elif escopo_filtro == "2º Turno (Smena 2 - Noturno)":
        query = """
            SELECT periodo_fechamento AS timestamp, total_producao_t_km AS production_q, 
                   total_consumo_t AS consumption_w, consumo_especifico_g_t_km AS efficiency_w_spec 
            FROM v_kpi_segundo_turno 
            ORDER BY periodo_fechamento DESC LIMIT 30;
        """
    else:
        query = """
            SELECT dia_fechamento AS timestamp, total_producao_t_km AS production_q, 
                   total_consumo_t AS consumption_w, consumo_especifico_g_t_km AS efficiency_w_spec 
            FROM v_kpi_diario 
            ORDER BY dia_fechamento DESC LIMIT 30;
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
    """Conta as anomalias gravadas no banco de forma bruta"""
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM anomaly_alerts;")
    total = cursor.fetchone()
    cursor.close()
    conn.close()
    return int(total[0]) if total and total[0] is not None else 0

def buscar_tabela_alertas():
    """Extrai os últimos 5 logs de alertas disparados pela IA"""
    conn = conectar_banco()
    query = """
        SELECT timestamp, asset_id, metric_type, description, severity 
        FROM anomaly_alerts 
        ORDER BY timestamp DESC 
        LIMIT 5;
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

@st.cache_resource
def carregar_modelo_dashboard_mlflow():
    """Baixa o cérebro preditivo diretamente do MLflow"""
    try:
        mlflow.set_tracking_uri("http://localhost:5000")
        run_id_campeao = "3952bcc5c570464fb557f75b64aee39d"
        model_uri = f"runs:/{run_id_campeao}/modelo_linear_misis"
        return mlflow.sklearn.load_model(model_uri)
    except Exception as e:
        return None

# --- CONSTRUÇÃO DA INTERFACE VISUAL COMPLETA (FADRÃO ПАКУЭ) ---
st.title("🚚 Sistema De Monitoramento Energético BelAZ-75306")
st.markdown("Gestão contínua da eficiência e consumo de combustível da frota integrada à Inteligência Artificial da universidade **МИСИС**.")

# Barra lateral de filtros
st.sidebar.header("⚙️ Configurações de Auditoria")
filtro_tempo = st.sidebar.selectbox(
    "Selecione o Escopo de Consolidação:",
    ["Consolidado Diário (Сутки)", "1º Turno (Smena 1 - Diurno)", "2º Turno (Smena 2 - Noturno)"]
)
st.sidebar.markdown("---")
st.sidebar.info("💡 Interface integrada a nível de banco com atualizações contínuas.")

try:
    # Carga de dados analíticos
    producao_kpi, consumo_kpi, eficiencia_kpi = buscar_metricas_consolidadas(filtro_tempo)
    total_alertas = buscar_total_alertas_ia()
    modelo_linear = carregar_modelo_dashboard_mlflow()
    dados_planta = buscar_dados_brutos(filtro_tempo)
    df_alertas_logs = buscar_tabela_alertas()
    
    # Renderização dos Cards de KPIs (Parte 2)
    st.subheader(f"📊 Indicadores Consolidados: {filtro_tempo.upper()}")
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric(label="TRABALHO DE TRANSPORTE ACUMULADO", value=f"{producao_kpi:,.2f} t·km", delta="Fechamento Turno")
    with col2: st.metric(label="MASSA DE DIESEL CONSUMIDA", value=f"{consumo_kpi:,.4f} t", delta="Gasto de Massa", delta_color="inverse")
    with col3: st.metric(label="CONSUMO ESPECÍFICO REAL", value=f"{eficiencia_kpi:,.2f} g/t·km", delta="w = (W * 10⁶) / Q")
    with col4:
        status_frota = "Estável" if total_alertas == 0 else "Crítico"
        st.metric(label="ANOMALIAS CAPTURADAS POR I.A.", value=f"{total_alertas} Eventos", delta=f"Status: {status_frota}", delta_color="off" if total_alertas == 0 else "inverse")
        
    st.markdown("---")
    
    # -----------------------------------------------------------------
    # GRÁFICOS REFORMULADOS: COMPARAÇÃO TEMPORAL DIÁRIA (CONFORME IMAGEM)
    # -----------------------------------------------------------------
    st.subheader("📈 Análise de Eficiência: Histórico de Consumo Específico")
    
    # Processamento de Vetores Analíticos
    dados_planta['timestamp'] = pd.to_datetime(dados_planta['timestamp'])
    # Formata a data para exibir apenas o dia/mês no eixo X (ex: 04.06) conforme a imagem enviada
    eixo_x_datas = dados_planta['timestamp'].dt.strftime('%d.%m').to_numpy()
    
    w_spec_real = dados_planta['efficiency_w_spec'].to_numpy()
    
    # Inferência da Inteligência Artificial para gerar o consumo alvo/esperado
    matriz_entrada = dados_planta[['production_q', 'consumption_w']].to_numpy()
    w_spec_predito = modelo_linear.predict(matriz_entrada) if modelo_linear is not None else np.zeros_like(w_spec_real)
    
    # Configura o estilo limpo de plotagem do Seaborn
    sns.set_theme(style="whitegrid")
    g_col1, g_col2 = st.columns(2)
    
    with g_col1:
        st.markdown("**Gráfico de Acompanhamento Temporal (Padrão ПАКУЭ)**")
        fig1, ax1 = plt.subplots(figsize=(6, 3.5))
        
        # 1. Linha do Consumo Específico Real (Azul) - "Факт"
        ax1.plot(eixo_x_datas, w_spec_real, color="#1E90FF", marker='o', linewidth=2, label="Real (Факт)")
        
        # 2. Linha do Consumo Específico Esperado pela I.A. (Vermelho) - "Ожидаемое"
        ax1.plot(eixo_x_datas, w_spec_predito, color="#FF4500", marker='o', linewidth=2, label="Planejado I.A. (Ожидаемое)")
        
        # Preenchimento translúcido sob as curvas igual ao modelo da imagem enviada
        ax1.fill_between(eixo_x_datas, w_spec_real, color="#1E90FF", alpha=0.1)
        ax1.fill_between(eixo_x_datas, w_spec_predito, color="#FF4500", alpha=0.05)
        
        ax1.set_xlabel("Data do Turno")
        ax1.set_ylabel("Consumo Específico w (g/t·km)")
        ax1.legend(loc="upper right")
        plt.xticks(rotation=30, ha='right') # Inclina as datas do eixo X para melhor legibilidade
        st.pyplot(fig1)
        
    with g_col2:
        st.markdown("**Gráfico de Correlação e Linha de Base**")
        fig2, ax2 = plt.subplots(figsize=(6, 3.5))
        Q_real = dados_planta['production_q'].to_numpy()
        indices_ordenados = np.argsort(Q_real)
        
        sns.scatterplot(x=Q_real, y=w_spec_real, color="dimgray", alpha=0.4, label="Medição Real", ax=ax2)
        sns.lineplot(x=Q_real[indices_ordenados], y=w_spec_predito[indices_ordenados], color="indigo", linewidth=2.5, label="Meta Planejada (МИСИС)", ax=ax2)
        ax2.set_xlabel("Trabalho de Transporte Q (t·km)")
        ax2.set_ylabel("Consumo Específico Planejado w (g/t·km)")
        ax2.legend()
        st.pyplot(fig2)
        
    st.markdown("---")
    
    # Central de Alertas Visuais & Visão Geral (Parte 4)
    b_col1, b_col2 = st.columns(2)
    with b_col1:
        st.subheader("🚨 Central de Alertas Críticos de Ineficiência")
        if len(df_alertas_logs) == 0:
            st.info("Nenhuma anomalia de sobreconsumo registrada pelo modelo de I.A. nas últimas operações.")
        else:
            for idx, row in df_alertas_logs.iterrows():
                st.error(f"⚠️ **Ativo BelAZ ID: {row['asset_id']}** | {row['timestamp']} | **{row['severity']}**\n\n{row['description']}")
                
    with b_col2:
        st.subheader("📋 Últimas Telemetrias Recebidas (Visão Geral):")
        st.dataframe(dados_planta.tail(5), use_container_width=True)

    # Sistema de atualização automática de tela a cada 5 segundos
    time.sleep(5)
    st.rerun()
    
except Exception as e:
    st.error(f"Erro ao renderizar a central de auditoria e alertas: {e}")
