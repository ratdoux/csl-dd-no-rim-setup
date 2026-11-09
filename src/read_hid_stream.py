"""Passive interrupt-input capture; never writes a HID output report."""
import ctypes as C,json,time
from ctypes import wintypes as W
from fanatec_hid_readonly import inventory,create,close,kernel,bind
class OVERLAPPED(C.Structure):
    _fields_=[('Internal',C.c_size_t),('InternalHigh',C.c_size_t),('Offset',W.DWORD),('OffsetHigh',W.DWORD),('hEvent',W.HANDLE)]
event=bind(kernel,'CreateEventW',[C.c_void_p,W.BOOL,W.BOOL,W.LPCWSTR],W.HANDLE)
read=bind(kernel,'ReadFile',[W.HANDLE,C.c_void_p,W.DWORD,C.POINTER(W.DWORD),C.POINTER(OVERLAPPED)],W.BOOL)
wait=bind(kernel,'WaitForSingleObject',[W.HANDLE,W.DWORD],W.DWORD)
result=bind(kernel,'GetOverlappedResult',[W.HANDLE,C.POINTER(OVERLAPPED),C.POINTER(W.DWORD),W.BOOL],W.BOOL)
cancel=bind(kernel,'CancelIoEx',[W.HANDLE,C.POINTER(OVERLAPPED)],W.BOOL)
reset=bind(kernel,'ResetEvent',[W.HANDLE],W.BOOL)

def sample(path,length,seconds=2):
    h=create(path,0x80000000,3,None,3,0x40000000,None)
    if h==C.c_void_p(-1).value: return {'error':C.get_last_error()}
    ev=event(None,True,False,None);outputs={};count=0;errors=[]
    try:
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            reset(ev);o=OVERLAPPED();o.hEvent=ev;buf=C.create_string_buffer(length);n=W.DWORD()
            ok=read(h,buf,length,C.byref(n),C.byref(o))
            if not ok:
                err=C.get_last_error()
                if err!=997:errors.append(err);break
                if wait(ev,500)!=0:
                    cancel(h,C.byref(o));result(h,C.byref(o),C.byref(n),True);continue
                if not result(h,C.byref(o),C.byref(n),False):errors.append(C.get_last_error());break
            value=buf.raw[:n.value].hex();outputs[value]=outputs.get(value,0)+1;count+=1
    finally:close(ev);close(h)
    return {'count':count,'unique_reports':outputs,'errors':errors}

if __name__=='__main__':
    out=[]
    for device in inventory():
        if 'caps' in device:out.append({'path':device['path'],'capture':sample(device['path'],device['caps']['InputReportByteLength'])})
    print(json.dumps(out,indent=2))
