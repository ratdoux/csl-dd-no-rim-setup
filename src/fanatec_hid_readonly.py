"""Read-only Fanatec HID inventory and input-report snapshot; no output APIs."""
import ctypes as C
from ctypes import wintypes as W
import json,sys

class GUID(C.Structure):
    _fields_=[('Data1',W.DWORD),('Data2',W.WORD),('Data3',W.WORD),('Data4',C.c_ubyte*8)]
class INTERFACE(C.Structure):
    _fields_=[('cbSize',W.DWORD),('InterfaceClassGuid',GUID),('Flags',W.DWORD),('Reserved',C.c_size_t)]
class ATTR(C.Structure):
    _fields_=[('Size',W.ULONG),('VendorID',W.USHORT),('ProductID',W.USHORT),('VersionNumber',W.USHORT)]
class CAPS(C.Structure):
    _fields_=[(x,W.USHORT) for x in ['Usage','UsagePage','InputReportByteLength','OutputReportByteLength','FeatureReportByteLength']]+[('Reserved',W.USHORT*17)]+[(x,W.USHORT) for x in ['NumberLinkCollectionNodes','NumberInputButtonCaps','NumberInputValueCaps','NumberInputDataIndices','NumberOutputButtonCaps','NumberOutputValueCaps','NumberOutputDataIndices','NumberFeatureButtonCaps','NumberFeatureValueCaps','NumberFeatureDataIndices']]
hid=C.WinDLL('hid',use_last_error=True);setup=C.WinDLL('setupapi',use_last_error=True);kernel=C.WinDLL('kernel32',use_last_error=True)
def bind(lib,name,args,ret):
    f=getattr(lib,name);f.argtypes=args;f.restype=ret;return f
getguid=bind(hid,'HidD_GetHidGuid',[C.POINTER(GUID)],None)
classes=bind(setup,'SetupDiGetClassDevsW',[C.POINTER(GUID),W.LPCWSTR,W.HWND,W.DWORD],W.HANDLE)
enum=bind(setup,'SetupDiEnumDeviceInterfaces',[W.HANDLE,C.c_void_p,C.POINTER(GUID),W.DWORD,C.POINTER(INTERFACE)],W.BOOL)
detail=bind(setup,'SetupDiGetDeviceInterfaceDetailW',[W.HANDLE,C.POINTER(INTERFACE),C.c_void_p,W.DWORD,C.POINTER(W.DWORD),C.c_void_p],W.BOOL)
destroy=bind(setup,'SetupDiDestroyDeviceInfoList',[W.HANDLE],W.BOOL)
create=bind(kernel,'CreateFileW',[W.LPCWSTR,W.DWORD,W.DWORD,C.c_void_p,W.DWORD,W.DWORD,W.HANDLE],W.HANDLE)
close=bind(kernel,'CloseHandle',[W.HANDLE],W.BOOL)
attrs=bind(hid,'HidD_GetAttributes',[W.HANDLE,C.POINTER(ATTR)],W.BOOLEAN)
preparsed=bind(hid,'HidD_GetPreparsedData',[W.HANDLE,C.POINTER(C.c_void_p)],W.BOOLEAN)
freepre=bind(hid,'HidD_FreePreparsedData',[C.c_void_p],W.BOOLEAN)
getcaps=bind(hid,'HidP_GetCaps',[C.c_void_p,C.POINTER(CAPS)],W.LONG)
getinput=bind(hid,'HidD_GetInputReport',[W.HANDLE,C.c_void_p,W.ULONG],W.BOOLEAN)

def inventory(read=False):
    guid=GUID();getguid(C.byref(guid));devs=classes(C.byref(guid),None,None,0x12);results=[]
    try:
        i=0
        while True:
            item=INTERFACE();item.cbSize=C.sizeof(item)
            if not enum(devs,None,C.byref(guid),i,C.byref(item)): break
            i+=1;n=W.DWORD()
            detail(devs,C.byref(item),None,0,C.byref(n),None)
            buf=C.create_string_buffer(n.value);C.cast(buf,C.POINTER(W.DWORD))[0]=8 if C.sizeof(C.c_void_p)==8 else 6
            if not detail(devs,C.byref(item),buf,n,None,None):continue
            path=C.wstring_at(C.addressof(buf)+4)
            if 'vid_0eb7' not in path.lower():continue
            h=create(path,0x80000000 if read else 0,3,None,3,0,None)
            result={'path':path}
            if h==C.c_void_p(-1).value:
                result['open_error']=C.get_last_error();results.append(result);continue
            try:
                a=ATTR();a.Size=C.sizeof(a)
                if attrs(h,C.byref(a)):result.update(vid=hex(a.VendorID),pid=hex(a.ProductID),usb_version=a.VersionNumber)
                p=C.c_void_p()
                if preparsed(h,C.byref(p)):
                    try:
                        c=CAPS();status=getcaps(p,C.byref(c));result['caps_status']=hex(status&0xffffffff)
                        result['caps']={name:getattr(c,name) for name,_ in CAPS._fields_ if name!='Reserved'}
                    finally:freepre(p)
                    if read and c.InputReportByteLength:
                        result['input_reports']=[]
                        for rid in [1,255]:
                            data=C.create_string_buffer(c.InputReportByteLength);data[0]=bytes([rid])
                            ok=getinput(h,data,len(data))
                            result['input_reports'].append({'report_id':rid,'ok':bool(ok),'error':0 if ok else C.get_last_error(),'hex':data.raw.hex() if ok else None})
            finally:close(h)
            results.append(result)
    finally:destroy(devs)
    return results

if __name__=='__main__': print(json.dumps(inventory('--read-input' in sys.argv),indent=2))
