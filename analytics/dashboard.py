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

@st.cache_resource
def carregar_modelo_dashboard_mlflow():
    """Baixa o cérebro preditivo diretamente do servidor MLflow usando o Run ID"""
    try:
        mlflow.set_tracking_uri("http://localhost:5000")
        run_id_campeao = "3952bcc5c570464fb557f75b64aee39d"
        return mlflow.sklearn.load_model(f"runs:/{run_id_campeao}/modelo_linear_misis")
    except Exception:
        return None
    


# =============================================================================
# LAYOUT VISUAL COM ISOLAMENTO DE TELA CONDICIONAL (ПАКУЭ)
# =============================================================================
try:
    # Criação do controle de abas no topo do ecrã para variação dinâmica de modo
 # Usamos st.radio estilizado de forma horizontal para capturar o clique do usuário antes de renderizar os blocos
    st.sidebar.header("⚙️ Configurações de Auditoria")
    filtro_tempo = st.sidebar.selectbox(
        "Selecione o Escopo de Consolidação:",
        ["Consolidado Diário (Сутки)", "1º Turno (Smena 1 - Diurno)", "2º Turno (Smena 2 - Noturno)"]
    )
    st.sidebar.markdown("---")
    st.sidebar.info("💡 Interface integrada a nível de banco com atualizações contínuas.")

    # Injeção do menu horizontal seletor na linha principal do ecrã
    modo_visualizacao = st.radio(
        "📋 Selecione o Painel de Análise Operacional:",
        ["⚡ Consumo Específico", "🛢️ Consumo Energético", "🏋️ Volume de Trabalho", "💰 Relatório Financeiro"],
        horizontal=True
    )
    st.markdown("---")

    # Carga dos dados do banco
    producao_kpi, consumo_kpi, eficiencia_kpi = buscar_metricas_consolidadas(filtro_tempo)
    total_alertas = buscar_total_alertas_ia()
    modelo_linear = carregar_modelo_dashboard_mlflow()
    dados_planta = buscar_dados_brutos(filtro_tempo)
    df_alertas_logs = buscar_tabela_alertas()

    # -----------------------------------------------------------------
    # SE O USUÁRIO CLICAR NO RELATÓRIO FINANCEIRO
    # -----------------------------------------------------------------
    if modo_visualizacao == "💰 Relatório Financeiro":
        # RENDERIZA APENAS E EXCLUSIVAMENTE O RELATÓRIO FINANCEIRO
        st.title("💰 Avaliação da Eficiência em Expressão Financeira")
        st.markdown("Cálculo do impacto Financeiro.")
        
        TARIFA_COMBUSTIVEL = 6.00
        
        # Computação matemática da fórmula
        q_s1, _, w_f1 = buscar_metricas_consolidadas("1º Turno (Smena 1 - Diurno)")
        q_s2, _, w_f2 = buscar_metricas_consolidadas("2º Turno (Smena 2 - Noturno)")
        w_p1, w_p2 = 52.50, 54.00
        
        ganho_s1 = ((w_p1 - w_f1) * q_s1 * TARIFA_COMBUSTIVEL) / 1000000.0
        ganho_s2 = ((w_p2 - w_f2) * q_s2 * TARIFA_COMBUSTIVEL) / 1000000.0
        ganho_total_diario = ganho_s1 + ganho_s2
        
        # Cards Executivos Monetários exclusivos da visão financeira
        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1:
            st.metric(label="BALANÇO FINANCEIRO - 1º TURNO", value=f"R$ {ganho_s1:,.2f}", 
                      delta="Economia (Lucro)" if ganho_s1 >= 0 else "Sobreconsumo (Perda)",
                      delta_color="normal" if ganho_s1 >= 0 else "inverse")
        with f_col2:
            st.metric(label="BALANÇO FINANCEIRO - 2º TURNO", value=f"R$ {ganho_s2:,.2f}", 
                      delta="Economia (Lucro)" if ganho_s2 >= 0 else "Sobreconsumo (Perda)",
                      delta_color="normal" if ganho_s2 >= 0 else "inverse")
        with f_col3:
            st.metric(label="IMPACTO TOTAL CONSOLIDADO (СУТКИ)", value=f"R$ {ganho_total_diario:,.2f}", 
                      delta="Saldo Positivo" if ganho_total_diario >= 0 else "Saldo Negativo",
                      delta_color="off")
        
        st.markdown("---")
        
        # Renderização da tabela oficial no ecrã
        matriz_misis = {
            "Indicador Operacional (ПАКУЭ)": [
                "Consumo Alvo I.A. [w_plan]", "Consumo Real Médio [w_fact]", 
                "Eficiência Diferencial [Δ w]", "Trabalho de Transporte Real [Q]", 
                "Resultado Financeiro do Lote"
            ],
            "1º Turno (Смена 1)": [
                f"{w_p1:.2f} g/t·km", f"{w_f1:.2f} g/t·km", f"{(w_p1 - w_f1):.2f} g/t·km",
                f"{q_s1:,.2f} t·km", f"R$ {ganho_s1:,.2f}"
            ],
            "2º Turno (Смена 2)": [
                f"{w_p2:.2f} g/t·km", f"{w_f2:.2f} g/t·km", f"{(w_p2 - w_f2):.2f} g/t·km",
                f"{q_s2:,.2f} t·km", f"R$ {ganho_s2:,.2f}"
            ]
        }
        st.table(pd.DataFrame(matriz_misis))
        
        if ganho_total_diario >= 0:
            st.success(f"📈 SUCESSO INDUSTRIAL: A operação gerou uma economia líquida de R$ {ganho_total_diario:,.2f} para a mineradora devido à alta eficiência de condução.")
        else:
            st.error(f"📉 ALERTA FINANCEIRO: O desvio operacional resultou em um prejuízo oculto de R$ {abs(ganho_total_diario):,.2f} no custo de combustível.")

    # -----------------------------------------------------------------
    # SE O USUÁRIO CLICAR EM QUALQUER ABA TÉCNICA
    # -----------------------------------------------------------------
    else:
        # EXIBE OS TÍTULOS TÉCNICOS E OS CARDS SUPERIORES QUE VOCÊ MANDOU TIRAR DO FINANCEIRO
        st.subheader(f"📊 Indicadores Consolidados do Camiao: {filtro_tempo.upper()}")
        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric(label="TRABALHO DE TRANSPORTE ACUMULADO", value=f"{producao_kpi:,.2f} t·km")
        with col2: st.metric(label="MASSA DE DIESEL CONSUMIDA", value=f"{consumo_kpi:,.4f} t")
        with col3: st.metric(label="CONSUMO ESPECÍFICO REAL", value=f"{eficiencia_kpi:,.2f} g/t·km")
        with col4: st.metric(label="ANOMALIAS CAPTURADAS POR I.A.", value=f"{total_alertas} Eventos")
            
        st.markdown("---")
        
        if len(dados_planta) > 0:
            dados_planta['timestamp'] = pd.to_datetime(dados_planta['timestamp'])
            eixo_x_datas = dados_planta['timestamp'].dt.strftime('%d.%m').to_numpy()
            
            Q_bruto = dados_planta['production_q'].to_numpy()
            W_bruto = dados_planta['consumption_w'].to_numpy()
            w_spec_real = dados_planta['efficiency_w_spec'].to_numpy()
            
            matriz_entrada = dados_planta[['production_q', 'consumption_w']].to_numpy()
            w_spec_predito = modelo_linear.predict(matriz_entrada) if modelo_linear is not None else np.zeros_like(w_spec_real)
            
            sns.set_theme(style="whitegrid")
            
            # Renderização isolada do gráfico correspondente à seleção
            if modo_visualizacao == "⚡ Consumo Específico":
                st.subheader("📈 Gráfico de Consumo Específico Real vs Linha de Base I.A.")
                fig, ax = plt.subplots(figsize=(11, 4.0))
                ax.plot(eixo_x_datas, w_spec_real, color="#1E90FF", marker='o', linewidth=2, label="Real")
                ax.plot(eixo_x_datas, w_spec_predito, color="#FF4500", marker='o', linewidth=2, label=" I.A Planejado")
                ax.set_ylabel("Específico [g/t·km]", fontsize=10)
                ax.set_xlabel("Data do Ciclo (Dia.Mês)", fontsize=10)
                ax.legend(loc="upper right", frameon=True, facecolor="white")
                st.pyplot(fig)
                
            elif modo_visualizacao == "🛢️ Consumo Energético":
                st.subheader("📈 Gráfico de Gasto Energético Absoluto (Diesel)")
                fig, ax = plt.subplots(figsize=(11, 4.0))
                ax.plot(eixo_x_datas, W_bruto, color="#1E90FF", marker='o', linewidth=2, label="Gasto de Óleo Diesel [t]")
                ax.set_ylabel("Consumo Absoluto [t]", fontsize=10)
                ax.set_xlabel("Data do Ciclo (Dia.Mês)", fontsize=10)
                ax.legend(loc="upper right", frameon=True, facecolor="white")
                st.pyplot(fig)
                
            elif modo_visualizacao == "🏋️ Volume de Trabalho":
                st.subheader("📈 Gráfico de Volume de Trabalho de Transporte Útil")
                fig, ax = plt.subplots(figsize=(11, 4.0))
                ax.plot(eixo_x_datas, Q_bruto, color="#1E90FF", marker='o', linewidth=2, label="Trabalho de Transporte (Volume)")
                ax.axhline(0, color="#FF4500", linestyle='-', linewidth=1.5)
                ax.set_ylabel("Volume Trabalho [t·km]", fontsize=10)
                ax.set_xlabel("Data do Ciclo (Dia.Mês)", fontsize=10)
                ax.legend(loc="upper right", frameon=True, facecolor="white")
                st.pyplot(fig)
        else:
            st.info("Aguardando novas inserções nas Views do banco para iniciar a plotagem.")
            
        st.markdown("---")
        
        # EXIBE A CENTRAL DE ALERTAS E TELEMETRIA APENAS SE NÃO ESTIVER NO MODO FINANCEIRO
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

    # Ciclo contínuo de auto-refresh de 5 segundos comum para ambos os modos
    time.sleep(5)
    st.rerun()

except Exception as e:
    st.error(f"Erro ao renderizar o ecossistema analítico isolado do Dashboard: {e}")

