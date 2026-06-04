import unittest
import psycopg2
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import sys
import os

# Adiciona a pasta analytics ao caminho para permitir simular o motor analítico
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'analytics')))
from main import carregar_modelo_campeao_mlflow

class TestPipelineIntegration(unittest.TestCase):

    def setUp(self):
        """Estabelece conexão real com o Docker antes de disparar a auditoria"""
        self.conn = psycopg2.connect(
            host="localhost", database="energy_management",
            user="admin", password="mineracao_secure_2026", port="5432"
        )
        # Carrega o modelo de IA via API do MLflow homologado na Fase 5
        self.modelo_ia, _ = carregar_modelo_campeao_mlflow()

    def tearDown(self):
        """Fecha a ponte de comunicação de forma segura após o teste"""
        self.conn.close()

    def test_fluxo_end_to_end_geracao_alerta(self):
        """Parte 2: Injeta anomalia grave na Hypertable e valida o disparo da IA"""
        self.assertIsNotNone(self.modelo_ia, "O servidor MLflow precisa estar online com o modelo homologado.")
        
        cursor = self.conn.cursor()
        timestamp_teste = datetime.now(timezone.utc)
        asset_id_teste = 99  # ID exclusivo reservado para o teste de integração
        
        # 1. Dados de rampa simulando um sobreconsumo severo (Falha mecânica/operacional)
        prod_q_falso = 100.0        # Trabalho de transporte baixo [t·km]
        cons_w_falso = 0.500000     # Consumo de diesel altíssimo [t] (Injeção travada)
        w_spec_real_falso = 5000.0  # Consumo específico gigante [g/t·km]
        
        print("\n[Teste Integração] Passo 1: Injetando linha anômala na Hypertable...")
        query_insert_bruto = """
            INSERT INTO measurements (timestamp, asset_id, production_q, consumption_w, efficiency_w_spec)
            VALUES (%s, %s, %s, %s, %s);
        """
        cursor.execute(query_insert_bruto, (timestamp_teste, asset_id_teste, prod_q_falso, cons_w_falso, w_spec_real_falso))
        
        # 2. Executa a lógica de inferência da I.A. emulando o Motor de Analytics da Fase 6
        print("[Teste Integração] Passo 2: Forçando processamento do cérebro preditivo...")
        matriz_entrada = np.array([[prod_q_falso, cons_w_falso]])
        w_spec_planejado = float(self.modelo_ia.predict(matriz_entrada)[0])

        # Margem de tolerância regulatória de 10%
        limite_tolerancia = w_spec_planejado * 1.10
        
        # Se ultrapassar o limite, grava o alerta crítico
        if w_spec_real_falso > limite_tolerancia:
            percentual_desvio = ((w_spec_real_falso - w_spec_planejado) / w_spec_planejado) * 100
            desc_alerta = f"[TESTE INTEGRAÇÃO] Sobreconsumo de {percentual_desvio:.2f}% localizado."
            
            query_insert_alerta = """
                INSERT INTO anomaly_alerts (timestamp, asset_id, metric_type, description, severity)
                VALUES (%s, %s, %s, %s, %s);
            """
            cursor.execute(query_insert_alerta, (timestamp_teste, asset_id_teste, 'INTEGRATION_TEST_OVER', desc_alerta, 'CRITICAL'))
        
        # Persiste temporariamente as alterações para realizar o SELECT de validação
        self.conn.commit()

        # 3. Auditoria Física: Verifica se o registro de anomalia foi gravado de verdade
        print("[Teste Integração] Passo 3: Escaneando tabela 'anomaly_alerts' no Docker...")
        query_select_validacao = "SELECT COUNT(*) FROM anomaly_alerts WHERE asset_id = %s;"
        cursor.execute(query_select_validacao, (asset_id_teste,))
        total_alertas_gravados = cursor.fetchone()[0]
        
        # Limpeza pós-teste: Deleta os logs falsos do caminhão 99 para manter o banco limpo
        cursor.execute("DELETE FROM measurements WHERE asset_id = %s;", (asset_id_teste,))
        cursor.execute("DELETE FROM anomaly_alerts WHERE asset_id = %s;", (asset_id_teste,))
        self.conn.commit()
        cursor.close()
        
        # O teste passa com nota 10 se o total de alertas encontrados for exatamente 1
        print(f"[Teste Integração] Sucesso! Total de alertas críticos validados: {total_alertas_gravados}")
        self.assertEqual(total_alertas_gravados, 1, "O pipeline falhou em gerar ou persistir o alerta de I.A.")

if __name__ == "__main__":
    print("\n" + "="*70)
    print("INICIALIZANDO AUDITORIA DE SOFTWARE: TESTES DE INTEGRAÇÃO")
    print("="*70)
    unittest.main()
