package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	// EXPRESSÕES OFICIAIS FIXADAS: Conexão direta por Pool de Alta Performance

	"github.com/jackc/pgx/v5/pgxpool"
	amqp "github.com/rabbitmq/amqp091-go"
)

// TelemetriaPayload representa a estrutura do JSON enviado pelo caminhão BelAZ na Fase 3
type TelemetriaPayload struct {
	Timestamp        time.Time `json:"timestamp"`
	AssetID          int       `json:"asset_id"`
	TurnoOperacional string    `json:"turno_operacional"`
	ProductionQ      float64   `json:"production_q"`      // Trabalho de Transporte [t·km]
	ConsumptionW     float64   `json:"consumption_w"`     // Consumo de Diesel [t]
	EfficiencyWSpec  float64   `json:"efficiency_w_spec"` // Consumo Específico [g/t·km]
}

func main() {
	log.Println("[API Gateway] Inicializando Servidor Central de Ingestão...")
	ctx := context.Background()

	// =========================================================================
	// PARTE 2 CORRIGIDA: POOL NATIVA DE ALTA VELOCIDADE COM PGXPOOL
	// =========================================================================
	dsn := fmt.Sprintf("postgres://%s:%s@%s:%d/%s?sslmode=disable",
		"admin", "mineracao_secure_2026", "localhost", 5432, "energy_management")

	log.Println("[API Gateway] Abrindo pool nativa de conexões com pgxpool/v5...")

	// Cria a pool chamando diretamente o pacote jackc/pgx (Impossível de ser deletado pelo VS Code!)
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		log.Fatalf("[Erro] Falha ao configurar a pool nativa do pgx: %v", err)
	}
	defer pool.Close()

	// Executa o teste de Ping físico passando o contexto
	if err = pool.Ping(ctx); err != nil {
		log.Fatalf("[Erro] Banco de dados inacessível ou offline: %v", err)
	}
	log.Println("[API Gateway] Conexão com o TimescaleDB estabelecida via PGXPOOL/V5!")

	// =========================================================================
	// PARTE 1: BARRAMENTO DE MENSAGENS (RabbitMQ)
	// =========================================================================
	conn, err := amqp.Dial("amqp://guest:guest@localhost:5672/")
	if err != nil {
		log.Fatalf("[Erro] Falha ao conectar no barramento RabbitMQ: %v", err)
	}
	defer conn.Close()

	ch, err := conn.Channel()
	if err != nil {
		log.Fatalf("[Erro] Falha ao abrir canal de mensageria: %v", err)
	}
	defer ch.Close()

	q, err := ch.QueueDeclare("telemetria_belaz_75306", true, false, false, false, nil)
	if err != nil {
		log.Fatalf("[Erro] Falha ao vincular fila de transporte: %v", err)
	}

	mensagens, err := ch.Consume(q.Name, "", true, false, false, false, nil)
	if err != nil {
		log.Fatalf("[Erro] Falha ao abrir fluxo de consumo: %v", err)
	}

	// =========================================================================
	// PARTE 3: PROCESSAMENTO CONCORRENTE ASSÍNCRONO (GOROUTINE)
	// =========================================================================
	go func() {
		log.Println("[API Gateway] Goroutine ativa. Aguardando pacotes do barramento CAN...")

		for d := range mensagens {
			var p TelemetriaPayload

			err := json.Unmarshal(d.Body, &p)
			if err != nil {
				log.Printf("[Aviso] Falha ao processar payload JSON corrompido: %v", err)
				continue
			}

			// Inserção otimizada executada diretamente na pool do pgx
			queryInsert := `
				INSERT INTO measurements (timestamp, asset_id, production_q, consumption_w, efficiency_w_spec)
				VALUES ($1, $2, $3, $4, $5);
			`
			_, err = pool.Exec(ctx, queryInsert, p.Timestamp, p.AssetID, p.ProductionQ, p.ConsumptionW, p.EfficiencyWSpec)
			if err != nil {
				log.Printf("[Erro Banco] Falha ao persistir telemetria do BelAZ no Timescale: %v", err)
			} else {
				log.Printf("[Gateway -> Banco] Gravado com Sucesso! %s | Q=%.2f t·km | W=%.6f t",
					p.TurnoOperacional, p.ProductionQ, p.ConsumptionW)
			}
		}
	}()

	log.Println("[API Gateway] Servidor online em modo de escuta total. Pressione Ctrl+C para encerrar.")

	sinalParada := make(chan os.Signal, 1)
	signal.Notify(sinalParada, syscall.SIGINT, syscall.SIGTERM)
	<-sinalParada
	log.Println("[API Gateway] Desligando servidor central de forma segura...")
}
