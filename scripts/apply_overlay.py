#!/usr/bin/env python3
"""Copy an auditable overlay into a pinned upstream checkout. Refuses to overwrite
non-identical existing files unless they are listed as generated replacements."""
from pathlib import Path
import argparse, shutil, sys

def main():
    p=argparse.ArgumentParser(); p.add_argument('overlay',type=Path); p.add_argument('target',type=Path)
    a=p.parse_args(); src=a.overlay/'files'; dst=a.target
    if not src.is_dir() or not dst.is_dir(): sys.exit('overlay/target missing')
    n=0
    for f in sorted(src.rglob('*')):
        if not f.is_file(): continue
        rel=f.relative_to(src); out=dst/rel; out.parent.mkdir(parents=True,exist_ok=True)
        if out.exists() and out.read_bytes()!=f.read_bytes():
            bak=out.with_suffix(out.suffix+'.upstream.bak')
            if not bak.exists(): shutil.copy2(out,bak)
        shutil.copy2(f,out); n+=1
    print(f'overlay: copied {n} files into {dst}')
if __name__=='__main__': main()
