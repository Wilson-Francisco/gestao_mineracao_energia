package main

import (
	"context"
	"encoding/json"
	"log"
	"math/rand"
	"time"

	amqp "github.com/rabbitmq/amqp091-go"
)

// TelemetriaBelaz representa o payload JSON oficial de telemetria
type TelemetriaBelaz struct {
	Timestamp        time.Time `json:"timestamp"`
	AssetID          int       `json:"asset_id"`
	TurnoOperacional string    `json:"turno_operacional"` // "Smena 1" ou "Smena 2"
	ProductionQ      float64   `json:"production_q"`      // Trabalho de Transporte Real [t·km]
	ConsumptionW     float64   `json:"consumption_w"`     // Massa de Combustível Consumido [t]
	EfficiencyWSpec  float64   `json:"efficiency_w_spec"` // Consumo Específico de Energia Real [g/t·km]
}

// definirTurnoAtual lê o relógio do sistema e carimba o turno com base nas regras do ПАКУЭ
func definirTurnoAtual(t time.Time) string {
	hora := t.Hour()
	// Turno 1 (Diurno): 08:00 às 19:59
	if hora >= 8 && hora < 20 {
		return "Smena 1"
	}
	// Turno 2 (Noturno): 20:00 às 07:59
	return "Smena 2"
}

func main() {
	log.Println("[IoT Borda] Inicializando Computador de Bordo do BelAZ-75306...")

	// 1. Estabelece conexão local com o Broker RabbitMQ via protocolo AMQP
	conn, err := amqp.Dial("amqp://guest:guest@localhost:5672/")
	if err != nil {
		log.Fatalf("[Erro] Falha ao conectar no RabbitMQ Broker: %v", err)
	}
	defer conn.Close()

	ch, err := conn.Channel()
	if err != nil {
		log.Fatalf("[Erro] Falha ao abrir canal de mensageria: %v", err)
	}
	defer ch.Close()

	// Declarar a fila oficial de telemetria veicular para o caminhão
	q, err := ch.QueueDeclare(
		"telemetria_belaz_75306", // Nome da fila estruturada no fluxograma
		true,                     // Durable: Fila persistente em disco no Docker
		false,
		false,
		false,
		nil,
	)
	if err != nil {
		log.Fatalf("[Erro] Falha ao declarar a fila de transporte: %v", err)
	}

	rand.Seed(time.Now().UnixNano())
	ctx := context.Background()

	log.Println("[IoT Borda] Conexão ativa! Enviando telemetria a cada 3 segundos...")

	// Loop contínuo de simulação dos sensores CAN-Bus do caminhão de 220 toneladas
	for {
		agora := time.Now().UTC()
		turno := definirTurnoAtual(agora)

		// Física do Ciclo de Transporte: Simula se o caminhão está carregado ou vazio
		estaCarregado := rand.Float64() > 0.4
		var pesoCacamba float64  // Toneladas de carga útil [t]
		var distanciaKm float64  // Distância percorrida no ciclo [km]
		var dieselGramas float64 // Consumo real de diesel medido em gramas [g]

		if estaCarregado {
			// Caminhão carregado subindo a rampa da mina com minério
			pesoCacamba = 180.0 + (rand.Float64() * 40.0) // Entre 180t e 220t (Capacidade Máxima)
			distanciaKm = 1.5 + (rand.Float64() * 2.5)    // Ciclos de 1.5km a 4km
			// Consumo massivo de rampa pesada
			dieselGramas = (pesoCacamba * distanciaKm) * (75.0 + (rand.Float64() * 10.0))
		} else {
			// Caminhão vazio retornando para a escavadeira no fundo da cava
			pesoCacamba = 0.0                          // Sem carga útil de produção
			distanciaKm = 1.5 + (rand.Float64() * 2.5) // Retorna a mesma distância
			// Consumo de deslocamento em vazio (Apenas tara do veículo)
			dieselGramas = 3000.0 + (rand.Float64() * 1500.0)
		}

		// -----------------------------------------------------------------
		// ENGENHARIA DE RECURSOS DE BORDA (EDGE COMPUTING)
		// -----------------------------------------------------------------
		// Q: Trabalho útil de transporte [t·km] = Peso útil * Distância
		// Se peso = 0 (vazio), o trabalho de transporte útil é 0, mas há gasto de diesel
		prodQ := pesoCacamba * distanciaKm

		// W: Conversão de massa de combustível de Gramas para Toneladas [t]
		consW := dieselGramas / 1000000.0

		// w_spec: Consumo específico real em [g/t·km]
		// Para evitar divisão por zero quando o caminhão corre vazio, usamos a linha de base de tara
		var effWSpec float64
		if prodQ > 0 {
			effWSpec = dieselGramas / prodQ
		} else {
			// Consumo específico simulado em vazio para fins de histórico analítico
			effWSpec = dieselGramas / (150.0 * distanciaKm)
		}

		// Montagem do objeto estruturado
		telemetria := TelemetriaBelaz{
			Timestamp:        agora,
			AssetID:          1, // ID do Caminhão BelAZ 01 da Frota
			TurnoOperacional: turno,
			ProductionQ:      prodQ,
			ConsumptionW:     consW,
			EfficiencyWSpec:  effWSpec,
		}

		// Converte o objeto em payload textual JSON
		body, err := json.Marshal(telemetria)
		if err != nil {
			log.Printf("[Aviso] Erro ao serializar JSON: %v", err)
			continue
		}

		// Despacha o pacote JSON para a fila estável do RabbitMQ
		err = ch.PublishWithContext(ctx,
			"",     // Exchange padrão
			q.Name, // Routing Key = Nome da fila
			false,
			false,
			amqp.Publishing{
				DeliveryMode: amqp.Persistent, // Mensagem salva em disco contra quedas
				ContentType:  "application/json",
				Body:         body,
			},
		)
		if err != nil {
			log.Printf("[Aviso] Falha ao injetar pacote na fila AMQP: %v", err)
		} else {
			log.Printf("[IoT] Dados Enviados -> %s | Q=%.2f t·km | W=%.6f t | w=%.2f g/t·km",
				turno, prodQ, consW, effWSpec)
		}

		// Janela de amostragem de 3 segundos definida no escopo técnico
		time.Sleep(3 * time.Second)
	}
}
