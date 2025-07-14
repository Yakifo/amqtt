import React from "react";

export type DataPoint = {
  time: string // ISO format
  timestamp: number; // epoch milliseconds
  value: number;
};

// Define the type for each entry in the topic_map
export type TopicEntry<T> = {
  current: T;
  update: React.Dispatch<React.SetStateAction<T>>;
};

// Define the topic_map type
export type TopicMap = {
  [topic: string]: TopicEntry<DataPoint[]>;
};

// no need for a full uuid, generate a 6-character alphanumeric sequence, in two parts
export function getClientID() {
  const genPart = () => {
    const rand = (Math.random() * 46656) | 0
    // convert random number into an ascii sequence of letters, trimmed to 3 characters
    return ("000" + rand.toString(36)).slice(-3)
  }
  return `web-client-${genPart() + genPart()}`
}

export function secondsToDhms(seconds: number) {
  const days = Math.floor(seconds / (24 * 3600));
  seconds %= (24 * 3600);
  const hours = Math.floor(seconds / 3600);
  seconds %= 3600;
  const minutes = Math.floor(seconds / 60);
  seconds = seconds % 60;

  return {
    days: days,
    hours: hours,
    minutes: minutes,
    seconds: seconds,
  };
}

export function getMQTTSettings() {
  return {
    url: import.meta.env.VITE_MQTT_WS_TYPE + '://' + import.meta.env.VITE_MQTT_WS_HOST + ':' + import.meta.env.VITE_MQTT_WS_PORT,
    client_id: getClientID(),
    clean: true,
    protocol: 'wss',
    protocolVersion: 4, // MQTT 3.1.1
    wsOptions: {
      protocol: 'mqtt'
    }
  }
}
