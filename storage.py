"""Discover numbered Xbox content folders and safely return a verified save."""
import ctypes
import os
import re
import hashlib
import tempfile
from pathlib import Path
from dataclasses import dataclass
from core import Package, SaveError, require

HEX16=re.compile(r'^[0-9A-Fa-f]{16}$')

@dataclass
class FoundSave:
    path: Path
    profile: str
    label: str

def drives():
    result=[]
    if os.name!='nt':return result
    mask=ctypes.windll.kernel32.GetLogicalDrives()
    for i in range(26):
        root=Path(f'{chr(65+i)}:/')
        if mask&(1<<i) and ctypes.windll.kernel32.GetDriveTypeW(str(root)) in (2,3):
            if (root/'Content').is_dir():result.append(root)
    return result

def content_roots(selected):
    selected=Path(selected).resolve()
    if selected.is_file():selected=selected.parent
    if selected.name.lower()=='content':return [selected]
    if (selected/'Content').is_dir():return [selected/'Content']
    # A selected numbered folder can be recognized without navigating upward manually.
    for parent in [selected,*list(selected.parents)[:4]]:
        if parent.name.lower()=='content':return [parent]
    roots=[]; visited=0
    for root,dirs,files in os.walk(selected,followlinks=False):
        visited+=1
        if visited>500:break
        base=Path(root)
        depth=len(base.relative_to(selected).parts)
        dirs[:]=[d for d in dirs if not (base/d).is_symlink() and depth<3]
        for name in list(dirs):
            if name.lower()=='content':
                roots.append(base/name); dirs.remove(name)
    return roots

def profile_name(folder):
    # STFS profile display names may contain a gamertag; absence gets an honest label.
    candidates=folder/'FFFE07D1'/'00010000'
    if candidates.is_dir():
        for path in list(candidates.iterdir())[:20]:
            if not path.is_file() or path.is_symlink():continue
            try:
                with path.open('rb') as stream:header=stream.read(0x1691)
                if header[:4]!=b'CON ':continue
                name=header[0x411:0x491].decode('utf-16-be',errors='ignore').split('\0')[0].strip()
                if name and name.lower() not in ('gamer profile','profile','xbox 360 profile'):
                    return name
            except OSError:continue
    return 'Xbox profile ending '+folder.name[-4:].upper()

def discover(selected):
    found=[]; issues=[]; seen=set()
    for content in content_roots(selected):
        try:profiles=list(content.iterdir())
        except OSError:continue
        for profile in profiles:
            if not profile.is_dir() or profile.is_symlink() or not HEX16.fullmatch(profile.name):continue
            saves=profile/'45410915'/'00000001'
            if not saves.is_dir():continue
            name=profile_name(profile)
            for path in sorted(saves.iterdir()):
                if path.is_symlink() or not path.is_file():continue
                try:
                    if not 0xa000<=path.stat().st_size<=64000000:continue
                    with path.open('rb') as stream:header=stream.read(0x379)
                    if header[:4]!=b'CON ' or int.from_bytes(header[0x344:0x348],'big')!=1:continue
                    # Ignore known career/profile packages rather than presenting them as boxer saves.
                    if path.name.startswith(('FN4PROFILE','FN4LEGACY','FN_CHAMP')):continue
                    package=Package(path.read_bytes())
                    owner=header[0x371:0x379].hex().upper()
                    require(owner==profile.name.upper(),'Save ownership does not match its Xbox profile folder.')
                    resolved=path.resolve()
                    if resolved in seen:continue
                    seen.add(resolved)
                    stamp=__import__('datetime').datetime.fromtimestamp(path.stat().st_mtime).strftime('%b %d, %Y %I:%M %p')
                    found.append(FoundSave(resolved,owner,f'{name} • Fight Night Champion boxers • {stamp}'))
                except (OSError,ValueError,IndexError) as error:
                    issues.append('A Fight Night Champion file could not be used: '+str(error))
    return found,issues

def put_back(source,original_hash,signed,expected_payload_hash,profile):
    """No USB write until signature, ownership, payload and unchanged-source checks pass."""
    source=Path(source)
    require(not source.is_symlink(),'The destination must be an actual save file.')
    parts=source.parts
    require(len(parts)>=5 and source.parent.name=='00000001' and source.parent.parent.name.upper()=='45410915'
            and source.parent.parent.parent.name.upper()==profile and source.parent.parent.parent.parent.name.lower()=='content',
            'The destination is not the discovered Fight Night Champion folder.')
    package=Package(signed)
    require(bytes(package.data[0x371:0x379]).hex().upper()==profile,'The signed copy belongs to another profile.')
    require(hashlib.sha256(package.payload).hexdigest()==expected_payload_hash,'The signed copy contains different boxer data.')
    require(hashlib.sha256(source.read_bytes()).hexdigest()==original_hash,'The original save changed after the backup. Scan again before continuing.')
    temp=None
    try:
        with tempfile.NamedTemporaryFile(dir=source.parent,prefix='.BishopBrothers-',delete=False) as stream:
            temp=Path(stream.name);stream.write(signed);stream.flush();os.fsync(stream.fileno())
        require(hashlib.sha256(temp.read_bytes()).hexdigest()==hashlib.sha256(signed).hexdigest(),'Copy verification failed.')
        require(hashlib.sha256(source.read_bytes()).hexdigest()==original_hash,'The save changed during copying.')
        os.replace(temp,source);temp=None
        require(hashlib.sha256(source.read_bytes()).hexdigest()==hashlib.sha256(signed).hexdigest(),'Final save verification failed. Restore the backup.')
    finally:
        if temp is not None and temp.exists():temp.unlink()
