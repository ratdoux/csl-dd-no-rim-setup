# SPDX-License-Identifier: AGPL-3.0-only
"""Native Windows desktop shortcuts; no shell commands or extra runtime needed.

Uses SHGetKnownFolderPath, IShellLinkW and IPersistFile (Microsoft Shell APIs).
Creating a shortcut never runs the launcher or accesses the wheelbase.
"""
from contextlib import contextmanager
from pathlib import Path
import ctypes as C
from ctypes import wintypes as W
import os
import uuid

from engine import load_configuration


class GUID(C.Structure):
    _fields_ = [('a', W.DWORD), ('b', W.WORD), ('c', W.WORD), ('d', C.c_ubyte * 8)]


def _guid(value):
    return GUID.from_buffer_copy(uuid.UUID(value).bytes_le)


def _check(hr, action):
    if hr < 0:
        raise OSError(f'{action} failed (Windows error 0x{hr & 0xffffffff:08x}).')


def _method(pointer, slot, *types):
    table = C.cast(pointer, C.POINTER(C.POINTER(C.c_void_p))).contents
    return C.WINFUNCTYPE(W.LONG, C.c_void_p, *types)(table[slot])


@contextmanager
def _com():
    ole = C.WinDLL('ole32')
    ole.CoInitializeEx.argtypes = [C.c_void_p, W.DWORD]
    ole.CoInitializeEx.restype = W.LONG
    ole.CoUninitialize.argtypes = []
    ole.CoUninitialize.restype = None
    # A thread already initialized in the other mode can still use ShellLink.
    hr = ole.CoInitializeEx(None, 2)
    initialized = hr >= 0
    if not initialized and hr & 0xffffffff != 0x80010106:
        _check(hr, 'Initialize Windows shortcuts')
    try:
        yield ole
    finally:
        if initialized:
            ole.CoUninitialize()


def desktop_folder():
    """Honor redirected desktops, including OneDrive, through Windows itself."""
    with _com() as ole:
        shell = C.WinDLL('shell32')
        shell.SHGetKnownFolderPath.argtypes = [C.POINTER(GUID), W.DWORD, W.HANDLE, C.POINTER(C.c_void_p)]
        shell.SHGetKnownFolderPath.restype = W.LONG
        ole.CoTaskMemFree.argtypes = [C.c_void_p]
        folder_id = _guid('b4bfcc3a-db2c-424c-b029-7fe99a87c641')
        value = C.c_void_p()
        try:
            _check(shell.SHGetKnownFolderPath(C.byref(folder_id), 0, None, C.byref(value)), 'Find Desktop')
            return Path(C.wstring_at(value))
        finally:
            if value.value:
                ole.CoTaskMemFree(value)


@contextmanager
def _link():
    with _com() as ole:
        ole.CoCreateInstance.argtypes = [C.POINTER(GUID), C.c_void_p, W.DWORD, C.POINTER(GUID), C.POINTER(C.c_void_p)]
        ole.CoCreateInstance.restype = W.LONG
        clsid = _guid('00021401-0000-0000-c000-000000000046')
        iid = _guid('000214f9-0000-0000-c000-000000000046')
        persist_iid = _guid('0000010b-0000-0000-c000-000000000046')
        link, persist = C.c_void_p(), C.c_void_p()
        _check(ole.CoCreateInstance(C.byref(clsid), None, 1, C.byref(iid), C.byref(link)), 'Create shortcut')
        try:
            _check(_method(link, 0, C.POINTER(GUID), C.POINTER(C.c_void_p))(
                link, C.byref(persist_iid), C.byref(persist)), 'Open shortcut storage')
            yield link, persist
        finally:
            if persist.value:
                _method(persist, 2)(persist)
            _method(link, 2)(link)


def shortcut_target(path):
    """Read an existing link without resolving or executing its target."""
    with _link() as (link, persist):
        _check(_method(persist, 5, W.LPCWSTR, W.DWORD)(persist, str(path), 0), 'Read shortcut')
        target = C.create_unicode_buffer(32768)
        _check(_method(link, 3, W.LPWSTR, C.c_int, C.c_void_p, W.DWORD)(
            link, target, len(target), None, 4), 'Read shortcut target')
        return Path(target.value)


def create_desktop_shortcut(folder, *, destination=None):
    """Create a .lnk to the confirmed Enable.cmd; preserve unrelated names."""
    folder = Path(folder).resolve()
    load_configuration(folder)  # Never offer an unconfirmed setup as a daily launcher.
    target = folder / 'Enable.cmd'
    executable = folder / 'CSL-DD-No-Rim.exe'
    if not target.is_file() or not executable.is_file():
        raise RuntimeError('Keep Enable.cmd and the portable executable in this folder. Save your setup first.')
    desktop = Path(destination) if destination is not None else desktop_folder()
    if not desktop.is_dir():
        raise RuntimeError('The Windows Desktop folder is unavailable.')
    for number in range(1, 100):
        suffix = '' if number == 1 else f' ({number})'
        path = desktop / ('Enable CSL DD FFB' + suffix + '.lnk')
        if not path.exists():
            break
        try:
            if os.path.normcase(str(shortcut_target(path))) == os.path.normcase(str(target)):
                return path
        except OSError:
            pass
    else:
        raise RuntimeError('Could not find an unused desktop shortcut name.')
    with _link() as (link, persist):
        _check(_method(link, 20, W.LPCWSTR)(link, str(target)), 'Set shortcut target')
        _check(_method(link, 9, W.LPCWSTR)(link, str(folder)), 'Set shortcut folder')
        _check(_method(link, 7, W.LPCWSTR)(link, 'Enable no-rim FFB before starting your game.'), 'Set shortcut description')
        icon = folder / 'CSL-DD-No-Rim-Setup.exe'
        _check(_method(link, 17, W.LPCWSTR, C.c_int)(link, str(icon if icon.is_file() else executable), 0), 'Set shortcut icon')
        _check(_method(persist, 6, W.LPCWSTR, W.BOOL)(persist, str(path), True), 'Save desktop shortcut')
    if not path.is_file():
        raise OSError('Windows did not create the desktop shortcut.')
    return path
