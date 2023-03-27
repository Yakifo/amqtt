import mysql.connector 
from mysql.connector import errorcode


def createDatabaseAndDatabaseTables():
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
            #self.logger.debug("\nDatabase already exists.")
            print("\nDatabase already exists.")
        else:
            #self.logger.debug("\nCreate DB error ", err)
            print("\nCreate DB error ", err)


    try:
        mycursor.execute("USE {}".format("brokerside"))
    except Exception as e:
        print("\n", e.args)
        #self.logger.debug("\n", e.args)
            
    clientsessions = (
        "CREATE TABLE `clientsessions` ("
        "  `client_id` varchar(32) NOT NULL,"
        "  `edf_state` int NOT NULL,"
        "  `pub_key` varchar(2048) NULL,"
        "  `priv_key` varchar(2048) NULL,"
        "  `session_key` varchar(2048) NULL,"
        "  PRIMARY KEY (`client_id`)"
    ") ENGINE=InnoDB")
                    
            
    #self.logger.debug("\nTrying to create table {}: ".format(clientsessions), end='')
    print("\nTrying to create table {}: ".format(clientsessions), end='')
    try:
        mycursor.execute(clientsessions)

    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_TABLE_EXISTS_ERROR:
            print("\nTable already exists.")
            #self.logger.debug("\nTable already exists.")
        else:
            print("\nCreate table error ", err)
            #self.logger.debug("\nCreate table error ", err)



#run this py to create the database and added tables 
#currently there exists one table in this part but more table create statements can be added if needed
createDatabaseAndDatabaseTables()