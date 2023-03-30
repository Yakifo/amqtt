from OpenSSL import crypto, SSL
from cryptography import x509
from OpenSSL.crypto import (load_certificate, dump_privatekey, dump_certificate, X509, X509Name, PKey)
from OpenSSL.crypto import (TYPE_DSA, TYPE_RSA, FILETYPE_PEM, FILETYPE_ASN1 )
from datetime import datetime
import textwrap


def format_subject_issuer(x509name):
    items = []
    for item in x509name.get_components():
        items.append('%s=%s' %  (item[0], item[1]) )
    return ", ".join(items);
 
def format_split_bytes(aa):
    print("aa:", aa)
    bb = aa[1:] if len(aa)%2==1 else aa #force even num bytes, remove leading 0 if necessary

    print("bb:", bb)
    out = format(':'.join(s.encode('hex').lower() for s in bb.decode('hex')))
    return out
 
def format_split_int(serial_number):
    aa = "0%x" % serial_number #add leading 0
    return format_split_bytes(aa)
 
def format_asn1_date(d):
    return datetime.strptime(d.decode('ascii'), '%Y%m%d%H%M%SZ').strftime("%Y-%m-%d %H:%M:%S GMT")

 


def read_cert(cert_file_name):
    

    with open(cert_file_name, 'rb+') as f:
        x509 = "None"
        try: 
            cert_pem = f.read()
            f.close()

            x509 = load_certificate(FILETYPE_PEM, cert_pem)

            keytype = x509.get_pubkey().type()
            keytype_list = {TYPE_RSA:'rsaEncryption', TYPE_DSA:'dsaEncryption', 408:'id-ecPublicKey'}
            key_type_str = keytype_list[keytype] if keytype in keytype_list else 'other'
    
            pkey_lines=[]
            pkey_lines.append("        Public Key Algorithm: %s" % key_type_str)
            pkey_lines.append("            Public-Key: (%s bit)" % x509.get_pubkey().bits())

            pubkeyobj = x509.get_pubkey()

            pubkeystr = crypto.dump_publickey(crypto.FILETYPE_PEM, pubkeyobj)
    
            print("Certificate:")
            print("    Data:")
            print("        Version: %s (0x%x)" % (int(x509.get_version()+1), x509.get_version()) )
            print("        Serial Number:")
            print("            %s" % x509.get_serial_number())
            print("    Signature Algorithm: %s" % x509.get_signature_algorithm())
            print("    Issuer: %s" % format_subject_issuer( x509.get_issuer() ) )
            print("    Validity")
            print("        Not Before: %s" % format_asn1_date(x509.get_notBefore()))
            print("        Not After : %s" % format_asn1_date(x509.get_notAfter()))
            print("    Subject: %s" % format_subject_issuer( x509.get_subject() ) )
            print("    Subject Public Key Info:")
            print("pub key:\n", pubkeystr,  "\n")
            print("\n".join(pkey_lines))
            print("        X509v3 extensions:")
            for i in range(x509.get_extension_count()):
                critical = 'critical' if x509.get_extension(i).get_critical() else ''
                print("             x509v3 %s: %s" % (x509.get_extension(i).get_short_name(), critical) )
                print("                 %s" % x509.get_extension(i).__str__() )
            print("    Signature Algorithm: %s" % x509.get_signature_algorithm() )

            print("    Thumbprint MD5:    %s" % x509.digest('md5'))
            print("    Thumbprint SHA1:   %s" % x509.digest('sha1'))
            print("    Thumbprint SHA256: %s" % x509.digest('sha256'))
        except: 
            print("Exceprtion occured when reading certificate")
            x509 = "None"
 
      

    return x509



#read_cert("selfsigned_example_1.crt")

