"""Conservative FNC boxer merge for the observed 83-slot Xbox 360 save layout."""
import hashlib
import struct
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes

class SaveError(ValueError):
    pass

def require(condition, message):
    if not condition:
        raise SaveError(message)

def sha(data):
    return hashlib.sha1(data).digest()

def forms(data):
    return [data, data[::-1], b''.join(data[i:i+8] for i in range(len(data)-8, -1, -8)),
            b''.join(data[i:i+8][::-1] for i in range(0, len(data), 8))]

def verify_signature(data):
    for modulus in forms(data[0x2c:0xac]):
        try:
            key = rsa.RSAPublicNumbers(int.from_bytes(data[0x28:0x2c], 'big'), int.from_bytes(modulus, 'big')).public_key()
        except ValueError:
            continue
        for signature in forms(data[0x1ac:0x22c]):
            try:
                key.verify(signature, bytes(data[0x22c:0x344]), padding.PKCS1v15(), hashes.SHA1())
                return True
            except Exception:
                continue
    return False

class Package:
    def __init__(self, data):
        self.data = bytearray(data)
        b = self.data
        require(0xa000 <= len(b) <= 64000000 and b[:4] == b'CON ', 'Choose a native Xbox 360 CON boxer save, not a ZIP, profile, or career save.')
        self.be = lambda o,n: int.from_bytes(b[o:o+n], 'big')
        self.le = lambda o,n: int.from_bytes(b[o:o+n], 'little')
        self.base = (self.be(0x340,4)+4095)&~4095
        self.sep = b[0x37b]
        self.sex = (~self.sep)&1
        self.alloc = self.be(0x395,4)
        require(self.base in (0xa000,0xb000) and 170 < self.alloc < 28900, 'This package layout is not supported yet.')
        require(self.be(0x360,4) in (0,0x45410915), 'This save belongs to a different game.')
        require(self.be(0x344,4) == 1, 'Choose a saved-game package.')
        self.top = self.base+(170+(1<<self.sex))*4096+((self.sep&2)<<11)
        require(self.top+4096 <= len(b) and self.addr(self.alloc-1)+4096 <= len(b), 'The save is truncated.')
        self.verify_hashes()
        require(verify_signature(b), 'The source package signature is invalid. Repair it in Horizon first.')
        require(self.le(0x37c,2) == 1, 'Multiple directory blocks are not supported yet.')
        entries=[]
        directory=self.addr(self.le(0x37e,3))
        for i in range(64):
            off=directory+i*64
            count=b[off+40]&63
            if not count:
                continue
            require(count<=40, 'Invalid file name in package.')
            name=bytes(b[off:off+count]).decode('ascii',errors='strict')
            if b[off+40]&128:
                continue
            entries.append((name,off,self.le(off+0x2f,3),self.be(off+0x34,4),self.le(off+0x29,3),bool(b[off+40]&64)))
        candidates=[e for e in entries if e[0].startswith('FN_FACE_')]
        require(len(candidates)==1, 'The package must contain exactly one Fight Night Champion boxer file.')
        self.entry=candidates[0]
        name,off,start,size,blocks,contiguous=self.entry
        require(size==14000028 and blocks==(size+4095)//4096 and contiguous, 'Unsupported boxer file size or allocation. The original was not changed.')
        require(0 <= start and start+blocks <= self.alloc, 'Invalid boxer block range.')
        self.payload=b''.join(bytes(b[self.addr(start+i):self.addr(start+i)+4096]) for i in range(blocks))[:size]
        validate_payload(self.payload)

    def addr(self,block):
        backing=block+((block+170)//170)*(1<<self.sex)
        if block>=170:
            backing+=((block+28900)//28900)*(1<<self.sex)
        return self.base+backing*4096

    def haddr(self,block):
        group=block//170
        backing=0 if group==0 else group*(170+(1<<self.sex))+(1<<self.sex)
        alternate=(self.data[self.top+group*24+20]&64)<<6
        return self.base+backing*4096+alternate+(block%170)*24

    def verify_hashes(self):
        b=self.data
        require(sha(b[0x344:self.base])==b[0x32c:0x340], 'The package header hash is invalid.')
        require(sha(b[self.top:self.top+4096])==b[0x381:0x395], 'The package root hash is invalid.')
        for group in range((self.alloc+169)//170):
            table=self.haddr(group*170)
            require(table+4096 <= len(b), 'Invalid hash table address.')
            require(sha(b[table:table+4096])==b[self.top+group*24:self.top+group*24+20], 'A package hash table is damaged.')
        for block in range(self.alloc):
            h=self.haddr(block)
            if b[h+20]&128:
                a=self.addr(block)
                require(sha(b[a:a+4096])==b[h:h+20], 'The save contains a damaged data block.')

    def replace(self,payload):
        require(len(payload)==len(self.payload), 'Unexpected merged size.')
        start=self.entry[2]
        for i in range(self.entry[4]):
            chunk=payload[i*4096:(i+1)*4096]
            a=self.addr(start+i)
            self.data[a:a+len(chunk)]=chunk
        self.data[0x360:0x364]=(0x45410915).to_bytes(4,'big')
        for block in range(self.alloc):
            a=self.addr(block); h=self.haddr(block)
            self.data[h:h+20]=sha(self.data[a:a+4096])
        for group in range((self.alloc+169)//170):
            a=self.haddr(group*170)
            self.data[self.top+group*24:self.top+group*24+20]=sha(self.data[a:a+4096])
        self.data[0x381:0x395]=sha(self.data[self.top:self.top+4096])
        self.data[0x32c:0x340]=sha(self.data[0x344:self.base])
        self.verify_hashes()

def validate_payload(payload):
    require(len(payload)==14000028 and payload[:16]==b'TXT_BOXERS_SAVE\0', 'Unsupported boxer data.')
    require(payload[16:32] == struct.pack('>4I',0,83,0,83), 'Unsupported boxer schema. The original was not changed.')
    for slot in range(83):
        record=payload[32+slot*1004:32+(slot+1)*1004]
        a,c=struct.unpack_from('>II',record)
        require(a==c and a<1000000, 'Unrecognized boxer record layout.')
        require(a!=0 or not any(record), 'An empty slot contains unknown data; merging is disabled.')

def merge(payload,donors):
    validate_payload(payload)
    require(len(donors)==2008, 'The bundled Bishop records are missing or invalid.')
    output=bytearray(payload)
    ids={int.from_bytes(payload[32+i*1004:36+i*1004],'big') for i in range(83)}
    empty=[i for i in range(83) if not any(payload[32+i*1004:32+(i+1)*1004])]
    added=[]; kept=[]; changed=[]
    for index,expected in enumerate((2514,2520)):
        record=donors[index*1004:(index+1)*1004]
        require(struct.unpack_from('>II',record)==(expected,expected), 'Invalid Bishop donor record.')
        if expected in ids:
            kept.append(expected)
            continue
        require(bool(empty), 'There are not enough verified empty slots for both Bishops.')
        slot=empty.pop(0); start=32+slot*1004
        output[start:start+1004]=record
        changed.append((start,start+1004)); added.append(expected)
    # Preserve every byte outside the inserted records, including all appearance blobs.
    cursor=0
    for start,end in sorted(changed):
        require(output[cursor:start]==payload[cursor:start], 'Preservation check failed.')
        cursor=end
    require(output[cursor:]==payload[cursor:], 'Preservation check failed.')
    validate_payload(output)
    return bytes(output),{'added':added,'already_present':kept,'changed_slots':[(a-32)//1004 for a,z in changed]}

def sign_keyvault(package,kv,preserve_console_id=False):
    require(len(kv) in (0x3ff0,0x4000), 'Choose a decrypted 0x3FF0 or 0x4000 byte signing keyvault.')
    shift=0x10 if len(kv)==0x4000 else 0
    cert=kv[0x9b8+shift:0x9b8+shift+0x1a8]
    require(int.from_bytes(cert[:2],'big')==0x1a8, 'The signing certificate is invalid or encrypted.')
    exponent=int.from_bytes(cert[0x24:0x28],'big')
    raw=kv[0x298+shift:0x398+shift]
    key=None
    for transform in range(4):
        n=int.from_bytes(forms(raw[:128])[transform],'big')
        p=int.from_bytes(forms(raw[128:192])[transform],'big')
        q=int.from_bytes(forms(raw[192:256])[transform],'big')
        if p*q!=n or p<3 or q<3:
            continue
        try:
            d=pow(exponent,-1,(p-1)*(q-1))
            key=rsa.RSAPrivateNumbers(p,q,d,d%(p-1),d%(q-1),pow(q,-1,p),rsa.RSAPublicNumbers(exponent,n)).private_key()
        except ValueError:
            continue
        require(n in [int.from_bytes(x,'big') for x in forms(cert[0x28:0xa8])], 'The private key does not match the certificate.')
        break
    require(key is not None, 'The signing private key is invalid or encrypted.')
    b=package.data
    profile=bytes(b[0x371:0x379])
    b[4:0x1ac]=cert
    if not preserve_console_id:
        b[0x36c:0x371]=cert[2:7]
    b[0x32c:0x340]=sha(b[0x344:package.base])
    sig=key.sign(bytes(b[0x22c:0x344]),padding.PKCS1v15(),hashes.SHA1())
    b[0x1ac:0x22c]=sig[::-1]
    require(verify_signature(b),'The new package signature failed verification.')
    require(bytes(b[0x371:0x379])==profile,'Profile preservation check failed.')
    package.verify_hashes()
    return bytes(b)
