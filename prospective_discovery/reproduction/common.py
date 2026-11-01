import hashlib,json
from pathlib import Path
PACKAGE=Path(__file__).resolve().parents[1]
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path): return json.loads(Path(path).read_text())
def write(path,obj):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f: json.dump(obj,f,indent=2,sort_keys=True);f.write('\n')
def safe(root,rel):
    p=Path(rel)
    if p.is_absolute() or '..' in p.parts or '\\' in rel: raise ValueError('Unsafe relative path')
    dest=root/p
    if dest.is_symlink() or not dest.resolve().is_relative_to(root.resolve()): raise ValueError('Unsafe path')
    return dest
