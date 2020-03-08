"""
This is a basic implementation of a client for a cryptocurrency
"""

import socket
import sys
import threading
from blockchain import Transaction
from blockchain import TransactionOutput
from blockchain import TransactionInput
from blockchain import Block
from Crypto.PublicKey import ECC
from Crypto.Hash import RIPEMD160
import os

class P2PNetwork(object):
    peers = ['127.0.0.1']


def update_peers(peers_string):
    P2PNetwork.peers = peers_string.split(',')[:-1]


class Client(object):

    def __init__(self, address):
        """
        Initialization method for Client class

        Convention:
        0x10 - New Transaction
        0x11 - New peers
        0x12 - New mined block
        """

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Make the connection
        self.socket.connect((address, 5000))
        self.byte_size = 1024
        self.peers = []
        print('==> Connected to server.')

        self.generate_key_pair()

        client_listener_thread = threading.Thread(target=self.send_message)
        client_listener_thread.start()

        while True:
            try:
                data = self.receive_message()
                if not data:
                    print("==> Server disconnected.")
                    break
                elif data[0:1] == '\x11':
                    print('==> Got peers.')
                    update_peers(data[1:])
                elif data[0:1] == '\x10':
                    print('==> New transaction')
                    print(data[1:])
                else:
                    print("[#] " + data)
            except ConnectionError as error:
                print("==> Server disconnected.")
                print('\t--' + str(error))
                break

    # BE CAREFUL !! THIS METHOD IS FOR DEMONSTRATIONS ONLY. In a real implementation, this method does not exists.
    def create_coin_gift(self, blockchain):
        # Get address of the client
        route_public_key = "public_keys/" + str(self.socket.getsockname()[1]) + "_public_key.pem"
        file_public_key = open(route_public_key, "wt")
        public_key = file_public_key.read()

        hash_object = RIPEMD160.new(public_key)
        hash_public_key = hash_object.hexdigest()

        coin_gift_tx_input = TransactionInput(prev_tx="0" * 64, pk_spender="0" * 64)
        coin_gift_tx_output = TransactionOutput(value=100, hash_pubkey_recipient=hash_public_key)
        coin_gift_tx = Transaction(tx_input=coin_gift_tx_input, tx_output=coin_gift_tx_output)

        transactions = [coin_gift_tx]

        nonce = 0
        while True:
            if len(blockchain.blocks) != 0:
                hash_prev_block = blockchain.blocks[len(blockchain.blocks) - 1].get_hash()
                new_block = Block(transactions, nonce, hash_prev_block)
            else:
                new_block = Block(transactions=transactions, nonce=nonce, prev_block_hash="0" * 64)

            if new_block.get_hash().startswith("0" * blockchain.difficulty):
                print("Nonce found:", nonce)
                return new_block

            nonce += 1

        message = "\x12" + block.serialize()
        self.socket.send(message.encode('utf-8'))

    def generate_key_pair(self):
        """
        Generate key pairs for this client using elliptic curves, in particular, it uses secp256r1 elliptic curve
        """
        print("==> Generating key pairs.")

        route_private_key = "private_keys/" + str(self.socket.getsockname()[1]) + "_private_key.pem"
        route_public_key = "public_keys/" + str(self.socket.getsockname()[1]) + "_public_key.pem"

        key = ECC.generate(curve="secp256r1")
        file_private_key = open(route_private_key, "wt")
        file_private_key.write(key.export_key(format="PEM"))

        file_public_key = open(route_public_key, "wt")
        file_public_key.write(key.public_key().export_key(format="PEM"))

        print("==> Key pairs generated.")
        print("\t" + route_private_key)
        print("\t" + route_public_key)

    def send_message(self):
        while True:
            input_command = input()

            # This variable is set to True when is a server command
            send_message_to_server = True

            # TODO Correct transaction sending
            if input_command.startswith("cmd_new_tx"):
                input_command_split = input_command.split()
                input_btc = int(input_command_split[1])
                output_btc = int(input_command_split[2])
                address = str(input_command_split[3])

                transaction = Transaction(input_btc, output_btc)
                message = "\x10" + transaction.serialize()

            elif input_command.startswith("cmd_show_addresses"):
                # This is not a server command
                send_message_to_server = False

                base_path = "public_keys/"
                for file in os.listdir(base_path):
                    pubkey_file = open(base_path + file)
                    pubkey = pubkey_file.read()

                    hash_object = RIPEMD160.new(data=pubkey.encode("utf-8"))
                    print("\t>>", hash_object.hexdigest(), "[", file, "]")

                    pubkey_file.close()

            elif input_command.startswith("cmd_gift"):
                self.create_coin_gift()
            else:
                message = input_command

            if send_message_to_server:
                self.socket.send(message.encode('utf-8'))

    def receive_message(self):
        try:
            data = self.socket.recv(self.byte_size)
            return data.decode('utf-8')
        except KeyboardInterrupt:
            self.send_disconnect_signal()

    def send_disconnect_signal(self):
        print('==> Disconnected from server.')
        self.socket.send("q".encode('utf-8'))
        sys.exit()


class Server(object):

    def __init__(self, byte_size):
        try:

            # List with connections to the server
            self.connections = []

            # List of peers connected
            self.peers = []

            # Socket instantiation and setup
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Bind socket to local host
            self.socket.bind(('127.0.0.1', 5000))

            self.socket.listen(1)

            self.byte_size = byte_size

            print('==> Server running.')

            # Listen to new connections
            # TODO Send the blockchain when a new client is connected
            while True:
                connection_handler, ip_port_tuple = self.socket.accept()

                # Add the new peer and send to clients the new list
                self.peers.append(ip_port_tuple)
                self.send_peers()
                self.connections.append(connection_handler)

                # Initialize the handler thread
                handler_thread = threading.Thread(target=self.handler, args=(connection_handler, ip_port_tuple,))
                handler_thread.daemon = True
                handler_thread.start()

                print('==> {} connected.'.format(ip_port_tuple))

        except Exception as exception:
            print(exception)
            sys.exit()

    def handler(self, connection_handler, ip_port_tuple):
        try:
            while True:
                data = connection_handler.recv(self.byte_size)
                # Check if the peer wants to disconnect
                for connection in self.connections:
                    if data and data.decode('utf-8') == 'cmd_show_peers':
                        connection.send(('---' + str(self.peers)).encode('utf-8'))
                    elif data:
                        connection.send(data)
        except ConnectionResetError:
            print("==> " + str(ip_port_tuple) + " disconnected")
            self.connections.remove(connection_handler)
            connection_handler.close()
            self.peers.remove(ip_port_tuple)
            self.send_peers()

    def send_peers(self):
        peer_list = ""
        for peer in self.peers:
            peer_list += str(peer[0]) + ','

        for connection in self.connections:
            connection.send(bytes('\x11' + peer_list, 'utf-8'))

        print('==> Peers sent.')


class Miner(object):
    # TODO implement Miner
    pass