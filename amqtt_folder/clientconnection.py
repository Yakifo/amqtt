import mysql.connector 
from mysql.connector import errorcode
import logging
from diffiehellman import DiffieHellman

class ClientConnection: #session-based class, containig information about the current client session


    def __init__(self) -> None:

        self.logger = logging.getLogger(__name__)

        self.client_id: str = None
        self.client_spec_priv_key: str = None #these can be turned into bytes or completely removed later on
        self.client_spec_pub_key: str = None
        self.session_key: bytes = None
        self.key_establishment_state: int = 1 #start from one as default
        self.n1: int = 0
        self.n2: int = 0
        self.n3: int = 0
        self.dh: DiffieHellman(group=14, key_bits=2048) #bilgesu: key size increased ton 2048
        self.client_dh_public_key = None
        self.client_x509 = None
        self.disconnect_flag = False
        self.dh_shared_key = None
        self.nonce2 = None
        self.nonce1 = None
        self.nonce3 = None


    @property
    def return_private_key(self):
        return self.client_spec_priv_key
    
    @property
    def return_establishment_state(self):
        return self.key_establishment_state
    
    @property
    def return_session_key_with_client(self):
        return self.session_key
    
    @property
    def return_public_key(self):
        return self.client_spec_pub_key
    
    @property
    def return_client_id(self):
        return str(self.client_id)
    
    @property
    def return_dh(self):
        return self.dh
    
    
    

def pushRowToDatabase(client_id: str, edf_state: int, pub_key: str, priv_key: str) -> bool: #create database and create table can be removed and run seperately

    success = False

    mydb = mysql.connector.connect(
        host="127.0.0.1",
        user="root",
        password=""
    ) 
    mycursor = mydb.cursor()

    try:
        mycursor.execute("USE {}".format("brokerside"))
    except Exception as e:
        print("\n", e.args)
        #self.logger.debug("\n", e.args)


    sql_query = "INSERT INTO `clientsessions`(`client_id`, `edf_state`, `pub_key`, `priv_key`, `session_key`, `nonce_one`, `nonce_two`, `nonce_three`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
    val = (client_id, edf_state, pub_key, priv_key, None, None, None, None)

    #self.logger.debug("\nTrying to push data to table")
    #print("\nTrying to push data to table")
    try:
        mycursor.execute(sql_query, val)
        mydb.commit()
        success = True

    except mysql.connector.Error as err:

        #if-else unique to some errors can be added

        print("\nFailed pushing data: {}".format(err))
        #self.logger.debug("\nFailed pushing data: {}".format(err))


    finally:
        return success


def updateRowFromDatabase(client_id: str, edf_state: int, pub_key: str, priv_key: str, session_key: str, n1: int, n2: int, n3: int) -> bool:



    success = False

    mydb = mysql.connector.connect(
        host="127.0.0.1",
        user="root",
        password=""
    ) 
    mycursor = mydb.cursor()

    try:
        mycursor.execute("USE {}".format("brokerside"))
    except Exception as e:
        
        print("\n", e.args)
        #self.logger.debug("\n", e.args)

    sql_query = "UPDATE `clientsessions` SET `edf_state` = %s, `pub_key` = %s, `priv_key` = %s, `session_key` = %s, `nonce_one` = %s, `nonce_two` = %s, `nonce_three` = %s WHERE `client_id` = %s;"
    values = (edf_state, pub_key, priv_key, session_key, n1, n2, n3, client_id)

    #self.logger.debug("\nTrying to push data to table")
    #print("\nTrying to update data to table")
    try:
        mycursor.execute(sql_query, values)
        mydb.commit()
        success = True

    except mysql.connector.Error as err:

        #if-else unique to some errors can be added

        print("\nFailed updating data: {}".format(err))
        #self.logger.debug("\nFailed pushing data: {}".format(err))

    finally:
        return success


def deleteRowFromDatabase(client_id):
    success = False

    mydb = mysql.connector.connect(
        host="127.0.0.1",
        user="root",
        password=""
    ) 
    mycursor = mydb.cursor()

    try:
        mycursor.execute("USE {}".format("brokerside"))
    except Exception as e:
        
        print("\n", e.args)
        #self.logger.debug("\n", e.args)


    sql_query = "DELETE FROM `clientsessions` WHERE `client_id` = %s;"
    values = (client_id, )

    try:
        mycursor.execute(sql_query, values)
        mydb.commit()
        success = True

    except mysql.connector.Error as err:

        #if-else unique to some errors can be added

        print("\nFailed deletion: {}".format(err))

    finally:
        return success


#examples

'''
obj = ClientConnection()

obj.client_id = "dummyId"
obj.client_spec_priv_key = "dummyPrivKey"
obj.client_spec_pub_key = "dummyPubKey"
obj.session_key ="dummySesionKey"


print(obj)
print(obj.client_id)
print(obj.session_key)
'''

#pushRowToDatabase(obj.client_id, obj.key_establishment_state, obj.client_spec_pub_key, obj.client_spec_priv_key, obj.session_key)
#updateRowFromDatabase(obj.client_id, obj.key_establishment_state, obj.client_spec_pub_key, obj.client_spec_priv_key, "dummySessionKeyNewUpdate")
