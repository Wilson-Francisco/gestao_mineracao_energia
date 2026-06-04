import psycopg2
import pandas as pd
import numpy as np
import mlflow
import mlflow.sklearn
import os
import time
from datetime import datetime, timedelta, timezone

def carregar_modelo_campeao_mlflow():
    """
    Corrigida: Utiliza o padrão estrito de URI com barra única (runs:/)
    exigido pelo ecossistema MLflow para baixar os pesos da Regressão Linear.
    """
    print("\n" + "="*75)
    print("ENGINE ANALYTICS: CONEXÃO E DOWNLOAD VIA MLFLOW RUNS API")
    print("="*75)
    
    try:
        # Configura a URI de comunicação com a porta 5000 do Docker
        mlflow.set_tracking_uri("http://localhost:5000")
        
        # ID da corrida identificado na interface gráfica web
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
        print("    Certifique-se de que o contêiner 'minera_mlflow' está ligado.")
        print("="*75 + "\n")
        return None, None

if __name__ == "__main__":
    # Executa o teste de carga definitivo
    modelo_final, nome_modelo_ia = carregar_modelo_campeao_mlflow()
