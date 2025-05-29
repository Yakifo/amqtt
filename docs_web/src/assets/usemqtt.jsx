import { useState, useEffect, useCallback, useRef } from 'react';
import mqtt from 'mqtt';

/**
 * Hook for connecting to an MQTT broker and subscribing to topics.
 *
 * @param {Object} settings - Configuration settings for the MQTT connection.
 * @param {string} settings.url - URL of the MQTT broker.
 * @param {Object} [settings.config] - Additional configuration options for the MQTT connection.
 * @param {number} [settings.reconnectDelay] - Reconnect delay in milliseconds (default: 5000).
 *
 * @returns {Object} An object containing the MQTT client, connection status, and payload.
 */

const Status = Object.freeze({
  NOT_CONNECTED: 'NOT_CONNECTED',
  IN_PROGRESS: 'IN_PROGRESS',
  CONNECTED: 'CONNECTED',
});

export default function useMqtt(settings) {
  const [client, setClient] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState(Status.NOT_CONNECTED);
  const [isConnected, setIsConnected] = useState(false);

  const subscribedTopics = useRef([]);

  const messageQueue = useRef([]);
  const [messageTick, setMessageTick] = useState(0); // used to trigger re-renders when new messages arrive


  const getClientId = () => {
    return `mqttjs_${settings.client_id}`;
  };

  const mqttConnect = useCallback(async () => {
    // Prevent multiple connection attempts
    if (connectionStatus !== Status.NOT_CONNECTED) {
      // console.log('trying to connect or already connected');
      return;
    }
    
    setConnectionStatus(Status.IN_PROGRESS);
    const clientId = getClientId();
    const url = settings.url;
    const options = {
      clientId,
      keepalive: 60,
      clean: true,
      reconnectPeriod: 0, // Disable automatic reconnection - we'll handle it ourselves
      connectTimeout: 30000,
      rejectUnauthorized: false,
      ...settings.config
    };
    try {
      const clientMqtt = await mqtt.connect(url, options);
      
      // Set up initial event listeners
      clientMqtt.on('connect', () => {
        setConnectionStatus(Status.CONNECTED);
        console.log('MQTT Connected');
      });
      
      clientMqtt.on('error', (err) => {
        console.error('MQTT Connection error:', err.message);
        setConnectionStatus(Status.NOT_CONNECTED);
        
        // Schedule reconnect separately from the event handler
        // setTimeout(() => {
        //   const delay = err.message?.includes('Not authorized')
        //     ? Math.max(3000, settings.reconnectDelay || 5000)
        //     : (settings.reconnectDelay || 5000);
        //
        //   console.log(`Waiting ${delay/1000} seconds before reconnecting...`);
        //   setTimeout(mqttConnect, delay);
        // }, 0);
      });

      clientMqtt.on('close', () => {
        console.log('MQTT Connection closed');
        setConnectionStatus(Status.NOT_CONNECTED);
      });

      clientMqtt.on('offline', () => {
        console.log('MQTT Offline');
        setConnectionStatus(Status.NOT_CONNECTED);
      });

      clientMqtt.on('message', (_topic, message) => {
        const payloadMessage = { topic: _topic, message: message.toString() };
        messageQueue.current.push(payloadMessage);
        setMessageTick((t) => t + 1); // trigger processing
      });

      setClient(clientMqtt);

    } catch (error) {
      console.error('MQTT Connection error:', error.message);
      setConnectionStatus(Status.NOT_CONNECTED);

      await mqttConnect();
    }
  }, [settings]);

  const mqttDisconnect = useCallback(() => {
    if (client) {
      client.end(() => {
        console.log('MQTT Disconnected');
        setConnectionStatus(Status.NOT_CONNECTED);

      });
    }
  }, [client]);

  const mqttSubscribe = async (topic) => {
    if (client && !subscribedTopics.current.includes(topic)) {
      console.log('MQTT subscribe ', topic);
      const _clientMqtt = await client.subscribe(topic, {
        qos: 0,
        rap: false,
        rh: 0,
      }, (error, granted) => {
        if (error) {
          console.log('MQTT Subscribe to topics error', error);
        } else {
          granted.forEach((item) => {
            subscribedTopics.current.push(item.topic)
          })
        }
      });
      
      // setClient(clientMqtt);
    }
  };

  const mqttUnSubscribe = async (topic) => {
    if (client) {
      const _clientMqtt = await client.unsubscribe(topic, (error) => {
        if (error) {
          console.log('MQTT Unsubscribe error', error);
        }
      });
      // setClient(clientMqtt);
    }
  };

  useEffect(() => {
    console.log('connectionStatus', connectionStatus);
    if(connectionStatus === Status.CONNECTED) {
      setIsConnected(true);
    } else {
      subscribedTopics.current = [];
      setIsConnected(false)
    }
  }, [connectionStatus])

  useEffect(() => {
    const _clientMqtt = mqttConnect();
    return () => {
      //mqttDisconnect();
    };
  }, [mqttConnect, mqttDisconnect]);

  return {
    mqttConnect,
    mqttDisconnect,
    mqttSubscribe,
    mqttUnSubscribe,
    messageQueue,
    messageTick,
    isConnected
  };
}