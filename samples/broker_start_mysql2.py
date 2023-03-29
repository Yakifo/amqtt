import logging    #for bring log information from mqtt broker
import asyncio    #to handle core routine function asyncronously
import os
from amqtt_folder.broker import Broker
from amqtt_folder.client import MQTTClient, ClientException
from amqtt_folder.mqtt.constants import QOS_1
import mysql.connector 
from mysql.connector import errorcode
from datetime import date
import datetime
import time

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


async def startBroker():
    await broker.start()

@asyncio.coroutine
def connectDB():
    mydb = mysql.connector.connect(
            host="127.0.0.1",
            user="root",
            password=""
        ) 
    mycursor = mydb.cursor()

    try:
        mycursor.execute("CREATE DATABASE deneme")
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_DB_CREATE_EXISTS:
            print("database already exists.")
        else:
            print("Create DB error ", err)


    try:
        mycursor.execute("USE {}".format("deneme"))
    except Exception as e:
        print(e.args)
    
    incomingmessages = (
        "CREATE TABLE `incomingmessages` ("
        "  `client_id` varchar(20) NOT NULL,"
        "  `topic` varchar(50) NOT NULL,"
        "  `message` varchar(100) NOT NULL,"
        "  `received_date` date NOT NULL,"
        "  PRIMARY KEY (`client_id`,`received_date`)"
    ") ENGINE=InnoDB")
            
    
    print("Trying to create table {}: ".format(incomingmessages), end='')
    try:
        mycursor.execute(incomingmessages)

    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_TABLE_EXISTS_ERROR:
            print("table already exists.")
        else:
            print("Create table error ", err)

    today = date.today()
    print("will call push data")
    try:
        pushDataTodatabase("dummy2", "topic/subtopic", "dummy message", today)
        pushDataTodatabase("dummy3", "topic/subtopic", "dummy message", today)
        pushDataTodatabase("dummy4", "topic/subtopic", "dummy message", today)
    except Exception as exc:
        print("exception trhown when pushing dummy data to database")
        print(exc.args)



def pushDataTodatabase(cli_id, topic, mesg, recevied_at):

    mydb = mysql.connector.connect(
                host="127.0.0.1",
                user="root",
                password=""
            )

    mycursor = mydb.cursor()

    mycursor.execute("USE {}".format("deneme"))



    ts = time.time()

    str_time = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')



    sql_query = "INSERT INTO `incomingmessages`(`client_id`, `topic`, `message`, `received_date`) VALUES (%s, %s, %s, %s)"
    val = (cli_id, topic, mesg, str_time)

    print("Trying to push data to table \"incomingmessages\"")
    try:
        mycursor.execute(sql_query, val)
        mydb.commit()

    except mysql.connector.Error as err:

        #if-else unique to some errors can be added

        print("Failed pushing data: {}".format(err))


async def brokerGetMessage(): #for getting message from publisher
    C = MQTTClient()
    await C.connect('mqtt://localhost:1883/')
    await C.subscribe([
        ("topic/test", QOS_1)
    ])
    logger.info('Subscribed!')
    try:
        for i in range(1,100):
            message = await C.deliver_message()

            packet = message.publish_packet
            print(packet.payload.data.decode('utf-8'))
            #add a way to access the client id
    except ClientException as ce:
        logger.error("Client exception : %s" % ce)

if __name__ == "__main__":   #it means when this broker_start.py executed, it will run
    formatter = "[%(asctime)s] :: %(levelname)s :: %(name)s :: %(message)s"  #formatter for our logging information
    #logging.basicConfig(level=logging.INFO, format=formatter)
    logging.basicConfig(level=logging.INFO, format=formatter)
    asyncio.get_event_loop().run_until_complete(startBroker())
    asyncio.get_event_loop().run_until_complete(connectDB())
    asyncio.get_event_loop().run_until_complete(brokerGetMessage())
    asyncio.get_event_loop().run_forever()
