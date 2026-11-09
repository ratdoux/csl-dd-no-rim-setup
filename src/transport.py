"""Windows HID transport. Only fixed status/override reports can be sent."""
import concurrent.futures
import ctypes as C
from ctypes import wintypes as W
import time
import hashlib
from fanatec_hid_readonly import inventory, create, close, kernel, bind
from read_hid_stream import sample, OVERLAPPED, event, wait, result, cancel

write = bind(kernel,'WriteFile',[W.HANDLE,C.c_void_p,W.DWORD,C.POINTER(W.DWORD),C.POINTER(OVERLAPPED)],W.BOOL)

def device_key(device):
    parts=device['path'].lower().split('#')
    return parts[1].split('&col')[0],parts[2].rsplit('&',1)[0]

class Connection:
    def __init__(self):
        devices=[d for d in inventory() if d.get('vid')=='0xeb7' and d.get('pid')=='0x4' and 'caps' in d]
        controls=[d for d in devices if d['caps']['UsagePage']==1 and d['caps']['Usage']==0x3a
                  and d['caps']['InputReportByteLength']==64 and d['caps']['OutputReportByteLength']==64]
        if not controls:
            raise RuntimeError('No compatible base found. Power on the CSL DD, connect USB, and select compatibility mode (yellow power light).')
        if len(controls)!=1:
            raise RuntimeError('More than one compatible device is connected. Connect only the intended CSL DD.')
        self.control=controls[0]
        outputs=[d for d in devices if device_key(d)==device_key(self.control) and '&col01#' in d['path'].lower()
                 and d['caps']['UsagePage']==1 and d['caps']['Usage']==4 and d['caps']['OutputReportByteLength']==8]
        if len(outputs)!=1:raise RuntimeError('The expected output interface was not found; no override command was sent.')
        self.output=outputs[0]
        self.identity=hashlib.sha256(repr(device_key(self.control)).encode('utf-8')).hexdigest()

    @staticmethod
    def _write(path,payload):
        h=create(path,0x40000000,3,None,3,0x40000000,None)
        if h==C.c_void_p(-1).value:raise OSError(C.get_last_error(),'Could not open the HID output interface')
        ev=event(None,True,False,None)
        try:
            o=OVERLAPPED();o.hEvent=ev;n=W.DWORD();buf=C.create_string_buffer(payload,len(payload))
            ok=write(h,buf,len(payload),C.byref(n),C.byref(o))
            if not ok:
                error=C.get_last_error()
                if error!=997:raise OSError(error,'HID write failed')
                if wait(ev,2000)!=0:
                    cancel(h,C.byref(o));result(h,C.byref(o),C.byref(n),True)
                    raise TimeoutError('HID output timed out')
                if not result(h,C.byref(o),C.byref(n),False):raise OSError(C.get_last_error(),'HID write completion failed')
            if n.value!=len(payload):raise RuntimeError('Incomplete HID write')
        finally:close(ev);close(h)

    def query(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            reader=pool.submit(sample,self.control['path'],64,2)
            time.sleep(.2)
            self._write(self.control['path'],bytes.fromhex('ff0802')+bytes(61))
            captured=reader.result()
        reports=[bytes.fromhex(v) for v in captured.get('unique_reports',{}) if v.startswith('ff08')]
        if not reports:
            raise RuntimeError('No system-status reply from the base. The requested operation cannot be verified. Check USB and power.')
        return reports[-1]

    def set_override(self,enabled):
        self._write(self.output['path'],bytes([1,0xfa,0xc7 if enabled else 0,0,0,0,0,0]))
