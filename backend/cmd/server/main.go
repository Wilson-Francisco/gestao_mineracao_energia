package main

import (
	"log"
	"os"
	"os/signal"
	"syscall"

	amqp "github.com/rabbitmq/amqp091-go"
)

func main() {
	log.Println("[API Gateway] Inicializando Servidor Central de Ingestão...")

	// 1. Conecta de forma offline ao Broker do RabbitMQ
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

	// 2. Garante o vínculo com a fila oficial do BelAZ-75306 gerada na Fase 3
	q, err := ch.QueueDeclare(
		"telemetria_belaz_75306",
		true, // Fila persistente em disco
		false,
		false,
		false,
		nil,
	)
	if err != nil {
		log.Fatalf("[Erro] Falha ao vincular com a fila de telemetria: %v", err)
	}

	log.Printf("[API Gateway] Escuta ativa na fila '%s'. Aguardando pacotes...", q.Name)

	// Mecanismo de segurança para manter o servidor ligado até receber ordem de fechar
	sinalParada := make(chan os.Signal, 1)
	signal.Notify(sinalParada, syscall.SIGINT, syscall.SIGTERM)

	<-sinalParada
	log.Println("[API Gateway] Desligando servidor central de forma segura...")
}
