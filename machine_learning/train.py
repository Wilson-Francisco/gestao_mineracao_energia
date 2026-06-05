import psycopg2
import pandas as pd
import numpy as np
from scipy import stats
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score, mean_absolute_error
import os
import mlflow
import mlflow.sklearn

def conectar_banco():
    """Conecta ao TimescaleDB local no Docker de forma offline"""
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



def executar_teste_shapiro_wilk(valores, alpha=0.05):
    
    """
    Executa o Teste de Hipótese de Shapiro-Wilk para atestar
    a conformidade estatística com a Distribuição Normal de Gauss.
    H0: Os dados seguem uma Distribuição Normal.
    H1: Os dados possuem desvios significativos de normalidade.
    """
    if len(valores) < 3:
        return 0.0, 0.0, "Dados Insuficientes"

    # Executa o teste estatístico da biblioteca scipy
    w_estatistica, p_valor = stats.shapiro(valores)
    
    # Avaliação da hipótese com base no nível de significância de 5%
    if p_valor > alpha:
        veredicto = "ACEITA H0 (Dados Normais/Gaussianos)"
    else:
        veredicto = "REJEITA H0 (Dados Não-Gaussianos/Com Ruído)"
        
    return w_estatistica, p_valor, veredicto



def conduzir_auditoria_turnos_gauss(df_filtrado):
    """
    Segrega a base de dados por Turnos e Diário, aplicando
    as análises de forma e os testes inferenciais de hipótese isoladamente.
    """
    # Mapeamento dos grupos analíticos conforme exigido
    escopos = {
        "1º Turno (Smena 1 - Diurno)": df_filtrado[df_filtrado['smena'] == 'Smena 1'],
        "2º Turno (Smena 2 - Noturno)": df_filtrado[df_filtrado['smena'] == 'Smena 2'],
        "Consolidado Diário (Сутки)": df_filtrado
    }
    
    for rotulo, df_grupo in escopos.items():
        print("\n" + "-"*75)
        print(f"DIAGNÓSTICO DE GAUSS: {rotulo.upper()}")
        print("-"*75)
        
        if len(df_grupo) < 3:
            print(" -> [Aviso] Dados insuficientes neste turno para conduzir análises inferenciais.")
            continue
            
        valores = df_grupo['efficiency_w_spec'].to_numpy()
        
        # Executa as Partes 3.1 e 3.2 criadas anteriormente
        mu, sigma, skew, kurt = calcular_indicadores_forma_gauss(valores)
        w_stat, p_val, veredicto = executar_teste_shapiro_wilk(valores)
        
        print(f"  -> Média Operacional (μ)             : {mu:.4f} g/t·km")
        print(f"  -> Desvio Padrão Amostral (σ)        : {sigma:.4f} g/t·km")
        print(f"  -> Coeficiente de Assimetria (Skew)   : {skew:.4f}")
        print(f"  -> Coeficiente de Curtose (Kurtosis)  : {kurt:.4f}")
        print(f"  -> Teste de Shapiro-Wilk (p-value)    : {p_val:.6f}")
        print(f"  -> Veredicto da Lei de Gauss          : {veredicto}")
        print("-"*75)




def inicializar_governanca_mlflow():
    """
    Configura a rota de conexão offline com o servidor MLflow no Docker
    e estabelece o experimento oficial de monitoramento do BelAZ-75306.
    """
    print("\n" + "="*75)
    print("[MLES - MLOps] Conectando ao Servidor Central do MLflow (Porta 5000)...")
    
    # Aponta para o endereço do contêiner Docker
    mlflow.set_tracking_uri("http://localhost:5000")
    
    nome_experimento = "Gestao_Energetica_BelAZ_75306"
    
    # Verifica se o experimento já existe, senão cria um novo
    experimento = mlflow.get_experiment_by_name(nome_experimento)
    if experimento is None:
        id_experimento = mlflow.create_experiment(
            name=nome_experimento,
            artifact_location="mlflow-artifacts:/"
        )
        print(f" -> Novo experimento criado com sucesso! ID: {id_experimento}")
    else:
        id_experimento = experimento.experiment_id
        print(f" -> Vinculado ao experimento existente. ID: {id_experimento}")
        
    mlflow.set_experiment(nome_experimento)
    print("="*75 + "\n")
    return id_experimento


def executar_treinamento_e_registro_mlflow(df_filtrado):
    """
    Divide os dados, treina a Regressao Linear (Principal) e o 
    Random Forest (Comparativo), registrando metricas e artefatos no MLflow.
    """
    print("\n" + "="*75)
    print("[I.A. - Treinamento] Iniciando modelagem preditiva...")
    print("="*75)

    # 1. Definicao das Variaveis Multariaveis
    # Matriz X: Trabalho de Transporte [t·km] e Consumo [t]
    X = df_filtrado[['production_q', 'consumption_w']].to_numpy()
    # Vetor y: Consumo Especifico Real [g/t·km]
    y = df_filtrado['efficiency_w_spec'].to_numpy()

    # Divisao padrao de mercado: 80% para aprendizado e 20% para teste/validacao
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # 2. Inicializacao da Corrida de Monitoramento (Run) no MLflow
    with mlflow.start_run(run_name="Treinamento_Modelos_BelAZ"):
        
        # --- MODELO 1: REGRESSÃO LINEAR MÚLTIPLA (PRINCIPAL) ---
        print(" -> Treinando Modelo Principal: Regressão Linear Múltipla...")
        modelo_linear = LinearRegression()
        modelo_linear.fit(X_train, y_train)
        
        # Predicoes e Calculo de Indicadores de Acerto
        y_pred_linear = modelo_linear.predict(X_test)
        r2_linear = r2_score(y_test, y_pred_linear)
        mae_linear = mean_absolute_error(y_test, y_pred_linear)

        # --- MODELO 2: RANDOM FOREST REGRESSOR (COMPARATIVO) ---
        print(" -> Treinando Modelo Comparativo: Random Forest Regressor...")
        modelo_rf = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)
        modelo_rf.fit(X_train, y_train)
        
        y_pred_rf = modelo_rf.predict(X_test)
        r2_rf = r2_score(y_test, y_pred_rf)
        mae_rf = mean_absolute_error(y_test, y_pred_rf)

        # -----------------------------------------------------------------
        # ENVIO DE PARÂMETROS E MÉTRICAS PARA O SERVIDOR MLFLOW
        # -----------------------------------------------------------------
        # Salva as notas de acerto da Regressao Linear
        mlflow.log_metric("r2_regressao_linear", r2_linear)
        mlflow.log_metric("mae_regressao_linear", mae_linear)
        
        # Salva as notas de acerto do Random Forest
        mlflow.log_metric("r2_random_forest", r2_rf)
        mlflow.log_metric("mae_random_forest", mae_rf)

        print("\n" + "-"*75)
        print("BALANÇO DE ACURÁCIA PRECOGNITIVA (MÉTRIQUE RESULTADOS):")
        print(f" -> Regressao Linear (Principal)  | R² (Acerto): {r2_linear * 100:.2f}% | MAE: {mae_linear:.4f}")
        print(f" -> Random Forest (Comparativo)   | R² (Acerto): {r2_rf * 100:.2f}% | MAE: {mae_rf:.4f}")
        print("-"*75)

        # -----------------------------------------------------------------
        # REGISTRO DO MODELO CAMPEÃO NO MODEL REGISTRY
        # -----------------------------------------------------------------
       
        print("\n[MLOps] Salvando e registrando modelo no catalogo central do MLflow...")
        mlflow.sklearn.log_model(
            sk_model=modelo_linear,
            artifact_path="modelo_linear_misis",
            registered_model_name="Modelo_Energetico_BelAZ"
        )
        print("[MLOps] Sucesso! Modelo homologado e fixado no servidor.")


        # -----------------------------------------------------------------
        # PROMOÇÃO AUTOMATIZADA PARA ESTÁGIO DE PRODUÇÃO
        # -----------------------------------------------------------------
        print("[MLOps] Promovendo modelo registrado para o estágio 'Production'...")
        from mlflow.tracking import MlflowClient
        client = MlflowClient()
        
        # Carimba a Versão 1 do Modelo como o Campeão oficial da Frota BelAZ
        client.transition_model_version_stage(
            name="Modelo_Energetico_BelAZ",
            version=1,
            stage="Production",
            archive_existing_versions=True # Arquiva versões antigas automaticamente
        )
        print("[MLOps] Sucesso! Modelo promovido e pronto para producao.")



if __name__ == "__main__":
    print("\n" + "="*75)
    print("FASE 5 - PARTE 5: PIPELINE DE TREINAMENTO E REGISTRO CENTRAL")
    print("="*75)
    
    try:
        inicializar_governanca_mlflow()
        df_bruto = carregar_dados_historicos()
        if len(df_bruto) > 0:
            df_filtrado = aplicar_filtro_grubbs_nativo(df_bruto, 'efficiency_w_spec')
            conduzir_auditoria_turnos_gauss(df_filtrado)
            
            # Executa a nova Parte 5: Treina e registra no MLflow
            executar_treinamento_e_registro_mlflow(df_filtrado)
            print("\n" + "="*75 + "\n")
        else:
            print("[Aviso] Banco de dados vazio.")
    except Exception as e:
        print(f"[Erro] Falha no fechamento da Fase 5: {e}")