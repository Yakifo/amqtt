get_schema = {
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AWS IoT Shadow Get Request",
  "type": "object",
  "properties": {
    "clientToken": { "type": "string" }
  },
  "additionalProperties": False
}

get_accepted_schema = {
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AWS IoT Shadow Get Accepted",
  "type": "object",
  "properties": {
    "state": {
      "type": "object",
      "properties": {
        "desired": { "type": "object" },
        "reported": { "type": "object" }
      }
    },
    "metadata": {
      "type": "object"
    },
    "version": { "type": "integer" },
    "timestamp": { "type": "integer" },
    "clientToken": { "type": "string" }
  },
  "required": ["state", "version", "timestamp"],
  "additionalProperties": False
}

get_rejected_schema = {
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AWS IoT Shadow Get Rejected",
  "type": "object",
  "properties": {
    "code": { "type": "integer" },
    "message": { "type": "string" },
    "clientToken": { "type": "string" }
  },
  "required": ["code", "message"],
  "additionalProperties": False
}

update_schema = {
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AWS IoT Shadow Update",
  "type": "object",
  "properties": {
    "state": {
      "type": "object",
      "properties": {
        "desired": { "type": "object" },
        "reported": { "type": "object" }
      },
      "additionalProperties": False
    },
    "clientToken": { "type": "string" },
    "version": { "type": "integer" }
  },
  "additionalProperties": False
}

update_accepted_schema = {
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AWS IoT Shadow Update Accepted",
  "type": "object",
  "properties": {
    "state": {
      "type": "object",
      "properties": {
        "desired": { "type": "object" },
        "reported": { "type": "object" }
      }
    },
    "metadata": {
      "type": "object",
      "properties": {
        "desired": { "type": "object" },
        "reported": { "type": "object" }
      }
    },
    "version": { "type": "integer" },
    "timestamp": { "type": "integer" },
    "clientToken": { "type": "string" }
  },
  "required": ["version", "timestamp"],
  "additionalProperties": False
}

update_rejected_schema = {
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AWS IoT Shadow Update Rejected",
  "type": "object",
  "properties": {
    "code": { "type": "integer" },
    "message": { "type": "string" },
    "clientToken": { "type": "string" }
  },
  "required": ["code", "message"],
  "additionalProperties": False
}

delta_schema = {
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AWS IoT Shadow Delta",
  "type": "object",
  "properties": {
    "state": { "type": "object" },
    "metadata": { "type": "object" },
    "version": { "type": "integer" },
    "timestamp": { "type": "integer" }
  },
  "required": ["state", "version", "timestamp"],
  "additionalProperties": False
}

update_documents_schema = {
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AWS IoT Shadow Update Documents",
  "type": "object",
  "properties": {
    "previous": {
      "type": "object",
      "properties": {
        "state": {
          "type": "object",
          "properties": {
            "desired": { "type": "object" },
            "reported": { "type": "object" }
          },
          "additionalProperties": True
        },
        "metadata": {
          "type": "object",
          "properties": {
            "desired": { "type": "object" },
            "reported": { "type": "object" }
          },
          "additionalProperties": True
        },
        "version": { "type": "integer" },
        "timestamp": { "type": "integer" }
      },
      "required": ["state", "metadata", "version", "timestamp"],
      "additionalProperties": False
    },
    "current": {
      "type": "object",
      "properties": {
        "state": {
          "type": "object",
          "properties": {
            "desired": { "type": "object" },
            "reported": { "type": "object" }
          },
          "additionalProperties": True
        },
        "metadata": {
          "type": "object",
          "properties": {
            "desired": { "type": "object" },
            "reported": { "type": "object" }
          },
          "additionalProperties": True
        },
        "version": { "type": "integer" },
        "timestamp": { "type": "integer" }
      },
      "required": ["state", "metadata", "version", "timestamp"],
      "additionalProperties": False
    },
    "timestamp": { "type": "integer" }
  },
  "required": ["previous", "current", "timestamp"],
  "additionalProperties": False
}
