package main

import (
	"fmt"
	"os"
	"strconv"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

func main() {
	if len(os.Args) < 2 {
		fatalf("usage: go-mqtt-client <connect|publish|ws-publish> ...")
	}

	switch os.Args[1] {
	case "connect":
		if len(os.Args) != 5 {
			fatalf("usage: connect <host> <port> <clientId>")
		}
		connect("tcp://"+os.Args[2]+":"+os.Args[3], os.Args[4])
	case "publish":
		if len(os.Args) != 8 {
			fatalf("usage: publish <host> <port> <clientId> <topic> <payload> <qos>")
		}
		qos := parseQoS(os.Args[7])
		publish("tcp://"+os.Args[2]+":"+os.Args[3], os.Args[4], os.Args[5], os.Args[6], qos, 1)
	case "ws-publish":
		if len(os.Args) != 8 {
			fatalf("usage: ws-publish <url> <clientId> <topic> <payload> <qos> <count>")
		}
		qos := parseQoS(os.Args[6])
		count, err := strconv.Atoi(os.Args[7])
		if err != nil || count < 1 {
			fatalf("invalid count: %s", os.Args[7])
		}
		publish(os.Args[2], os.Args[3], os.Args[4], os.Args[5], qos, count)
	default:
		fatalf("unknown command: %s", os.Args[1])
	}
}

func connect(brokerURL string, clientID string) {
	client := newClient(brokerURL, clientID)
	wait(client.Connect(), "connect")
	client.Disconnect(250)
}

func publish(brokerURL string, clientID string, topic string, payload string, qos byte, count int) {
	client := newClient(brokerURL, clientID)
	wait(client.Connect(), "connect")
	for i := 0; i < count; i++ {
		wait(client.Publish(topic, qos, false, payload), "publish")
	}
	client.Disconnect(250)
}

func newClient(brokerURL string, clientID string) mqtt.Client {
	options := mqtt.NewClientOptions()
	options.AddBroker(brokerURL)
	options.SetClientID(clientID)
	options.SetCleanSession(true)
	options.SetProtocolVersion(4)
	options.SetConnectTimeout(5 * time.Second)
	options.SetKeepAlive(30 * time.Second)
	return mqtt.NewClient(options)
}

func wait(token mqtt.Token, action string) {
	if !token.WaitTimeout(5 * time.Second) {
		fatalf("%s timed out", action)
	}
	if err := token.Error(); err != nil {
		fatalf("%s failed: %v", action, err)
	}
}

func parseQoS(value string) byte {
	qos, err := strconv.Atoi(value)
	if err != nil || qos < 0 || qos > 2 {
		fatalf("invalid qos: %s", value)
	}
	return byte(qos)
}

func fatalf(format string, args ...any) {
	fmt.Fprintf(os.Stderr, format+"\n", args...)
	os.Exit(1)
}
