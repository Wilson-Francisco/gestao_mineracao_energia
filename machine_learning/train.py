import psycopg2
import pandas as pd
import numpy as np
from scipy import stats
import os

def conectar_banco():
    """Conecta ao TimescaleDB local no Docker de forma offline (Fase 1)"""
    return psycopg2.connect(
        host="localhost",
        database="energy_management",
        user="admin",
        password="mineracao_secure_2026",
        port="5432"
    )

def carregar_dados_historicos():
    """Busca o histórico de telemetria bruto gravado pelo Go Server na Fase 4"""
    print("[I.A. - Ingestão] Coletando registros históricos da Hypertable...")
    conn = conectar_banco()
    query = """
        SELECT timestamp, production_q, consumption_w, efficiency_w_spec 
        FROM measurements 
        ORDER BY timestamp ASC;
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # Adiciona a coluna de marcação de Smena com base no horário UTC para a análise futura
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['hora'] = df['timestamp'].dt.hour
    df['smena'] = np.where((df['hora'] >= 8) & (df['hora'] < 20), 'Smena 1', 'Smena 2')
    
    print(f"[I.A. - Ingestão] Sucesso! Total de registros brutos: {len(df)}")
    return df

def aplicar_filtro_grubbs_nativo(df, coluna_alvo, alpha=0.05):
    """
    Algoritmo de Smirnov-Grubbs iterativo conforme exigido pelo ПАКУЭ.
    Detecta e elimina outliers baseando-se na distribuição normal de Gauss.
    """
    print(f"[I.A. - Limpeza] Executando algoritmo de Grubbs na coluna '{coluna_alvo}'...")
    df_limpo = df.copy()
    outliers_detectados = True
    contador_remocoes = 0
    
    while outliers_detectados:
        n = len(df_limpo)
        if n < 3:
            break
            
        valores = df_limpo[coluna_alvo].to_numpy()
        media = np.mean(valores)
        desvio_padrao = np.std(valores, ddof=1)
        
        if desvio_padrao == 0:
            break
            
        distancias = np.abs(valores - media)
        idx_maximo = np.argmax(distancias)
        g_calculado = distancias[idx_maximo] / desvio_padrao
        
        # Cálculo do valor crítico teórico baseado na t de Student
        t_dist = stats.t.ppf(1 - alpha / (2 * n), n - 2)
        numerador = (n - 1) * np.sqrt(t_dist**2)
        denominador = np.sqrt(n) * np.sqrt(n - 2 + t_dist**2)
        g_teorico = numerador / denominador
        
        if g_calculado > g_teorico:
            contador_remocoes += 1
            df_limpo = df_limpo.drop(df_limpo.index[idx_maximo]).reset_index(drop=True)
        else:
            outliers_detectados = False
            
    print(f" -> Filtragem concluída! Outliers removidos em '{coluna_alvo}': {contador_remocoes}")
    return df_limpo

if __name__ == "__main__":
    print("\n" + "="*70)
    print("📊 FASE 5: EXTRAÇÃO DE DADOS E FILTRAGEM DE OUTLIERS DE GAUSS")
    print("="*70)
    
    try:
        df_bruto = carregar_dados_historicos()
        if len(df_bruto) > 0:
            df_filtrado = aplicar_filtro_grubbs_nativo(df_bruto, 'efficiency_w_spec')
            print(f"[Sucesso] Amostra estável finalizada: {len(df_filtrado)} linhas prontas para análise.")
        else:
            print("[Aviso] A Hypertable está vazia. Rode o Go Collector/Server para gerar dados.")
    except Exception as e:
        print(f"[Erro Pipeline] Falha na execução da Parte 2: {e}")