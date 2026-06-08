# 🚚 Plataforma ПАКУЭ — Eficiência Energética de Frotas com I.A. (BelAZ-75306)

[![Go Version](https://shields.io)](https://go.dev)
[![Python Version](https://shields.io)](https://python.org)
[![Docker](https://shields.io)](https://docker.com)
[![MLflow](https://shields.io)](https://mlflow.org)

Este repositório hospeda a reconstrução industrial do ecossistema de software de gestão energética. O sistema gerencia, analisa e audita a intensidade energética e o consumo de combustível da frota de caminhões fora de estrada **BelAZ-75306** (capacidade de 220 toneladas) operando em cavas de mineração de grande porte.

---

## 🏗️ Arquitetura do Ecossistema Offline (Microsserviços)

```text
 [ Computador de Bordo Go ] ──(AMQP)──> [ RabbitMQ Broker ]
                                               │
 [ TimescaleDB Hypertable ] <──(Batch)─── [ Go API Gateway ]
        │                  (Measurements)
        ├──> [ Pipeline ML Python ] ───> [ MLflow Server (Port 5000) ]
        │       (Filtro Grubbs)               │ (Model Registry)
        └──> [ Motor Analytics ] <──(Runs API)┘
                (Cálculo de Desvios)
                     │
         [ Streamlit Web Dashboard ] (Visão Turnos Smena 1, 2 e Diário)
```

---

## 🧬 Fundamentos Científicos & Regras de Negócio

### 1. Modelagem Física de Borda
O computador de bordo simula os sensores do barramento CAN-Bus do veículo separando ciclos carregados de ciclos em vazio. Ele realiza *Edge Computing* para derivar as variáveis centrais:
* **Trabalho de Transporte Útil ($Q$):** $Q = \text{Peso Útil } [t] \times \text{Distância } [km]$
* **Massa de Combustível ($W$):** Conversão contínua de gramas injetadas para Toneladas $[t]$.
* **Consumo Específico Real ($w_{\text{real}}$):** $w_{\text{real}} = \frac{W \times 10^6}{Q} \quad [g/t\cdot km]$

### 2. Controle Estatístico de Gauss
Antes da modelagem preditiva, aplica-se o **Filtro de Smirnov-Grubbs** de forma iterativa para expurgar outliers causados por trepidações extremas de pista. A normalidade da amostra é auditada via teste inferencial de **Shapiro-Wilk** segregada por turnos industriais:
* **1º Turno (Smena 1):** 08:00h às 19:59h UTC
* **2º Turno (Smena 2):** 20:00h às 07:59h UTC
* **Diário (Сутки):** Consolidação assíncrona executada via *Continuous Aggregations* no banco.

### 3. Modelo Preditivo Principal
O modelo principal é uma **Regressão Linear Múltipla** devido à sua total interpretabilidade física para o planejamento de metas, tendo o **Random Forest Regressor** ($R^2 = 99.51\%$) como benchmark analítico não-linear.

### 4. Impacto Econômico e Financeiro 
A avaliação monetária da eficiência segue a equação da página 48 do manual:
$$\mathbf{Э_{э\ м\ i} = (w_{пл\ м\ i} - w_{ф\ ср\ i}) \cdot Q_{ф\ i} \cdot Ц_э}$$
Onde $Ц_э$ representa a tarifa do óleo diesel configurada na plataforma (R$ 6,00/kg).

---

## 📂 Organização Modular do Repositório

* `/backend/cmd/collector`: Computador de bordo em Go (simulador CAN-Bus IoT com marcação de turnos).
* `/backend/cmd/server`: API Gateway assíncrona em Go (gravação paralela via pool nativo `pgxpool`).
* `/backend/sql`: Scripts DDL criando Hypertables do TimescaleDB e as views de consolidação assíncronas.
* `/machine_learning`: Pipeline Python contendo o tratamento Grubbs, teste Shapiro-Wilk e treino via MLflow.
* `/analytics`: Motor contínuo de auditoria de desvios ($>10\%$) e interface gráfica em Streamlit Web.

---

## 🛠️ Como Executar a Plataforma Localmente

### Pré-requisitos
* Docker Desktop instalado e ativo.
* Go (Golang) instalado na máquina.
* Python 3.10+ configurado.

### Erguer a Infraestrutura Docker
Na raiz do projeto, execute o orquestrador para ligar o banco, o broker e o painel de MLOps:
```bash
docker compose up -d
```

### Inicializar o Banco de Dados (Injeção de Tabelas)
```bash
Get-Content backend/sql/init.sql | docker exec -i minera_db psql -U admin -d energy_management
```

### Iniciar a Camada de Ingestão (Go)
Abra dois terminais paralelos para rodar o Server central e o Coletor veicular:
```bash
# Terminal do Server
cd backend/cmd/server && go run main.go

# Terminal do Collector
cd backend/cmd/collector && go run main.go
```

### Executar Treinamento da I.A. & Monitoramento
Com o ambiente virtual `venv` ativo e dependências instaladas:
```bash
# Executa o Pipeline e registra o modelo campeão no MLflow (Port 5000)
cd machine_learning && python train.py

# Liga o Motor de Analytics de desvios
cd analytics && python main.py
```

### Abrir o Painel Corporativo (Streamlit)
```bash
python -m streamlit run analytics/dashboard.py
```
