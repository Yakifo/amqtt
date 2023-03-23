import mysql.connector 
from mysql.connector import errorcode
from datetime import date
import datetime
import time



class ClientConnection: #session-based class, containin information about the current client session


    __slots__ = ("client_id", "key_establishment_state", "session_key", "client_spec_pub_key", "client_spec_priv_key")


    def __init__(self, client_id: str) -> None:

        self.client_id = client_id
        self.client_spec_priv_key = None
        self.client_spec_pub_key = None
        self.session_key = None
        self.key_establishment_state = 0

    @property
    def establishment_state(self):
        return self.key_establishment_state

    @establishment_state.setter
    def establishment_state(self, new_state: int):
        self.key_establishment_state = new_state


    @property
    def session_key_with_client(self):
        return self.session_key
    
    @session_key_with_client.setter
    def session_key_with_client(self, s_k: str):
        self.session_key = s_k



        #push to database


    @property
    def public_key(self):
        return self.client_spec_pub_key
    
    @public_key.setter
    def public_key(self, public_key_generated):
        self.client_spec_pub_key = public_key_generated


    @property
    def private_key(self):
        return self.client_spec_priv_key
    
    @private_key.setter
    def private_key(self, private_key_generated):
        self.client_spec_priv_key = private_key_generated

    @classmethod
    def pushRowToDatabase(self):

        mydb = mysql.connector.connect(
            host="127.0.0.1",
            user="root",
            password=""
        ) 
        mycursor = mydb.cursor()

        try:
            mycursor.execute("CREATE DATABASE brokerside")
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_DB_CREATE_EXISTS:
                print("Database already exists.")
            else:
                print("Create DB error ", err)


        try:
            mycursor.execute("USE {}".format("brokerside"))
        except Exception as e:
            print(e.args)
        
        clientsessions = (
            "CREATE TABLE `clientsessions` ("
            "  `client_id` varchar(32) NOT NULL,"
            "  `edf_state` int NOT NULL,"
            "  `pub_key` varchar(2048) NULL,"
            "  `priv_key` varchar(2048) NULL,"
            "  `session_key` varchar(2048) NULL,"
            "  PRIMARY KEY (`client_id`)"
        ") ENGINE=InnoDB")
                
        
        print("Trying to create table {}: ".format(clientsessions), end='')
        try:
            mycursor.execute(clientsessions)

        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_TABLE_EXISTS_ERROR:
                print("Table already exists.")
            else:
                print("Create table error ", err)

        sql_query = "INSERT INTO `clientsessions`(`client_id`, `edf_state`, `pub_key`, `priv_key`, `session_key`) VALUES (%s, %s, %s, %s, %s)"
        val = (self.client_id, self.key_establishment_state, self.client_spec_pub_key, self.client_spec_priv_key, self.session_key)

        print("Trying to push data to table")
        try:
            mycursor.execute(sql_query, val)
            mydb.commit()

        except mysql.connector.Error as err:

            #if-else unique to some errors can be added

            print("Failed pushing data: {}".format(err))




