-- ============================================================================
-- SCRIPT DE INICIALIZAÇÃO E MODELAGEM DE TURNOS - PADRÃO МИСИС (ПАКУЭ)
-- ATIVO: CAMINHÃO FORA DE ESTRADA BelAZ-75306 (CAPACIDADE 220 TONELADAS)
-- ============================================================================

-- 1. Criação da Tabela de Telemetria Bruta de Campo
CREATE TABLE IF NOT EXISTS measurements (
    timestamp TIMESTAMPTZ NOT NULL,
    asset_id INT NOT NULL,
    production_q DOUBLE PRECISION NOT NULL,    -- Trabalho de Transporte Real [t·km]
    consumption_w DOUBLE PRECISION NOT NULL,   -- Massa de Combustível Consumido [t]
    efficiency_w_spec DOUBLE PRECISION NOT NULL -- Consumo Específico de Energia Real [g/t·km]
);

-- Transformação da tabela em uma Hypertable do TimescaleDB fatiada por tempo (Intervalo de 1 dia)
SELECT create_hypertable('measurements', 'timestamp', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);

-- 2. Criação da Tabela para Registro de Alertas Críticos gerados pela I.A.
CREATE TABLE IF NOT EXISTS anomaly_alerts (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    asset_id INT NOT NULL,
    metric_type VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    severity VARCHAR(20) NOT NULL
);

-- ============================================================================
-- REGRA DE NEGÓCIO (TURNOS OPERACIONAIS DA MINA):
-- 1º TURNO (DIURNO): 08:00:00 às 19:59:59
-- 2º TURNO (NOTURNO): 20:00:00 às 07:59:59 (do dia seguinte)
-- DIÁRIO (SUKTI): Fechamento consolidado das 24 horas.
-- ============================================================================

-- Consolidação do 1º Turno (Diurno)
CREATE OR REPLACE VIEW v_kpi_primeiro_turno AS
SELECT 
    time_bucket('12 hours', timestamp, '08:00:00') AS periodo_fechamento,
    asset_id,
    SUM(production_q) AS total_producao_t_km,
    SUM(consumption_w) AS total_consumo_t,
    -- Formula do manual: g/t·km = (Consumo em toneladas * 1.000.000) / Produção em t·km
    CASE 
        WHEN SUM(production_q) > 0 THEN (SUM(consumption_w) * 1000000) / SUM(production_q)
        ELSE 0 
    END AS consumo_especifico_g_t_km
FROM measurements
WHERE EXTRACT(HOUR FROM timestamp AT TIME ZONE 'UTC') >= 8 
  AND EXTRACT(HOUR FROM timestamp AT TIME ZONE 'UTC') < 20
GROUP BY periodo_fechamento, asset_id;

-- Consolidação do 2º Turno (Noturno)
CREATE OR REPLACE VIEW v_kpi_segundo_turno AS
SELECT 
    time_bucket('12 hours', timestamp, '20:00:00') AS periodo_fechamento,
    asset_id,
    SUM(production_q) AS total_producao_t_km,
    SUM(consumption_w) AS total_consumo_t,
    CASE 
        WHEN SUM(production_q) > 0 THEN (SUM(consumption_w) * 1000000) / SUM(production_q)
        ELSE 0 
    END AS consumo_especifico_g_t_km
FROM measurements
WHERE EXTRACT(HOUR FROM timestamp AT TIME ZONE 'UTC') >= 20 
   OR EXTRACT(HOUR FROM timestamp AT TIME ZONE 'UTC') < 8
GROUP BY periodo_fechamento, asset_id;

-- Consolidação Diária (Fechamento Completo 24h - Сутки)
CREATE OR REPLACE VIEW v_kpi_diario AS
SELECT 
    time_bucket('1 day', timestamp) AS dia_fechamento,
    asset_id,
    SUM(production_q) AS total_producao_t_km,
    SUM(consumption_w) AS total_consumo_t,
    CASE 
        WHEN SUM(production_q) > 0 THEN (SUM(consumption_w) * 1000000) / SUM(production_q)
        ELSE 0 
    END AS consumo_especifico_g_t_km
FROM measurements
GROUP BY dia_fechamento, asset_id;

