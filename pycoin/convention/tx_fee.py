import io

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
    s = io.BytesIO()
    tx.stream(s)

    in_tx = sum(1 for t in tx.txs_in)
    out_tx = sum(1 for t in tx.txs_out)

    # Are all outputs 0.01 BTC or larger.(Dust)
    no_dust = all(t.coin_value >= 1000000 for t in tx.txs_out)

    size_bytes = ((in_tx*148) + (out_tx*32) + 10)

    priority = 0

    try:
        priority = (sum(t.coin_value * t.confirmations for t in tx.unspents)) / size_bytes
    except TypeError:
        pass

    tx_byte_count = len(s.getvalue())

    # No fee are needed if we are above the treshold and
    # the transaction is less then 1000 bytes.
    if priority > TRESH_HOLD and tx_byte_count < 1000 and no_dust:
      return 0

    tx_fee = TX_FEE_PER_THOUSAND_BYTES * ((999+tx_byte_count)//1000)

    return tx_fee
