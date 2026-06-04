import psycopg2
import pandas as pd
import numpy as np
import mlflow
import mlflow.sklearn
import os
import time
from datetime import datetime, timedelta, timezone

def conectar_banco():
    """Conecta de forma segura ao banco TimescaleDB local no Docker"""
    return psycopg2.connect(
        host="localhost",
        database="energy_management",
        user="admin",
        password="mineracao_secure_2026",
        port="5432"
    )

def carregar_modelo_campeao_mlflow():
    """Parte 1 Concluída: Baixa o modelo da Regressão Linear via MLflow Runs API"""
    print("\n" + "="*75)
    print("ENGINE ANALYTICS: CONEXÃO E DOWNLOAD VIA MLFLOW RUNS API")
    print("="*75)
    try:
        mlflow.set_tracking_uri("http://localhost:5000")
        run_id_campeao = "3952bcc5c570464fb557f75b64aee39d"
        nome_artefato = "modelo_linear_misis"
        model_uri = f"runs:/{run_id_campeao}/{nome_artefato}"
        print(f" -> Requisitando artefatos em: {model_uri}")
        modelo_carregado = mlflow.sklearn.load_model(model_uri)
        print(f"MODELO CAMPEÃO INTEGRADO COM SUCESSO EM PRODUÇÃO!")
        print("="*75 + "\n")
        return modelo_carregado, "Regressao_Linear_MISIS"
    except Exception as e:
        print(f" [Erro MLOps] Falha ao baixar modelo do servidor MLflow: {e}")
        return None, None

# =============================================================================
# INGESTÃO DE FLUXO CONTÍNUO E CÁLCULO DE KPIs OPERACIONAIS
# =============================================================================
def buscar_novas_medicoes(conn, data_limite):
    """Busca as telemetrias brutas gravadas na Hypertable após o ponteiro de tempo atual"""
    cursor = conn.cursor()
    query = """
        SELECT timestamp, asset_id, production_q, consumption_w, efficiency_w_spec 
        FROM measurements 
        WHERE timestamp > %s
        ORDER BY timestamp ASC;
    """
    cursor.execute(query, (data_limite,))
    registros = cursor.fetchall()
    cursor.close()
    return registros

if __name__ == "__main__":
    modelo_final, nome_modelo_ia = carregar_modelo_campeao_mlflow()
    
    # Ponteiro de tempo inicial: Começa varrendo os dados gerados nos últimos 15 minutos
    relogio_ponteiro = datetime.now(timezone.utc) - timedelta(minutes=15)
    
    print("="*75)
    print(f"MOTOR DE ANALYTICS: AGREGADOR DE KPIs OPERACIONAIS EM EXECUÇÃO")
    print("="*75 + "\n")
    
    try:
        db_conn = conectar_banco()
        novas_linhas = buscar_novas_medicoes(db_conn, relogio_ponteiro)
        
        if len(novas_linhas) > 0:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Lote capturado: Convertendo {len(novas_linhas)} linhas para Pandas...")
            
            # Converte a tupla de banco em um DataFrame Pandas estruturado para os cálculos de KPIs
            colunas = ['timestamp', 'asset_id', 'production_q', 'consumption_w', 'efficiency_w_spec']
            df_lote = pd.DataFrame(novas_linhas, columns=colunas)
            
            # Atualiza o ponteiro de tempo com o carimbo do último registro processado
            df_lote['timestamp'] = pd.to_datetime(df_lote['timestamp'])
            relogio_ponteiro = df_lote['timestamp'].max()
            
            # --- CÁLCULO DO KPI DE COMPORTAMENTO GLOBAL DO LOTE ---
            consumo_total_lote = float(df_lote['consumption_w'].sum())   # Soma da massa de diesel [t]
            producao_total_lote = float(df_lote['production_q'].sum())   # Soma do trabalho útil [t·km]
            
            if producao_total_lote > 0:
                # Fórmula do manual: Intensidade Energética Global do lote em [g/t·km]
                intensidade_global_lote = (consumo_total_lote * 1000000.0) / producao_total_lote
                
                print(f"[KPI DE COMPORTAMENTO GLOBAL DO LOTE]")
                print(f"   -> Trabalho de Transporte Total : {producao_total_lote:.2f} t·km")
                print(f"   -> Massa de Diesel Consumida    : {consumo_total_lote:.6f} t")
                print(f"   -> Intensidade Energética Lote  : {intensidade_global_lote:.4f} g/t·km")
            else:
                print("   -> [Aviso] Lote composto apenas por caminhões rodando em vazio (Produção útil = 0).")
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Amostra estável. Sem novas telemetrias na Hypertable.")
            
        db_conn.close()
    except Exception as error:
        print(f"[Erro Analytics] Falha de processamento analítico na Parte 2: {error}")
