import unittest
import numpy as np
import sys
import os

# Adiciona a pasta machine_learning ao caminho do sistema para permitir a importação
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'machine_learning')))

# Importa as funções originais que desenvolvemos na Fase 5
from train import aplicar_filtro_grubbs_nativo, calcular_indicadores_forma_gauss

class TestAnalyticsMisis(unittest.TestCase):

    def setUp(self):
        """Prepara uma massa de dados controlada antes de cada teste"""
        # Massa estável seguindo uma distribuição limpa
        self.dados_estaveis = [50.0, 51.0, 49.0, 50.5, 49.5, 50.0, 50.2]
        
        # Massa corrompida com um Outlier extremo de trepidação de pista (999.0)
        self.dados_com_ruido = [50.0, 51.0, 49.0, 50.5, 49.5, 50.0, 999.0]

    def test_filtro_grubbs_detecta_outlier(self):
        """Parte 1.1: Valida se o algoritmo de Smirnov-Grubbs expurga o ruído extremo"""
        import pandas as pd
        df = pd.DataFrame({"efficiency_w_spec": self.dados_com_ruido})
        
        # Executa o filtro original da Fase 5
        df_limpo = aplicar_filtro_grubbs_nativo(df, "efficiency_w_spec", alpha=0.05)
        
        # O teste passa se o valor 999.0 tiver sido removido com sucesso da amostra
        self.assertNotIn(999.0, df_limpo["efficiency_w_spec"].values)
        self.assertEqual(len(df_limpo), 6)

    def test_indicadores_forma_gauss(self):
        """Parte 1.2: Valida se o cálculo de Assimetria e Curtose roda sem travar"""
        valores = np.array(self.dados_estaveis)
        
        # Executa o motor inferencial da Fase 5
        mu, sigma, skew, kurt = calcular_indicadores_forma_gauss(valores)
        
        # Validações matemáticas estritas
        self.assertAlmostEqual(mu, 50.03, places=2)
        self.assertTrue(sigma > 0)
        self.assertIsInstance(skew, float)
        self.assertIsInstance(kurt, float)

if __name__ == "__main__":
    print("\n" + "="*70)
    print("INICIALIZANDO AUDITORIA DE SOFTWARE: TESTES UNITÁRIOS")
    print("="*70)
    unittest.main()
