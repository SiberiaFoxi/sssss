#!/usr/bin/env python3
"""Make pinned upstream buildable as a personal fork in CI (demo credentials)."""
from pathlib import Path
import json, sys
t=Path(sys.argv[1])
# Personal package in every google-services.json (upstream public dummy Firebase config).
for gs in t.glob('TMessagesProj*/google-services.json'):
    d=json.loads(gs.read_text(encoding="utf-8"))
    for c in d.get('client',[]):
        info=c.get('client_info',{}).get('android_client_info',{})
        pkg=info.get('package_name','')
        if pkg.startswith('org.telegram.messenger'):
            info['package_name']=pkg.replace('org.telegram.messenger','org.derenguhgram.personal',1)
    gs.write_text(encoding="utf-8",data=json.dumps(d,indent=2)+'\n')
# Trim unused app modules / Huawei repository to keep CI hermetic and faster.
settings=t/'settings.gradle'; s=settings.read_text(encoding="utf-8")
for line in ["include ':TMessagesProj_AppHuawei'\n","include ':TMessagesProj_AppHockeyApp'\n","include ':TMessagesProj_AppStandalone'\n","include ':TMessagesProj_AppTests'\n"]:
    s=s.replace(line,'')
settings.write_text(encoding="utf-8",data=s)
root=t/'build.gradle'; s=root.read_text(encoding="utf-8")
s=s.replace("        maven { url 'https://developer.huawei.com/repo/' }\n",'')
s=s.replace("        classpath 'com.huawei.agconnect:agcp:1.9.1.301'\n",'')
root.write_text(s,encoding="utf-8")
print('Android CI prep done')
