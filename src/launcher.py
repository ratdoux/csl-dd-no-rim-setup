# SPDX-License-Identifier: AGPL-3.0-only
from pathlib import Path
import argparse,json,sys
from transport import Connection
from firmware import reviewed
from engine import app_folder,state,enable_saved,stop_trial
from version import APP_VERSION

def main():
    gui=Path(sys.executable).stem.endswith('-Setup') if getattr(sys,'frozen',False) else False
    if gui or (len(sys.argv)>1 and sys.argv[1]=='setup'):
        from wizard import main as show
        show();return 0
    p=argparse.ArgumentParser(description='CSL DD No-Rim: detect, test, confirm, then enable your saved setup.')
    p.add_argument('action',nargs='?',default='status',choices=['status','enable','disable','check-ui'])
    p.add_argument('--wheel-clear',action='store_true')
    p.add_argument('--json',action='store_true')
    p.add_argument('--version',action='version',version='CSL DD No-Rim Setup '+APP_VERSION)
    a=p.parse_args()
    if a.action=='enable' and not a.wheel_clear:p.error('Clear the wheel and close games/FFB tests, then use --wheel-clear.')
    try:
        if a.action=='check-ui':
            from wizard import check_ui
            print(json.dumps(check_ui()));return 0
        c=Connection()
        if a.action=='enable':answer={'message':enable_saved(c,app_folder())}
        elif a.action=='disable':
            s=state(c);answer={'message':stop_trial(c,reviewed(s['firmware']),s)}
        else:
            s=state(c);profile=reviewed(s['firmware'])
            answer={'status':s,'reviewed_profile':bool(profile),'readback':profile['readback'] if profile else None}
            if not a.json:
                print('CSL DD firmware: '+s['firmware'])
                if not profile:print('No reviewed command profile. Run Setup for image inspection.')
                elif profile['readback']=='manual':print('Command reviewed; this firmware does not expose the override flag. Use Setup and confirm in a game.')
                elif s['rim_id']==0 and s['availability'] in (0,15):print('Override: '+('ENABLED' if s['availability']==15 else 'DISABLED'))
                else:print('Override state not confirmed.')
        if a.json:print(json.dumps(answer))
        elif 'message' in answer:print(answer['message'])
        return 0
    except (Exception,KeyboardInterrupt) as exc:
        print(json.dumps({'error':str(exc)}) if a.json else 'ERROR: '+str(exc));return 1

if __name__=='__main__':raise SystemExit(main())
