import hashlib
import json
import requests

from textwrap import dedent
from time import time
from uuid import uuid4

from flask import Flask, jsonify, request
from urllib.parse import urlparse

class Blockchain(object):
    '''
    blockchain init:
    1) reload chain and transactions stack
    2) create genesis block
    '''
    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.nodes = set()

        #create the genesis block
        self.new_block(prev_hash=1, proof=100)
    #register new node as URL
    def register_node(self, address):
        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)
    '''
    1) try to equal block and last block hash
    2) try to equal proof and last block proof
    if one of them is FALSE - all chain FALSE
    '''
    def valid_chain(self, chain):
        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            print(f'{last_block}')
            print(f'{block}')
            print("\n-------------\n")

            if block['prev_hash'] != self.hash(last_block):
                return False

            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

            last_block = block

            current_index += 1

        return True
    '''
    method resolve some kind of conflicts
    1) call to neighbours
    2) get them chains
    3) equals length of chains
        3.1) if chain is longer, then need to verify chain
        3.2) if chain is valid, replace current chain and new chain
    4) if new chain is found, replace and return
    '''
    def resolve_conflicts(self):
        neighbours = self.nodes
        new_chain = None

        max_length = len(self.chain)

        for node in neighbours:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        if new_chain:
            self.chain = new_chain
            return True
        return False
    '''
    Create new block:
    1) create structured row of data
    2) reload transactions stack
    3) append new block to chain
    4) return new block
    '''
    def new_block(self, proof, prev_hash=None):
        #create new block and chain it
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'prev_hash': prev_hash or self.hash(self.chain[-1])
        }

        self.current_transactions = []
        self.chain.append(block)

        return block
    '''
    register new transaction in stack
    '''
    def new_transaction(self, sender, recipient, amount):
        #create new transaction to transaction list
        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount
        })

        return self.last_block['index'] + 1
    '''
    find PoW number, and return it
    '''
    def proof_of_work(self, last_proof):
        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1

        return proof
    '''
    Method check PoW
    '''
    @staticmethod
    def valid_proof(last_proof, proof):
        guess = f"{last_proof}{proof}".encode()
        guess_hash = hashlib.sha256(guess).hexdigest()

        return guess_hash[:4] == "0000"
    '''
    return hash of block
    '''
    @staticmethod
    def hash(block):
        #block hashing
        block_str = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_str).hexdigest()
    '''
    contain last block of chain
    '''
    @property
    def last_block(self):
        #return last chain block
        return self.chain[-1]

app = Flask(__name__)

node_id = str(uuid4()).replace('-', '')

blockchain = Blockchain()

@app.route('/test', methods=['GET'])
def isOnline():
    response = {
        'message': 'Node is online',
        'node': request.host
    }

    return jsonify(response), 200
@app.route('/mine', methods=['GET'])
def mine():
    last_block = blockchain.last_block
    last_proof = last_block['proof']

    proof = blockchain.proof_of_work(last_proof)

    blockchain.new_transaction(
        sender="0",
        recipient=node_id,
        amount=1
    )

    block = blockchain.new_block(proof)

    response = {
        'message': "New block forged",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'prev_hash': block['prev_hash']
    }
    return jsonify(response), 200

@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()

    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return 'Missing values', 400

    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])

    response = {'message': f'Transaction will be added to Block {index}'}
    return jsonify(response), 201

@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain)
    }
    return jsonify(response), 200
#register new node as URL
@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()

    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes)
    }

    return jsonify(response), 201
#resolve any problems
@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()
    if replaced:
        response = {
            'message': 'Chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Chain is verified',
            'chain': blockchain.chain
        }

    return jsonify(response), 200
if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='listened port')
    args = parser.parse_args()
    port = args.port

    app.run(host='127.0.0.1', port=port)