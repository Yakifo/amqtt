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



