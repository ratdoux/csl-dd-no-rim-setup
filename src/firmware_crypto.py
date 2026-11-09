# SPDX-License-Identifier: AGPL-3.0-only
"""Offline Fanatec package extraction, based on ProjectSerotonin/vlfx.

Uses the Windows CryptoAPI recipe published in vlfx (AGPL-3.0), with an
ephemeral provider and correct returned plaintext lengths. Never opens a device.
Source: https://github.com/ProjectSerotonin/vlfx/blob/master/src/fanatec_decrypt.rs
"""
from pathlib import Path
import argparse, ctypes as C, hashlib, json, re, shutil, struct
from ctypes import wintypes as W

def decrypt(data):
    api = C.WinDLL('advapi32', use_last_error=True)
    H = C.c_size_t
    specs = {
        'CryptAcquireContextA': ([C.POINTER(H), C.c_char_p, C.c_char_p, W.DWORD, W.DWORD], W.BOOL),
        'CryptCreateHash': ([H,W.DWORD,H,W.DWORD,C.POINTER(H)],W.BOOL),
        'CryptHashData': ([H,C.c_void_p,W.DWORD,W.DWORD],W.BOOL),
        'CryptDeriveKey': ([H,W.DWORD,H,W.DWORD,C.POINTER(H)],W.BOOL),
        'CryptDecrypt': ([H,H,W.BOOL,W.DWORD,C.c_void_p,C.POINTER(W.DWORD)],W.BOOL),
        'CryptDestroyHash': ([H],W.BOOL), 'CryptDestroyKey': ([H],W.BOOL),
        'CryptReleaseContext': ([H,W.DWORD],W.BOOL),
    }
    for name,(args,ret) in specs.items():
        getattr(api,name).argtypes=args; getattr(api,name).restype=ret
    def call(name,*args):
        if not getattr(api,name)(*args): raise C.WinError(C.get_last_error())
    provider, digest, key = H(),H(),H()
    try:
        call('CryptAcquireContextA',C.byref(provider),None,b'Microsoft Enhanced RSA and AES Cryptographic Provider',24,0xF0000000)
        call('CryptCreateHash',provider,0x8003,0,0,C.byref(digest))
        password=b'!!endorfanatec!!'
        call('CryptHashData',digest,password,len(password),0)
        call('CryptDeriveKey',provider,0x660E,digest,0x800000,C.byref(key))
        result=bytearray()
        for off in range(0,len(data),100000):
            block=data[off:off+100000]; buf=C.create_string_buffer(block,len(block)); length=W.DWORD(len(block))
            call('CryptDecrypt',key,0,off+len(block)==len(data),0,buf,C.byref(length))
            result.extend(buf.raw[:length.value])
        return bytes(result)
    finally:
        if key.value: api.CryptDestroyKey(key)
        if digest.value: api.CryptDestroyHash(digest)
        if provider.value: api.CryptReleaseContext(provider,0)

def parse_hex(plain):
    memory={}; upper=0; counts={}; headers=[]; entry=None; eof=False
    for line in plain.decode('ascii').splitlines():
        line=line.strip()
        if not line: continue
        if not line.startswith(':'):
            if memory: raise ValueError('Unexpected non-HEX text after records')
            headers.append(line); continue
        record=bytes.fromhex(line[1:]); n=record[0]; addr=int.from_bytes(record[1:3],'big'); typ=record[3]; payload=record[4:-1]
        if len(record)!=n+5 or sum(record)&255: raise ValueError('Invalid Intel HEX length/checksum')
        counts[typ]=counts.get(typ,0)+1
        if eof: raise ValueError('Records after EOF')
        if typ==0:
            for i,b in enumerate(payload):
                a=upper+addr+i
                if a in memory and memory[a]!=b: raise ValueError('Conflicting HEX records')
                memory[a]=b
        elif typ==1: eof=True
        elif typ==2: upper=int.from_bytes(payload,'big')<<4
        elif typ==4: upper=int.from_bytes(payload,'big')<<16
        elif typ==5: entry=int.from_bytes(payload,'big')
        elif typ==3: entry=(int.from_bytes(payload[:2],'big')<<4)+int.from_bytes(payload[2:],'big')
        else: raise ValueError(f'Unsupported record type {typ}')
    if not eof: raise ValueError('No HEX EOF')
    ranges=[]
    for a in sorted(memory):
        if not ranges or a!=ranges[-1][1]: ranges.append([a,a+1])
        else: ranges[-1][1]=a+1
    return memory,dict(headers=headers,records=counts,entry=entry,eof=eof,ranges=ranges)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('source',type=Path); ap.add_argument('out',type=Path); args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    encrypted=args.source.read_bytes(); original=args.out/'original.encrypted.hex'; original.write_bytes(encrypted)
    plain=decrypt(encrypted); (args.out/'decrypted.hex').write_bytes(plain)
    print('Plaintext header:',repr(plain[:160]))
    memory,info=parse_hex(plain)
    records='\n'.join(line.strip() for line in plain.decode('ascii').splitlines() if line.strip().startswith(':'))+'\n'
    (args.out/'firmware.headerless.hex').write_text(records,encoding='ascii')
    info.update(source=str(args.source),encrypted_size=len(encrypted),plaintext_size=len(plain),encrypted_sha256=hashlib.sha256(encrypted).hexdigest(),plaintext_sha256=hashlib.sha256(plain).hexdigest())
    info['segments']=[]
    for lo,hi in info['ranges']:
        blob=bytes(memory[a] for a in range(lo,hi)); name=f'segment_{lo:08x}_{hi:08x}.bin'; (args.out/name).write_bytes(blob)
        info['segments'].append(dict(file=name,start=hex(lo),end_exclusive=hex(hi),length=len(blob),sha256=hashlib.sha256(blob).hexdigest(),head=blob[:64].hex()))
    (args.out/'manifest.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
    print(json.dumps(info,indent=2))

if __name__=='__main__': main()
