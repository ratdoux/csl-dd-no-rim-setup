# SPDX-License-Identifier: AGPL-3.0-only
"""Local firmware inspection. Unknown images never authorize motor commands."""
from pathlib import Path
import hashlib,json,os,re,struct
from firmware_crypto import decrypt,parse_hex

CATALOG=json.loads(Path(__file__).with_name('catalog.json').read_text(encoding='utf-8'))

def fingerprint(profile):
    return hashlib.sha256(json.dumps(profile,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def reviewed(version):
    return CATALOG['profiles'].get(version)

def inspect_image(path,running_version=None):
    path=Path(path)
    if not 0<path.stat().st_size<=4*1024*1024:raise ValueError('Select a firmware image smaller than 4 MB, not an installer or archive.')
    raw=path.read_bytes()
    plain=raw if raw.lstrip().startswith((b'0x0720_',b':')) else decrypt(raw)
    match=re.search(rb'^0x0720_V(\d+)_(\d+)_(\d+)_(\d+)[^\r\n]*',plain,re.M)
    if not match:raise ValueError('This is not a recognized CSL DD firmware image with a version header.')
    version='.'.join(g.decode() for g in match.groups())
    if running_version and version!=running_version:
        raise ValueError('Image version '+version+' does not match the connected base ('+running_version+').')
    memory,info=parse_hex(plain)
    canonical=b''.join(struct.pack('<IB',a,b) for a,b in sorted(memory.items()))
    digest=hashlib.sha256(canonical).hexdigest();profile=reviewed(version)
    exact=bool(profile and digest==profile['memory_sha256'])
    if exact:
        for block in profile['blocks']:
            start=int(block['pc'],16)*2;expected=bytes.fromhex(block['bytes'])
            if bytes(memory.get(start+i,0xff) for i in range(len(expected)))!=expected:
                raise ValueError('Reviewed instruction block did not match.')
    # A byte-pattern match is only a lead, never permission to send a command.
    pattern=bytes.fromhex(CATALOG['candidate_pattern'])
    candidate=any(pattern in bytes(memory[a] for a in range(lo,hi)) for lo,hi in info['ranges'] if hi-lo<4*1024*1024)
    return {'version':version,'image_name':path.name,'image_verified':exact,'memory_sha256':digest,
            'candidate_pattern':candidate,'profile':profile if exact else None,
            'basis':'Matching image and reviewed instruction blocks.' if exact else 'Image parsed, but its complete contents have not been reviewed. Testing is blocked.'}

def discover(version):
    roots=[]
    for key in ('ProgramFiles','ProgramFiles(x86)'):
        value=os.environ.get(key)
        if value:roots.append(Path(value)/'Fanatec/Fanatec Wheel/fw')
    matches=[];count=0
    for root in roots:
        if not root.is_dir():continue
        for path in root.rglob('*.hex'):
            count+=1
            if count>200:break
            try:
                if path.stat().st_size<400000:continue
                item=inspect_image(path,version)
                if item['image_verified']:return item
                matches.append(item)
            except (OSError,ValueError,UnicodeError,IndexError):continue
    if matches:return matches[0]
    profile=reviewed(version)
    return {'version':version,'image_name':None,'image_verified':False,'profile':profile,
            'basis':'Reviewed official-version profile; no matching local image found. The device flash was not read back.' if profile else 'No reviewed profile or matching image found. Choose a matching firmware image for inspection; unrecognized images remain blocked.'}
