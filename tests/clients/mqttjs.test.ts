import mqtt, { MqttClient } from 'mqtt';

import { spawn, ChildProcess } from 'child_process';

let brokerProcess: ChildProcess;

beforeAll(() => {
  // brokerProcess = spawn('amqtt', {
  //   cwd: __dirname,
  //   stdio: 'inherit', // optional: shows output in real time
  // });

});

afterAll(() => {
  // if (brokerProcess && !brokerProcess.killed) {
  //   brokerProcess.kill();
  // }
});

test('MQTT client connects to broker', async () => {

  await new Promise((resolve) => setTimeout(resolve, 500));

  const client = mqtt.connect('mqtt://localhost:1883', {'connectTimeout': 2000});

  await new Promise<void>((resolve, reject) => {
    client.on('connect', () => {

      expect(client.connected).toBe(true);
      client.end(true, {}, (err) => {
        if (err) reject(err);
        else resolve();
      });
    });

    client.on('error', (err) => {
      client.end(true, {}, () => reject(err));
    });
  });
});


test('MQTT client subscribes to $SYS', async () => {

  await new Promise((resolve) => setTimeout(resolve, 500));

  const client = mqtt.connect('mqtt://localhost:1883', {'connectTimeout': 2000});

  await new Promise<void>((resolve, reject) => {
    client.on('connect', () => {

      expect(client.connected).toBe(true);
      client.subscribe('$SYS/#');
      client.end(true, {}, (err) => {
        if (err) reject(err);
        else resolve();
      });
    });

    client.on("message", (topic, message) => {
      // message is Buffer
      console.log(message.toString());
      client.end();
    });

    client.on('error', (err) => {
      client.end(true, {}, () => reject(err));
    });
  });
});


