# provide support to insight API servers
# see also https://github.com/bitpay/insight-api

import decimal
import json
import logging
import io

try:
    from urllib2 import HTTPError, urlopen
    from urllib import urlencode
except ImportError:
    from urllib.request import urlopen
    from urllib.error import HTTPError
    from urllib.parse import urlencode

from pycoin.block import BlockHeader
from pycoin.convention import btc_to_satoshi
from pycoin.encoding import double_sha256
from pycoin.merkle import merkle
from pycoin.serialize import b2h, b2h_rev, h2b, h2b_rev
from pycoin.tx.script import tools
from pycoin.tx import Spendable, Tx, TxIn, TxOut


class InsightService(object):
    def __init__(self, base_url):
        while base_url[-1] == '/':
            base_url = base_url[:-1]
        self.base_url = base_url

    def get_blockchain_tip(self):
        URL = "%s/api/status?q=getLastBlockHash" % self.base_url
        d = urlopen(URL).read().decode("utf8")
        r = json.loads(d)
        return h2b_rev(r.get("lastblockhash"))

    def get_blockheader(self, block_hash):
        return self.get_blockheader_with_transaction_hashes(block_hash)[0]

    def get_blockheader_with_transaction_hashes(self, block_hash):
        URL = "%s/api/block/%s" % (self.base_url, b2h_rev(block_hash))
        r = json.loads(urlopen(URL).read().decode("utf8"))
        version = r.get("version")
        previous_block_hash = h2b_rev(r.get("previousblockhash"))
        merkle_root = h2b_rev(r.get("merkleroot"))
        timestamp = r.get("time")
        difficulty = int(r.get("bits"), 16)
        nonce = int(r.get("nonce"))
        tx_hashes = [h2b_rev(tx_hash) for tx_hash in r.get("tx")]
        blockheader = BlockHeader(version, previous_block_hash, merkle_root, timestamp, difficulty, nonce)
        if blockheader.hash() != block_hash:
            return None, None
        calculated_hash = merkle(tx_hashes, double_sha256)
        if calculated_hash != merkle_root:
            return None, None
        blockheader.height = r.get("height")
        return blockheader, tx_hashes

    def get_block_height(self, block_hash):
        return self.get_blockheader_with_transaction_hashes(block_hash)[0].height

    def get_tx(self, tx_hash):
        URL = "%s/api/tx/%s" % (self.base_url, b2h_rev(tx_hash))
        r = json.loads(urlopen(URL).read().decode("utf8"))
        tx = tx_from_json_dict(r)
        if tx.hash() == tx_hash:
            return tx
        return None

    def get_tx_dict(self, tx_hash):
        d = {}
        URL = "%s/api/tx/%s" % (self.base_url, tx_hash)
        r = json.loads(urlopen(URL).read().decode("utf8"))
        try:
            d['confirmations'] = r['confirmations']
        except KeyError:
            d['confirmations'] = -1
        d['fee'] = btc_to_satoshi(r['fees'])
        d['amount'] = btc_to_satoshi(r['valueIn'])
        return d

    def get_tx_confirmation_block(self, tx_hash):
        return self.get_tx(tx_hash).confirmation_block_hash

    def address_received(self, bitcoin_address):
        URL = "%s/api/addr/%s/totalReceived" % (self.base_url, bitcoin_address)
        r = json.loads(urlopen(URL).read().decode("utf8"))
        return r

    def address_sent(self, bitcoin_address):
        URL = "%s/api/addr/%s/totalSent" % (self.base_url, bitcoin_address)
        r = json.loads(urlopen(URL).read().decode("utf8"))
        return r

    def address_balance(self, bitcoin_address):
        URL = "%s/api/addr/%s/balance" % (self.base_url, bitcoin_address)
        r = json.loads(urlopen(URL).read().decode("utf8"))
        return r

    def address_unconfirmed_balance(self, bitcoin_address):
        URL = "%s/api/addr/%s/unconfirmedBalance" % (self.base_url, bitcoin_address)
        r = json.loads(urlopen(URL).read().decode("utf8"))
        return r

    def spendables_for_address(self, bitcoin_address):
        """
        Return a list of Spendable objects for the
        given bitcoin address.
        """
        URL = "%s/api/addr/%s/utxo?noCache=1" % (self.base_url, bitcoin_address)
        r = json.loads(urlopen(URL).read().decode("utf8"))
        spendables = []
        for u in r:
            coin_value = btc_to_satoshi(str(u.get("amount")))
            script = h2b(u.get("scriptPubKey"))
            previous_hash = h2b_rev(u.get("txid"))
            previous_index = u.get("vout")
            confirmations = u.get("confirmations")
            spendables.append(Spendable(coin_value, script, previous_hash, previous_index,confirmations=confirmations))
        return spendables

    def spendables_for_addresses(self, bitcoin_addresses):
        addresses = ','.join(bitcoin_addresses)
        URL = "%s/api/addrs/%s/utxo?noCache=1" % (self.base_url, addresses)
        r = json.loads(urlopen(URL).read().decode("utf8"))
        spendables = []
        for u in r:
            coin_value = btc_to_satoshi(str(u.get("amount")))
            script = h2b(u.get("scriptPubKey"))
            previous_hash = h2b_rev(u.get("txid"))
            previous_index = u.get("vout")
            confirmations = u.get("confirmations")
            spendables.append(Spendable(coin_value, script, previous_hash, previous_index,confirmations=confirmations))
        return spendables

    def send_tx(self, tx):
        s = io.BytesIO()
        tx.stream(s)
        tx_as_hex = b2h(s.getvalue())
        data = urlencode(dict(rawtx=tx_as_hex)).encode("utf8")
        URL = "%s/api/tx/send" % self.base_url
        try:
            d = urlopen(URL, data=data).read()
            return d
        except HTTPError as err:
            if err.code == 400:
                raise ValueError(err.readline())
            raise err

    def is_address_used(self, bitcoin_address):
        """
        Return True if the bitcoin_address never has been
        part of a transaction.
        """
        URL = "%s/api/addr/%s" % (self.base_url, bitcoin_address)
        r = json.loads(urlopen(URL).read().decode("utf8"))
        return len(r['transactions']) != 0

    def has_unconfirmed_balance(self, bitcoin_addresses):
        """
        Return True if any of the bitcoin addresses has unconfirmed
        balance. False otherwise
        """
        for addr in bitcoin_addresses:
            URL = "%s/api/addr/%s/unconfirmedBalance" % (self.base_url, addr)
            r = json.loads(urlopen(URL).read().decode("utf8"))
            if r > 0:
                return True
        return False


def tx_from_json_dict(r):
    version = r.get("version")
    lock_time = r.get("locktime")
    txs_in = []
    for vin in r.get("vin"):
        if "coinbase" in vin:
            previous_hash = b'\0' * 32
            script = h2b(vin.get("coinbase"))
            previous_index = 4294967295
        else:
            previous_hash = h2b_rev(vin.get("txid"))
            script = tools.compile(vin.get("scriptSig").get("asm"))
            previous_index = vin.get("vout")
        sequence = vin.get("sequence")
        txs_in.append(TxIn(previous_hash, previous_index, script, sequence))
    txs_out = []
    for vout in r.get("vout"):
        coin_value = btc_to_satoshi(decimal.Decimal(vout.get("value")))
        script = tools.compile(vout.get("scriptPubKey").get("asm"))
        txs_out.append(TxOut(coin_value, script))
    tx = Tx(version, txs_in, txs_out, lock_time)
    bh = r.get("blockhash")
    if bh:
        bh = h2b_rev(bh)
    tx.confirmation_block_hash = bh
    return tx
