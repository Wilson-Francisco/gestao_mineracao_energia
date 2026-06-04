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


def calcular_indicadores_forma_gauss(valores):
    """
    Calcula os indicadores inferenciais de forma da curva
    para avaliar a aderência matemática à Lei de Gauss.
    """
    if len(valores) < 3:
        return 0.0, 0.0, 0.0, 0.0

    media = float(np.mean(valores))
    desvio_padrao = float(np.std(valores, ddof=1))
    
    # Assimetria (Skewness): Mede a distorção lateral em relação à curva de Gauss
    assimetria = float(stats.skew(valores))
    
    # Curtose (Kurtosis): Mede o achatamento ou pico da curva do sensor
    curtose = float(stats.kurtosis(valores))
    
    return media, desvio_padrao, assimetria, curtose


if __name__ == "__main__":
    print("\n" + "="*75)
    print("TESTE DOS INDICADORES DE FORMA DE GAUSS")
    print("="*75)
    
    try:
        df_bruto = carregar_dados_historicos()
        if len(df_bruto) > 0:
            df_filtrado = aplicar_filtro_grubbs_nativo(df_bruto, 'efficiency_w_spec')
            
            # Extrai os valores escalares do consumo específico para o teste
            valores_consumo = df_filtrado['efficiency_w_spec'].to_numpy()
            
            # Executa a nova função da Parte 3.1
            mu, sigma, skew, kurt = calcular_indicadores_forma_gauss(valores_consumo)
            
            print(f"\n [Diagnóstico de Gauss] Resultados da Amostra:")
            print(f" -> Média Operacional (μ)             : {mu:.4f} g/t·km")
            print(f" -> Desvio Padrão Amostral (σ)        : {sigma:.4f} g/t·km")
            print(f" -> Coeficiente de Assimetria (Skew)   : {skew:.4f}")
            print(f" -> Coeficiente de Curtose (Kurtosis)  : {kurt:.4f}")
            print("="*75 + "\n")
        else:
            print("[Aviso] Banco de dados vazio. Execute a ingestão em Go.")
    except Exception as e:
        print(f"[Erro] Falha no teste da Parte 3.1: {e}")       