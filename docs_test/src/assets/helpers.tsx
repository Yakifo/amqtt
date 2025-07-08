import React from "react";

export type DataPoint = {
  timestamp: string; // ISO format
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