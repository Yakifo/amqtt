import java.util.Locale;
import org.eclipse.paho.client.mqttv3.MqttClient;
import org.eclipse.paho.client.mqttv3.MqttConnectOptions;
import org.eclipse.paho.client.mqttv3.MqttMessage;

public final class MqttInteropClient {
    private MqttInteropClient() {
    }

    public static void main(String[] args) throws Exception {
        if (args.length < 1) {
            throw new IllegalArgumentException("usage: MqttInteropClient <connect|publish|ws-publish> ...");
        }

        String command = args[0].toLowerCase(Locale.ROOT);
        switch (command) {
            case "connect" -> {
                if (args.length != 4) {
                    throw new IllegalArgumentException("usage: connect <host> <port> <clientId>");
                }
                connect("tcp://" + args[1] + ":" + args[2], args[3]);
            }
            case "publish" -> {
                if (args.length != 7) {
                    throw new IllegalArgumentException("usage: publish <host> <port> <clientId> <topic> <payload> <qos>");
                }
                publish("tcp://" + args[1] + ":" + args[2], args[3], args[4], args[5], Integer.parseInt(args[6]), 1);
            }
            case "ws-publish" -> {
                if (args.length != 7) {
                    throw new IllegalArgumentException("usage: ws-publish <uri> <clientId> <topic> <payload> <qos> <count>");
                }
                publish(args[1], args[2], args[3], args[4], Integer.parseInt(args[5]), Integer.parseInt(args[6]));
            }
            default -> throw new IllegalArgumentException("unknown command: " + command);
        }
    }

    private static void connect(String brokerUri, String clientId) throws Exception {
        MqttClient client = new MqttClient(brokerUri, clientId, null);
        client.connect(connectOptions());
        client.disconnect();
        client.close();
    }

    private static void publish(
            String brokerUri,
            String clientId,
            String topic,
            String payload,
            int qos,
            int count
    ) throws Exception {
        MqttClient client = new MqttClient(brokerUri, clientId, null);
        client.connect(connectOptions());
        for (int i = 0; i < count; i++) {
            MqttMessage message = new MqttMessage(payload.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            message.setQos(qos);
            client.publish(topic, message);
        }
        client.disconnect();
        client.close();
    }

    private static MqttConnectOptions connectOptions() {
        MqttConnectOptions options = new MqttConnectOptions();
        options.setMqttVersion(MqttConnectOptions.MQTT_VERSION_3_1_1);
        options.setCleanSession(true);
        options.setConnectionTimeout(5);
        return options;
    }
}
