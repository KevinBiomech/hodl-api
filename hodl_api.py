#!/usr/bin/env python3

import requests, json
import bitcoin.rpc
from bitcoin.core import (
        b2x, b2lx, x, lx, COIN, COutPoint, CTxIn, CTxOut, CTransaction)
from bitcoin.core.script import (
        OP_NOP2, OP_DROP, OP_CHECKSIG, OP_RETURN, CScript)
from bitcoin.core.key import CPubKey
from bitcoin.wallet import (
        P2SHBitcoinAddress, CBitcoinAddress, P2PKHBitcoinAddress)
from binascii import unhexlify
from conf.coin import CoinParams

bitcoin.params = bitcoin.core.coreparams = CoinParams()


def tx_broadcast(rawtx):
    url = CoinParams.EXPLORER
    url += '/insight-api-komodo/tx/send'
    try:
        r = requests.post(
            url,
            headers = {'Content-type': 'application/json;charset=UTF-8'},
            json = {"rawtx": str(rawtx)}
        )
        try:
            explorer_output = json.loads(r.text)
            return(explorer_output)
        except:
            error_msg = r.text
            return({'error': error_msg})
    except Exception as e:
        print("Error trying to send transaction to " + url)
        error_msg = str(e)
        return({'error': error_msg})


def hodl_redeemScript(pubkey, nLockTime):
    publicKey = CPubKey(x(pubkey))
    return CScript([nLockTime, OP_NOP2, OP_DROP, publicKey, OP_CHECKSIG])


def create_command(pubkey, nLockTime):
    redeemScript = hodl_redeemScript(pubkey, nLockTime)
    addr = P2SHBitcoinAddress.from_redeemScript(redeemScript)
    return({'address': str(addr), 'redeemScript': b2x(redeemScript)})


def sendmany_command(payments):
    proxy = bitcoin.rpc.Proxy(btc_conf_file=bitcoin.params.CONF_FILE)
    txid = lx(proxy.sendmany("", payments).hex()).hex()
    return(txid)


def spend_command(pubkey, nLockTime, prevOuts):
    addr = P2PKHBitcoinAddress.from_pubkey(x(pubkey))
    address = addr
    redeemScript = hodl_redeemScript(pubkey, nLockTime)
    scriptPubKey = redeemScript.to_p2sh_scriptPubKey()
    proxy = bitcoin.rpc.Proxy(btc_conf_file=bitcoin.params.CONF_FILE)
    prevouts = []
    for prevout in prevOuts:
        try:
            txid, n = prevout.split(':')
            txid = lx(txid)
            n = int(n)
            outpoint = COutPoint(txid, n)
        except ValueError:
            raise Exception('Invalid output: %s' % prevout)
        try:
            prevout = proxy.gettxout(outpoint)
        except IndexError:
            raise Exception('Outpoint %s not found' % outpoint)
        prevout = prevout['txout']
        if prevout.scriptPubKey != scriptPubKey:
            raise Exception('Outpoint not correct scriptPubKey')
        prevouts.append((outpoint, prevout))

    sum_in = sum(prev_txout.nValue for outpoint, prev_txout in prevouts)

    tx_size = (4 +  # version field
               2 +  # number of txins
               len(prevouts) * 153 +  # txins, including sigs
               1 +  # number of txouts
               34 +  # txout
               4)  # nLockTime field

    feerate = int(proxy._call('estimatefee', 1) * COIN)  # satoshi's per KB
    if feerate <= 0:
        feerate = 10000
    fees = int(tx_size / 1000 * feerate)

    unsigned_tx = CTransaction(
        [CTxIn(outpoint, redeemScript, nSequence=0) for outpoint, prevout in prevouts],
        [CTxOut(sum_in - fees, address.to_scriptPubKey())],
        nLockTime)

    return({'redeemTransaction': b2x(unsigned_tx.serialize())})


def analyze_tx(tx_hex_string):
    output = {}

    # get op_return from transaction
    hex = unhexlify(tx_hex_string)
    deserializedTransaction = CTransaction.deserialize(hex)
    op_return_vout = deserializedTransaction.vout[1].scriptPubKey

    # get redeem script
    redeem_script = ''
    for i in op_return_vout:
        script = bytes(i).decode('utf8')
        if 'REDEEM' in script:
            redeem_script_string = script.replace('REDEEM SCRIPT ', '')
    output['redeemScript'] = redeem_script_string

    # convert redeem script into list
    redeemScript = CScript(unhexlify(redeem_script_string))
    redeem_script_array = []
    for i in redeemScript:
        redeem_script_array.append(i)

    # get redeem script hash (hodl address)
    p2sh_address = P2SHBitcoinAddress.from_redeemScript(redeemScript)
    output['hodlAddress'] = str(p2sh_address)

    # get nlocktime from redeem script
    nlocktime_hex = b2lx(redeem_script_array[0])
    nlocktime = int(nlocktime_hex, 16)
    output['nLockTime'] = nlocktime

    # get authorized key from redeem script
    pubkey = b2x(redeem_script_array[3])

    # get address from authorized key
    pubkey = unhexlify(pubkey)
    P2PKHBitcoinAddress = bitcoin.wallet.P2PKHBitcoinAddress
    addr = P2PKHBitcoinAddress.from_pubkey(pubkey)
    output['authorizedAddress'] = str(addr)

    # get total sent to hodl address
    locked_satoshis = 0
    for i in deserializedTransaction.vout:
        if i.nValue > 0:
            sPK = i.scriptPubKey
            amount = i.nValue
            try:
                vout_p2sh_addr = P2SHBitcoinAddress.from_scriptPubKey(sPK)
                # rewards only paid to really locked funds
                if str(p2sh_address) == str(vout_p2sh_addr):
                    locked_satoshis += amount
            except: pass
    output["lockedSatoshis"] = locked_satoshis

    return(output)


if __name__ == '__main__':
    print("HODL API")
