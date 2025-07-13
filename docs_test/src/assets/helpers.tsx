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