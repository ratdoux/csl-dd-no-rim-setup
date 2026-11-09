# SPDX-License-Identifier: AGPL-3.0-only
"""Setup state machine and saved-profile enforcement, independent of the UI."""
from pathlib import Path
from datetime import datetime,timezone
import json,sys
from firmware import reviewed,fingerprint

def app_folder():
    return Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent

def state(connection):
    data=connection.query()
    if len(data)!=64 or data[:2]!=b'\xff\x08':raise RuntimeError('Unrecognized system report.')
    return {'device_id':connection.identity,'base_type':data[2],
            'firmware':'.'.join(map(str,data[5:9])),'rim_id':data[24],
            'status_profile':data[53],'availability':data[55]}

def binding(s):return {k:s[k] for k in ('device_id','base_type','firmware','status_profile')}

def guard(s,profile,expected=None):
    trusted=reviewed(s['firmware'])
    if not profile or not trusted or fingerprint(profile)!=fingerprint(trusted):
        raise RuntimeError('This firmware has no reviewed command profile. No trial is allowed.')
    if s['base_type']!=10 or s['status_profile']!=profile['status_profile']:
        raise RuntimeError('This base or status profile has not been reviewed.')
    if s['rim_id']!=0:raise RuntimeError('A rim is detected. This setup is for a passive or undetected rim.')
    if expected and binding(s)!=binding(expected):raise RuntimeError('The base, USB connection, or firmware changed. Detect it again.')
    if profile['readback']=='availability15' and s['availability'] not in (0,15):
        raise RuntimeError('Unexpected override status. No trial is allowed.')

def send_checked(connection,profile,expected,enabled):
    connection.set_override(enabled)
    after=state(connection);guard(after,profile,expected)
    if profile['readback']=='availability15' and after['availability']!=(15 if enabled else 0):
        raise RuntimeError('The requested override state was not confirmed by the base.')
    return after

def run_trial(connection,profile,detected,progress=lambda message:None):
    before=state(connection);guard(before,profile,detected)
    record={'binding':binding(before),'profile_id':fingerprint(profile),'readback':profile['readback'],
            'started_at':datetime.now(timezone.utc).isoformat(),'steps':[],'trial_completed':False}
    try:
        if profile['readback']=='availability15':
            original=before['availability']==15
            progress('Checking that the override can change state...')
            for enabled in (not original,original):
                after=send_checked(connection,profile,before,enabled)
                record['steps'].append({'enabled':enabled,'availability':after['availability']})
            if not original:
                progress('Reversible test passed. Enabling for your game test...')
                after=send_checked(connection,profile,before,True)
                record['steps'].append({'enabled':True,'availability':after['availability']})
            record['automatic_readback_passed']=True
        else:
            progress('Sending the reviewed command. This version requires a game test to confirm it.')
            after=send_checked(connection,profile,before,True)
            record['steps'].append({'enabled':True,'transport_completed':True})
            record['automatic_readback_passed']=False
        record['trial_completed']=True
        record['enabled_for_game']=True
        return record
    except (Exception,KeyboardInterrupt) as exc:
        try:
            send_checked(connection,profile,before,False)
            suffix='The disabled state was confirmed.' if profile['readback']=='availability15' else 'A disable command was sent; this version cannot report its override state. Power off the base if unsure.'
        except (Exception,KeyboardInterrupt):
            suffix='Cleanup could not be confirmed. Power off the base before continuing.'
        raise RuntimeError('The trial did not complete. '+suffix+' Details: '+str(exc)) from exc

def stop_trial(connection,profile,expected):
    before=state(connection);guard(before,profile,expected)
    if profile['readback']=='availability15' and before['availability']==0:
        return 'Already disabled; no command resent.'
    send_checked(connection,profile,before,False)
    return 'Disabled and verified.' if profile['readback']=='availability15' else 'Disable command sent. This firmware does not report the flag; power off the base if you need certainty.'

def save_configuration(folder,record,current,game_confirmed):
    if not game_confirmed or not record or not record.get('trial_completed') or not record.get('enabled_for_game'):
        raise RuntimeError('Complete a trial and explicitly confirm that FFB worked in a game first.')
    profile=reviewed(current['firmware']);guard(current,profile,record['binding'])
    if fingerprint(profile)!=record['profile_id']:raise RuntimeError('The reviewed profile changed. Run setup again.')
    if profile['readback']=='availability15' and current['availability']!=15:
        raise RuntimeError('The override is no longer enabled. Run the trial again before saving.')
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    config={'schema':1,'binding':binding(current),'profile_id':record['profile_id'],
            'game_confirmed':True,'confirmed_at':datetime.now(timezone.utc).isoformat(),'trial':record}
    temporary=folder/'setup-profile.json.tmp'
    temporary.write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
    temporary.replace(folder/'setup-profile.json')
    batch='\r\n'.join(['@echo off','setlocal','title CSL DD - Enable confirmed setup',
        'echo Keep the wheel clear and close games or FFB tests before enabling.','echo.',
        '"%~dp0CSL-DD-No-Rim.exe" enable --wheel-clear','set "CSL_EXIT=%ERRORLEVEL%"','echo.','pause','exit /b %CSL_EXIT%',''])
    (folder/'Enable.cmd').write_bytes(batch.encode('ascii'))
    return folder/'Enable.cmd'

def load_configuration(folder):
    path=Path(folder)/'setup-profile.json'
    if not path.is_file():raise RuntimeError('Run Setup first, test in a game, and confirm it worked. No enable command was sent.')
    value=json.loads(path.read_text(encoding='utf-8'))
    if value.get('schema')!=1 or value.get('game_confirmed') is not True:
        raise RuntimeError('This setup has not been confirmed. Run Setup again.')
    profile=reviewed(value.get('binding',{}).get('firmware'))
    if not profile or value.get('profile_id')!=fingerprint(profile):raise RuntimeError('The saved firmware profile is no longer valid. Run Setup again.')
    return value,profile

def enable_saved(connection,folder):
    config,profile=load_configuration(folder)
    before=state(connection);guard(before,profile,config['binding'])
    if profile['readback']=='availability15' and before['availability']==15:
        return 'Already enabled; no command resent.'
    try:send_checked(connection,profile,before,True)
    except (Exception,KeyboardInterrupt) as exc:
        try:
            send_checked(connection,profile,before,False)
            cleanup='Disabled again.' if profile['readback']=='availability15' else 'Disable command sent; state cannot be read back.'
        except (Exception,KeyboardInterrupt):cleanup='Cleanup could not be confirmed; power off the base.'
        raise RuntimeError('Enable did not complete. '+cleanup+' '+str(exc)) from exc
    return 'Enabled and verified.' if profile['readback']=='availability15' else 'Enable command sent for your game-confirmed firmware. This version does not expose an override-state acknowledgement.'
