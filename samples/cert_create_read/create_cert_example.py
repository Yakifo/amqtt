from OpenSSL import crypto, SSL
from os.path import exists, join


def cert_gen():
    #can look at generated file using openssl:
    #openssl x509 -inform pem -in selfsigned.crt -noout -text
    # create a key pair

    emailAddress="emailAddress",
    commonName="commonName",
    countryName="TR",
    localityName="localityName",
    stateOrProvinceName="stateOrProvinceName",
    organizationName="organizationName",
    organizationUnitName="organizationUnitName",
    serialNumber=0,
    validityStartInSeconds=0,
    validityEndInSeconds=2*365*24*60*60,
    KEY_FILE = "private_1.key",
    CERT_FILE="selfsigned_example_1.crt"
    

    try:
        cert_dir="."
        C_F = join(cert_dir, CERT_FILE)
        K_F = join(cert_dir, KEY_FILE)
        if not exists(C_F) or not exists(K_F):
            k = crypto.PKey()
            print(k.bits)
            k.generate_key(crypto.TYPE_RSA, 4096)
           
            # create a self-signed cert

            try:
                cert = crypto.X509()
                cert.get_subject().C = countryName
                cert.get_subject().ST = stateOrProvinceName
                cert.get_subject().L = localityName
                cert.get_subject().O = organizationName
                cert.get_subject().OU = organizationUnitName
                cert.get_subject().CN = commonName
                cert.get_subject().emailAddress = emailAddress
                cert.set_serial_number(serialNumber)
                cert.gmtime_adj_notBefore(0)
                cert.gmtime_adj_notAfter(validityEndInSeconds)
                cert.set_issuer(cert.get_subject())
                cert.set_pubkey(k)
                cert.sign(k, 'sha512')



                with open(CERT_FILE, "wt") as f:
                    f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode("utf-8"))
                with open(KEY_FILE, "wt") as f:
                    f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k).decode("utf-8"))

            except:
         
               returnstr = "inner exception"
        else: 
            print("exist")
    except: 
        returnstr = "outer exception"

    
    

    

cert_gen()


