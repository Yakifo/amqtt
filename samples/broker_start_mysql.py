import logging    #for bring log information from mqtt broker
import asyncio    #to handle core routine function asyncronously
import os
from amqtt.broker import Broker
from amqtt.client import MQTTClient, ClientException
from amqtt.mqtt.constants import QOS_1
import mysql.connector 

logger = logging.getLogger(__name__)

config = {
    "listeners": {
        "default": {
            "type": "tcp",
            "bind": "0.0.0.0:1883"     #localhost:1883
        },
    },
    "sys_interval": 6000,
    "auth": {
        "allow-anonymous": True,
        "password-file": os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "passwd"
        ),
        "plugins": ["auth_file", "auth_anonymous"],
    },
    "topic-check": {
        "enabled": True,
        "plugins": ["topic_acl"] ,
        "acl": {
            "test": ["a/#"],
            "testpub1": ["a/b"],
            "anonymous":["#"]
            },
    },
}

broker = Broker(config)  


@asyncio.coroutine
def startBroker():
    yield from broker.start()

@asyncio.coroutine
def brokerGetMessage(): #for getting message from publisher
    C = MQTTClient()
    yield from C.connect('mqtt://localhost:1883/')
    yield from C.subscribe([
        ("topic/test", QOS_1)
    ])
    logger.info('Subscribed!')
    try:
        for i in range(1,100):
            message = yield from C.deliver_message()
            packet = message.publish_packet
            print(packet.payload.data.decode('utf-8'))
            mydb = mysql.connector.connect(
                host="127.0.0.1",
                user="root",
                password=""
            )
            mycursor = mydb.cursor()
            sql = '''insert into mqttpy (message) values (%s)'''
            val = str(packet.payload.data.decode('utf-8'))
            mycursor.execute("create database deneme")
            print("database created")
            #mydb.commit()
            #print(mydb.rowcount, 'Data saved!')
    except ClientException as ce:
        logger.error("Client exception : %s" % ce)

if __name__ == "__main__":   #it means when this broker_start.py executed, it will run
    formatter = "[%(asctime)s] :: %(levelname)s :: %(name)s :: %(message)s"  #formatter for our logging information
    # formatter = "%(asctime)s :: %(levelname)s :: %(message)s"
    #logging.basicConfig(level=logging.INFO, format=formatter)
    logging.basicConfig(level=logging.INFO, format=formatter)
    asyncio.get_event_loop().run_until_complete(startBroker())
    asyncio.get_event_loop().run_until_complete(brokerGetMessage())
    asyncio.get_event_loop().run_forever()
