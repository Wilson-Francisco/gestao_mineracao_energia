import psycopg2
import pandas as pd
import numpy as np
import mlflow
import mlflow.sklearn
import os
import time
from datetime import datetime, timedelta, timezone

def conectar_banco():
    """Conecta de forma segura ao banco TimescaleDB local no Docker (Fase 1)"""
    return psycopg2.connect(
        host="localhost",
        database="energy_management",
        user="admin",
        password="mineracao_secure_2026",
        port="5432"
    )

def carregar_modelo_campeao_mlflow():
    """Baixa o modelo da Regressão Linear via MLflow Runs API"""
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

def buscar_novas_medicoes(conn, data_limite):
    """Busca as telemetrias brutas na Hypertable após o ponteiro"""
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
    # Carrega o cérebro preditivo uma única vez ao iniciar o servidor
    modelo_final, nome_modelo_ia = carregar_modelo_campeao_mlflow()
    
    # Ponteiro de tempo inicial: Varre os dados gerados nos últimos 30 minutos
    relogio_ponteiro = datetime.now(timezone.utc) - timedelta(minutes=30)
    
    print("="*75)
    print(f"MOTOR DE ANALYTICS EM EXECUÇÃO CONTÍNUA (CICLO 5s - PADRÃO PDCA)")
    print(f" Monitorando frota BelAZ-75306 com o modelo: {nome_modelo_ia}")
    print("="*75 + "\n")
    
    # =========================================================================
    # LOOP DE EXECUÇÃO EM TEMPO REAL E INSERÇÃO DE ANOMALIAS
    # =========================================================================
    while True:
        try:
            db_conn = conectar_banco()
            novas_linhas = buscar_novas_medicoes(db_conn, relogio_ponteiro)
            
            if len(novas_linhas) > 0:
                colunas = ['timestamp', 'asset_id', 'production_q', 'consumption_w', 'efficiency_w_spec']
                df_lote = pd.DataFrame(novas_linhas, columns=colunas)
                
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Inspecionando lote com {len(df_lote)} novas telemetrias...")
                
                cursor_escrita = db_conn.cursor()
                
                # Varre linha por linha do lote para aplicar a Inteligência Artificial
                for idx, row in df_lote.iterrows():
                    ts = row['timestamp']
                    asset_id = int(row['asset_id'])
                    prod_q = float(row['production_q'])     // [t·km]
                    cons_w = float(row['consumption_w'])    // [t]
                    w_spec_real = float(row['efficiency_w_spec']) // [g/t·km]
                    
                    # Atualiza o ponteiro de tempo para evitar reprocessamento no próximo ciclo
                    if ts.to_pydatetime().replace(tzinfo=timezone.utc) > relogio_ponteiro:
                        relogio_ponteiro = ts.to_pydatetime().replace(tzinfo=timezone.utc)
                    
                    # Prepara a entrada multivariável exata exigida pelo Scikit-Learn [[Q, W]]
                    matriz_entrada = np.array([[prod_q, cons_w]])
                    
                    # A I.A. calcula o consumo específico Alvo/Planejado esperado em [g/t·km]
                    w_spec_planejado = float(modelo_final.predict(matriz_entrada)[0])
                    
                    # Regra de Tolerância do ПАКУЭ: Alvo + 10% de margem aceitável
                    limite_tolerancia = w_spec_planejado * 1.10
                    
                    # Se o caminhão gastou mais diesel do que o limite calculado pela I.A.
                    if w_spec_real > limite_tolerancia:
                        percentual_desvio = ((w_spec_real - w_spec_planejado) / w_spec_planejado) * 100
                        
                        print(f" [DESVIO CRÍTICO] Caminhão BelAZ ID {asset_id} ultrapassou o limite!")
                        print(f"     -> Real: {w_spec_real:.2f} g/t·km | I.A. Alvo: {w_spec_planejado:.2f} g/t·km | Desvio: +{percentual_desvio:.2f}%")
                        
                        # Monta a descrição executiva da falha para salvar no banco
                        descricao_alerta = f"Caminhao operando com {percentual_desvio:.2f}% de sobreconsumo de diesel acima da meta planejada pela Regressao Linear."
                        
                        query_insert_alerta = """
                            INSERT INTO anomaly_alerts (timestamp, asset_id, metric_type, description, severity)
                            VALUES (%s, %s, %s, %s, %s);
                        """
                        # Grava o log com severidade CRITICAL na tabela do Docker
                        cursor_escrita.execute(query_insert_alerta, (
                            ts, asset_id, 'OVER_CONSUMPTION_LINEAR', descricao_alerta, 'CRITICAL'
                        ))
                
                # Processa as somas consolidadas do lote para auditoria no terminal
                consumo_total_lote = float(df_lote['consumption_w'].sum())
                producao_total_lote = float(df_lote['production_q'].sum())
                if producao_total_lote > 0:
                    intensidade_global = (consumo_total_lote * 1000000.0) / producao_total_lote
                    print(f" [Fechamento do Lote] Intensidade Energética Global: {intensidade_global:.4f} g/t·km")
                
                # Força o banco de dados a persistir em disco e salva as alterações
                db_conn.commit()
                cursor_escrita.close()
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Amostra estável. Nenhum desvio de combustível detectado na frota.")
                
            db_conn.close()
        except Exception as error:
            print(f"[Erro Crítico no Loop] Falha de processamento: {error}")
            
        # Janela de atualização cíclica de 5 segundos definida no escopo técnico
        time.sleep(5)
