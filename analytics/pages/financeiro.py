import streamlit as st
import psycopg2
import pandas as pd
import numpy as np
st.set_page_config(
    page_title="ПАКУЭ - Análise Financeira",
    page_icon="💰",
    layout="wide"
)

def conectar_banco():
    return psycopg2.connect(
        host="localhost", database="energy_management",
        user="admin", password="mineracao_secure_2026", port="5432"
    )

def extrair_balanco_financeiro_view(view_name):
    """Extrai os dados reais agregados das views do banco para computar o PDCA financeiro"""
    conn = conectar_banco()
    query = f"SELECT SUM(total_producao_t_km), SUM(total_consumo_t) FROM {view_name};"
    cursor = conn.cursor()
    cursor.execute(query)
    res = cursor.fetchone()
    cursor.close()
    conn.close()
    
    prod_q = float(res[0]) if res and res[0] is not np else 0.0
    cons_w = float(res[1]) if res and res[1] is not np else 0.0
    w_fact = (cons_w * 1000000.0) / prod_q if prod_q > 0 else 0.0
    return prod_q, w_fact

st.title("💰 Avaliação da Eficiência em Expressão Financeira")
st.markdown("Cálculo do impacto monetário de economia ou sobreconsumo baseado na fórmula oficial **МИСИС (Fase 7 - Página 48)**.")

# TARIFA FIXADA: R$ 6.00 por unidade de massa de combustível líquido (Diesel)
TARIFA_COMBUSTIVEL = 6.00

try:
    # 1. Extração dos dados agregados por turno de produção real
    q_smena1, w_fact_smena1 = extrair_balanco_financeiro_view("v_kpi_primeiro_turno")
    q_smena2, w_fact_smena2 = extrair_balanco_financeiro_view("v_kpi_segundo_turno")
    
    # 2. Definição das Metas Planejadas pela I.A. (Representando a linha de base estável)
    w_plan_smena1 = 52.5000  # Meta teórica fixada pela regressão linear para o dia
    w_plan_smena2 = 54.0000  # Meta teórica fixada para a noite
    
    # 3. Execução da Equação de Impacto Econômico da Imagem (Convertendo g para toneladas)
    # Economia = (w_plan - w_fact) * Q * Tarifa / 1.000.000 (para alinhar gramas com toneladas)
    ganho_smena1 = ((w_plan_smena1 - w_fact_smena1) * q_smena1 * TARIFA_COMBUSTIVEL) / 1000000.0
    ganho_smena2 = ((w_plan_smena2 - w_fact_smena2) * q_smena2 * TARIFA_COMBUSTIVEL) / 1000000.0
    ganho_total_diario = ganho_smena1 + ganho_smena2

    # --- COMPONENTE VISUAL 1: CARDS EXECUTIVOS ---
    st.subheader("📊 Resultado Econômico do Turno Atual")
    f_col1, f_col2, f_col3 = st.columns(3)
    
    with f_col1:
        st.metric(label="BALANÇO FINANCEIRO - 1º TURNO", value=f"R$ {ganho_smena1:,.2f}", 
                  delta="Economia (Lucro)" if ganho_smena1 >= 0 else "Sobreconsumo (Perda)",
                  delta_color="normal" if ganho_smena1 >= 0 else "inverse")
    with f_col2:
        st.metric(label="BALANÇO FINANCEIRO - 2º TURNO", value=f"R$ {ganho_smena2:,.2f}", 
                  delta="Economia (Lucro)" if ganho_smena2 >= 0 else "Sobreconsumo (Perda)",
                  delta_color="normal" if ganho_smena2 >= 0 else "inverse")
    with f_col3:
        st.metric(label="IMPACTO TOTAL CONSOLIDADO (СУТКИ)", value=f"R$ {ganho_total_diario:,.2f}", 
                  delta="Saldo Positivo" if ganho_total_diario >= 0 else "Saldo Negativo",
                  delta_color="off")

    st.markdown("---")
    
    # --- COMPONENTE VISUAL 2: REPLICAÇÃO EXATA DA TABELA DA UNIVERSIDADE ---
    st.subheader("📋 Matriz de Avaliação de Resultados Tecnológicos e Financeiros")
    
    matriz_misis = {
        "Indicador Operacional": [
            "Consumo Alvo I.A. [w_plan]", 
            "Consumo Real Médio [w_fact]", 
            "Eficiência Diferencial [Δ w]", 
            "Trabalho de Transporte Real [Q]", 
            "Resultado Financeiro Amostral"
        ],
        "1º Turno (Смена 1)": [
            f"{w_plan_smena1:.2f} g/t·km", f"{w_fact_smena1:.2f} g/t·km", f"{(w_plan_smena1 - w_fact_smena1):.2f} g/t·km",
            f"{q_smena1:,.2f} t·km", f"R$ {ganho_smena1:,.2f}"
        ],
        "2º Turno (Смена 2)": [
            f"{w_plan_smena2:.2f} g/t·km", f"{w_fact_smena2:.2f} g/t·km", f"{(w_plan_smena2 - w_fact_smena2):.2f} g/t·km",
            f"{q_smena2:,.2f} t·km", f"R$ {ganho_smena2:,.2f}"
        ]
    }
    
    df_misis = pd.DataFrame(matriz_misis)
    
    # Renderiza a tabela corporativa estilizada ocupando a tela cheia
    st.table(df_misis)
    
    # Destaque visual colorido igual às marcações da imagem enviada
    if ganho_total_diario >= 0:
        st.success(f"📈 SUCESSO INDUSTRIAL: A operação gerou uma economia líquida de R$ {ganho_total_diario:,.2f} para a mineradora devido à alta eficiência de condução da frota.")
    else:
        st.error(f"📉 ALERTA FINANCEIRO: O desvio operacional resultou em um desperdício oculto de R$ {abs(ganho_total_diario):,.2f} no custo de combustível.")

except Exception as e:
    st.error(f"Aguardando novos ciclos de telemetria Go para processamento do balanço financeiro: {e}")
