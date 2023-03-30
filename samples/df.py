import nacl.utils
from nacl.public import PrivateKey, Box
from diffiehellman import DiffieHellman

def df():


    # automatically generate two key pairs
    dh1 = DiffieHellman(group=14, key_bits=540)
    dh2 = DiffieHellman(group=14, key_bits=540)
    

    # get both public keys
    dh1_public = dh1.get_public_key()
    dh2_public = dh2.get_public_key()
    print("dh1_public", dh1_public)
    print("dh2_public" , dh2_public)

    # generate shared key based on the other side's public key
    dh1_shared = dh1.generate_shared_key(dh2_public)
    dh2_shared = dh2.generate_shared_key(dh1_public)
    print("dh1_shared",dh1_shared)
    print("dh2_shared",dh2_shared)



    # the shared keys should be equal
    assert dh1_shared == dh2_shared

    

if __name__ == "__main__":
    df()