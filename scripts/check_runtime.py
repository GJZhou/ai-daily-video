"""Probe the relocated interpreter, Python packages and application-local C++ DLLs."""
import ctypes
import json
from pathlib import Path
import site
import sys

import numpy
import onnxruntime
import qwen_tts
import soundfile
import torch

root = Path(sys.executable).resolve().parent
assert sys.version_info[:2] == (3, 12), 'CPython 3.12 is required.'
assert Path(sys.prefix).resolve() == root, 'Interpreter prefix leaked to the source machine.'
assert site.ENABLE_USER_SITE is False, 'User site-packages must be disabled.'
for package in (numpy, onnxruntime, qwen_tts, soundfile, torch):
    assert Path(package.__file__).resolve().is_relative_to(root), 'External package path detected.'
kernel = ctypes.WinDLL('kernel32', use_last_error=True)
kernel.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
kernel.GetModuleHandleW.restype = ctypes.c_void_p
kernel.GetModuleFileNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32]
kernel.GetModuleFileNameW.restype = ctypes.c_uint32
paths = {}
for name in ('msvcp140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll'):
    handle = kernel.GetModuleHandleW(name)
    assert handle, f'CRT dependency was not loaded: {name}'
    buffer = ctypes.create_unicode_buffer(32768)
    assert kernel.GetModuleFileNameW(handle, buffer, len(buffer)), 'Cannot locate loaded CRT.'
    path = Path(buffer.value).resolve()
    assert path.parent == root, f'CRT dependency resolved outside the portable runtime: {name}'
    paths[name] = str(path)
print(json.dumps({'status': 'portable-imports-ready', 'python': str(root),
                  'torch': torch.__version__, 'user_site_enabled': site.ENABLE_USER_SITE,
                  'application_local_crt': paths}, ensure_ascii=False))
