#!/usr/bin/env python3

import bitcoin
import bitcoin.rpc
from conf.coin import CoinParams
import argparse
import time

parser = argparse.ArgumentParser()
parser.add_argument("--height", help="set block height to start scan at")
args = parser.parse_args()

bitcoin.params = bitcoin.core.coreparams = CoinParams()
proxy = bitcoin.rpc.Proxy(btc_conf_file=bitcoin.params.CONF_FILE)


if args.height:
    height = args.height
else:
    height = 1

block = proxy.call('getblock', str(height))

while True:
    for tx in block['tx']:
        rawtx = proxy.call('getrawtransaction', tx)
        dtx = proxy.call('decoderawtransaction', rawtx)
        vout = dtx['vout']
        if len(vout) > 1:
            asm = vout[1]['scriptPubKey']['asm']
            if 'OP_RETURN' in asm:
                hex = asm[10:]
                try:
                    asmd = bytes.fromhex(hex).decode('ascii')
                    if 'REDEEM SCRIPT' in asmd:
                        addrs = []
                        for v in vout:
                            if 'addresses' in v['scriptPubKey']:
                                addrs.append(v['scriptPubKey']['addresses'])
                        data = {'txid': tx, 'height': block['height'], 'addresses': addrs}
                        print(data)
                except Exception as e:
                    # print(str(e))
                    pass
    if 'nextblockhash' in block:
        height = int(height) + 1
        block = proxy.call('getblock', str(height))
    else:
        time.sleep(60)