import io
from pycoin.tx.Tx import Tx

TX_FEE_PER_THOUSAND_BYTES = 10000


def recommended_fee_for_tx(tx):
    """
    https://bitcointalk.org/index.php?topic=648769.0

    Return the recommended transaction fee in satoshis.
    This is a grossly simplified version of this function.
    TODO: improve to consider TxOut sizes.
      - whether the transaction contains "dust"
      - whether any outputs are less than 0.001
      - update for bitcoind v0.90 new fee schedule
    """
    TRESH_HOLD = 57600000
    in_tx = sum(1 for t in tx.txs_in)
    out_tx = sum(1 for t in tx.txs_out)

    size_bytes = ((in_tx*148) + (out_tx*32) + 10)
    priority = 0
    for t in tx.unspents:
      priority += t.coin_value * t.confirmations

    value = priority / size_bytes

    s = io.BytesIO()
    tx.stream(s)
    tx_byte_count = len(s.getvalue())
    tx_fee = TX_FEE_PER_THOUSAND_BYTES * ((999+tx_byte_count)//1000)

    # No fee are needed if we are above the treshold and
    # the transaction is less then 1000 bytes.
    if value > TRESH_HOLD and tx_byte_count < 1000:
      return 0

    return tx_fee
