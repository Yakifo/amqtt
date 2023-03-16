import logging    #for bring log information from mqtt broker
import asyncio    #to handle core routine function asyncronously
import os
from amqtt.broker import Broker
from amqtt.client import MQTTClient, ClientException
from amqtt.mqtt.constants import QOS_1
import mysql.connector 
from mysql.connector import errorcode

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
def connectToDatabaseAndAddTable():
    print("in connectToDatabaseAndAddTable")

    mydb = mysql.connector.connect(
                host="127.0.0.1",
                user="root",
                password=""
            )

    mycursor = mydb.cursor()

    try:
        mycursor.execute("create database deneme")
    except mysql.connector.Error as err:

        if err.errno == errorcode.ER_DB_CREATE_EXISTS:
            print("database already exists.")

            try:
                mycursor.execute("USE {}".format("deneme"))
            except Exception as e:
                print(e.args)

            TABLES = {}
            TABLES['incomingmessages'] = (
                "CREATE TABLE `incomingmessages` ("
                "  `client_id` int(20) NOT NULL,"
                "  `topic` varchar(50) NOT NULL,"
                "  `message` varchar(100) NOT NULL,"
                "  `received_date` date NOT NULL,"
                "  PRIMARY KEY (`client_id`,`received_date`)"
                ") ENGINE=InnoDB")
            
            for table_name in TABLES:
                table_description = TABLES[table_name]
                
                try:
                    print("Creating table {}: ".format(table_name), end='')
                    mycursor.execute(table_description)

                except mysql.connector.Error as err:
                    if err.errno == errorcode.ER_TABLE_EXISTS_ERROR:
                        print("already exists.")
                    else:
                        print(err.msg)
                else:
                    print("OK")

        else:
            print("Failed creating database: {}".format(err))
            exit(1)


@asyncio.coroutine
def pushDataTodatabase(cli_id, topic, mesg, recevied_at):

    mydb = mysql.connector.connect(
                host="127.0.0.1",
                user="root",
                password=""
            )

    mycursor = mydb.cursor()

    mycursor.execute("USE {}".format("deneme"))

    sql_query = ""

    try:
        print("Pushing data to table \"incomingmessages\"")
        mycursor.execute(sql_query)

    except mysql.connector.Error as err:

        #if-else unique to some errors can be added

        print("Failed pushing data: {}".format(err))
    else:
        print("pushed to table succesfully")





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
            print(packet, "packet var")
            print(packet.payload.data.decode('utf-8'))
            mydb = mysql.connector.connect(
                host="127.0.0.1",
                user="root",
                password=""
            )
            mycursor = mydb.cursor()
            #sql = '''insert into mqttpy (message) values (%s)'''
            #val = str(packet.payload.data.decode('utf-8'))
            
            #mycursor.execute("create database deneme")
            #print("database created")
            
            #mydb.commit()
            #print(mydb.rowcount, 'Data saved!')

            #add a way to access the client id
    except ClientException as ce:
        logger.error("Client exception : %s" % ce)

if __name__ == "__main__":   #it means when this broker_start.py executed, it will run
    formatter = "[%(asctime)s] :: %(levelname)s :: %(name)s :: %(message)s"  #formatter for our logging information
    # formatter = "%(asctime)s :: %(levelname)s :: %(message)s"
    #logging.basicConfig(level=logging.INFO, format=formatter)
    logging.basicConfig(level=logging.INFO, format=formatter)
    asyncio.get_event_loop().run_until_complete(startBroker())
    asyncio.get_event_loop().run_until_complete(connectToDatabaseAndAddTable())
    asyncio.get_event_loop().run_until_complete(brokerGetMessage())
    asyncio.get_event_loop().run_forever()
