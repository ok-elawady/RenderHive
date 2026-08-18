from __future__ import print_function
import json, os, re
from pathlib import Path

SUPPORTED = ("19.5", "20.0", "20.5", "21.0")
source = Path(__file__).resolve().parents[1]
text=(source/'payload/python_libs/renderhive_houdini/version.py').read_text(encoding='utf-8')
version=re.search(r'__version__\s*=\s*["\']([^"\']+)',text).group(1)
local=Path(os.environ.get('LOCALAPPDATA', str(Path.home()/'AppData'/'Local')))
runtime=local/'RenderHive'/'Houdini'/version
print('='*60)
print(' RenderHive Houdini v{} - Installation Check'.format(version))
print('='*60)
checks={
 'Runtime': runtime/'python_libs/renderhive_houdini/version.py',
 'Shelf definition': runtime/'toolbar/RenderHive.shelf',
 'Shelf SVG icon': runtime/'config/Icons/renderhive.svg',
 'Shelf PNG icon': runtime/'config/Icons/renderhive.png',
 'Header logo': runtime/'icons/renderhive_header_logo.png',
 'Python Panel': runtime/'python_panels/renderhive.pypanel',
 'Main Menu': runtime/'MainMenuCommon.xml',
}
ok=True
for label,path in checks.items():
    good=path.is_file(); ok &= good
    print('{:<18} {}'.format(label+':', 'OK - '+str(path) if good else 'MISSING - '+str(path)))
registered=0
for series in SUPPORTED:
    package=Path.home()/'Documents'/('houdini'+series)/'packages'/'renderhive.json'
    if not package.is_file(): continue
    try:
        data=json.loads(package.read_text(encoding='utf-8-sig'))
        hpath=str(data.get('hpath',''))
        expected=str(runtime).replace('\\','/')
        good=(hpath == '$RENDERHIVE_HOUDINI_ROOT' and any(isinstance(x,dict) and x.get('RENDERHIVE_HOUDINI_ROOT')==expected for x in data.get('env',[])))
    except Exception:
        good=False
    print('Houdini {:<7} {}'.format(series+':', 'REGISTERED' if good else 'REGISTRATION INVALID'))
    ok &= good; registered += int(good)
if registered == 0:
    print('Package registration: NONE')
    ok=False
print()
print('Installation structure is READY.' if ok else 'Installation structure has a problem.')
raise SystemExit(0 if ok else 1)
