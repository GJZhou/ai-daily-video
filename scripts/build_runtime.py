#!/usr/bin/env python3
"""Build a Windows x64 portable TTS release from an already validated local environment."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ID = 'win-x64-20261026-v1'
TAG = 'runtime-' + RUNTIME_ID


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def add_vc_runtime(source, output, release):
    """Add the licensed Visual Studio redistributable CRT as a separately pinned sidecar."""
    names = ('concrt140.dll', 'msvcp140.dll', 'msvcp140_1.dll', 'msvcp140_2.dll',
             'msvcp140_atomic_wait.dll', 'msvcp140_codecvt_ids.dll', 'vccorlib140.dll',
             'vcruntime140.dll', 'vcruntime140_1.dll', 'vcruntime140_threads.dll')
    for name in names:
        if not (source/name).is_file() or (source/name).is_symlink():
            raise ValueError(f'Missing Visual Studio redistributable CRT: {name}')
    archive = output/'msvc-applocal.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for name in names:
            bundle.write(source/name, 'python/'+name)
        bundle.writestr('licenses/Microsoft-CRT-NOTICE.txt',
            'Microsoft Visual C++ 2022 Redistributable CRT (x64), 14.40.33810.0.\n'
            'Copyright Microsoft Corporation. All rights reserved.\n'
            'Redistributable release binaries from the licensed Visual Studio 2022 installation, not debug runtimes.\n'
            'Distributed as application-local dependencies under the Microsoft Software License Terms for Visual Studio.\n'
            'Redistributable list: https://learn.microsoft.com/en-us/visualstudio/releases/2022/redistribution\n'
            'Deployment: https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files\n'
            'No machine-wide runtime, registry or PATH modification.\n')
    release['msvc_sidecar'] = {'name': archive.name, 'bytes': archive.stat().st_size, 'sha256': digest(archive),
                              'version': '14.40.33810.0', 'files': list(names)}
    write_json(output/'portable-runtime.json', release)
    return release


def copy_tree(source, target):
    # Never follow a junction or symlink into the author's unrelated folders.
    if source.is_symlink() or source.is_junction():
        raise ValueError(f'Linked directory is not allowed: {source.name}')
    target.mkdir(parents=True, exist_ok=False)
    for child in sorted(source.iterdir()):
        if child.is_symlink() or child.is_junction():
            raise ValueError(f'Linked input is not allowed: {child.name}')
        if child.name in {'__pycache__', '.cache', '.git', '.env'} or child.suffix in {'.pyc', '.pyo'}:
            continue
        if child.is_dir():
            copy_tree(child, target / child.name)
        else:
            shutil.copy2(child, target / child.name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--venv', type=Path, required=True, help='Validated Windows Python 3.12 venv.')
    parser.add_argument('--base-python', type=Path, required=True, help='Matching original CPython root; only stdlib/DLLs are copied.')
    parser.add_argument('--model', type=Path, required=True, help='Approved Qwen Base model directory.')
    parser.add_argument('--vc-redist', type=Path, required=True, help='Licensed VS 2022 x64 Microsoft.VC143.CRT directory (14.40.33810.0).')
    parser.add_argument('--output', type=Path, required=True, help='New empty build directory outside the Skill.')
    parser.add_argument('--dry-run', action='store_true', help='Validate inputs and show the bounded copy plan only.')
    args = parser.parse_args()
    source = args.base_python.resolve()
    venv = args.venv.resolve()
    model = args.model.resolve()
    output = args.output.resolve()
    if output.exists() or output.is_relative_to(ROOT):
        raise ValueError('Output must be a new directory outside the installed Skill.')
    required = [source/'python.exe', source/'python312.dll', source/'LICENSE.txt', source/'Lib/encodings',
                venv/'Lib/site-packages/qwen_tts', venv/'Lib/site-packages/torch']
    if not all(p.exists() for p in required):
        raise ValueError('Expected complete Windows CPython 3.12 and validated TTS dependencies.')
    if not (args.vc_redist/'msvcp140.dll').is_file():
        raise ValueError('A licensed x64 Visual Studio redistributable CRT directory is required.')
    manifest = json.loads((ROOT/'references/qwen-base-tts-manifest.json').read_text(encoding='utf-8-sig'))
    artifacts = []
    for item in manifest['artifacts']:
        relative = item['path'].replace('\\', '/').split('Qwen3-TTS-12Hz-1.7B-Base/', 1)[1]
        path = model / relative
        if path.is_symlink() or not path.is_file() or path.stat().st_size != item['bytes']:
            raise ValueError(f'Model input is missing or wrong-sized: {relative}')
        artifacts.append((relative, path, item['sha256']))
    print(json.dumps({'runtime_id': RUNTIME_ID, 'output': str(output),
                      'includes': ['CPython standard library and native DLLs', 'validated venv site-packages',
                                   'approved Base model allowlist', 'third-party license notices'],
                      'excludes': ['base Python site-packages and Codex tools', 'episodes and test renders',
                                   'caches, credentials, old render scripts', 'unrelated models']}, ensure_ascii=False), flush=True)
    if args.dry_run:
        return
    output.mkdir(parents=True)
    payload = output/'payload'
    python = payload/'python'
    python.mkdir(parents=True)
    for name in ('python.exe', 'python3.dll', 'python312.dll', 'vcruntime140.dll', 'vcruntime140_1.dll', 'LICENSE.txt'):
        shutil.copy2(source/name, python/name)
    copy_tree(source/'DLLs', python/'DLLs')
    (python/'Lib').mkdir()
    for child in sorted((source/'Lib').iterdir()):
        if child.name in {'site-packages', '__pycache__', 'test', 'idlelib', 'tkinter', 'turtledemo', 'ensurepip'}:
            continue
        if child.is_dir():
            copy_tree(child, python/'Lib'/child.name)
        elif child.suffix != '.pyc':
            shutil.copy2(child, python/'Lib'/child.name)
    copy_tree(venv/'Lib/site-packages', python/'Lib/site-packages')
    # Isolate this interpreter from registry, PYTHONPATH and user site-packages.
    (python/'python312._pth').write_text('.\nDLLs\nLib\nLib/site-packages\nimport site\n', encoding='ascii')
    target_model = payload/'models/Qwen3-TTS-12Hz-1.7B-Base'
    for relative, path, expected in artifacts:
        if digest(path) != expected:
            raise ValueError(f'Model checksum mismatch: {relative}')
        target = target_model/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    (payload/'licenses').mkdir()
    shutil.copy2(ROOT/'assets/licenses/Qwen3-TTS-APACHE2.txt', payload/'licenses/Qwen3-TTS-APACHE2.txt')
    (payload/'licenses/NOTICE.txt').write_text(
        'Portable AI Daily voice runtime. Unmodified CPython standard library and DLLs: Python Software Foundation license in python/LICENSE.txt.\n'
        'Qwen3-TTS-12Hz-1.7B-Base revision '+manifest['revision']+': Apache-2.0; see Qwen3-TTS-APACHE2.txt and model README.md.\n'
        'Python dependency licenses, copyright and notices are retained in python/Lib/site-packages/*dist-info and package license directories.\n'
        'The dependency version record is shipped with the Skill. Package metadata contains upstream project/source URLs.\n'
        'No Codex application, account state, global Python third-party packages, episode content, or private caches are bundled.\n', encoding='utf-8')
    records = [{'path': p.relative_to(payload).as_posix(), 'bytes': p.stat().st_size, 'sha256': digest(p)}
               for p in sorted(payload.rglob('*')) if p.is_file()]
    write_json(payload/'runtime-files.json', {'runtime_id': RUNTIME_ID, 'files': records})
    archive = output/'voice-runtime.zip'
    print(f'Archiving {len(records)} verified runtime files...', flush=True)
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as bundle:
        for path in sorted(payload.rglob('*')):
            if path.is_file():
                bundle.write(path, path.relative_to(payload).as_posix())
    archive_hash = digest(archive)
    parts = []
    with archive.open('rb') as stream:
        index = 1
        while True:
            block = stream.read(8 * 1024 * 1024)
            if not block:
                break
            path = output/f'voice-runtime.zip.part{index:03}'
            size = 0
            checksum = hashlib.sha256()
            with path.open('xb') as part:
                while block:
                    part.write(block); checksum.update(block); size += len(block)
                    if size >= 1504 * 1024 * 1024:
                        break
                    block = stream.read(8 * 1024 * 1024)
            parts.append({'name': path.name, 'bytes': size, 'sha256': checksum.hexdigest()})
            print(f'{path.name}: {size / 1024**3:.2f} GiB', flush=True)
            index += 1
    release = {'schema_version': 1, 'runtime_id': RUNTIME_ID, 'platform': 'windows-x86_64',
               'python': '3.12.14', 'model': manifest['repo'], 'model_revision': manifest['revision'],
               'release_tag': TAG, 'repository': 'GJZhou/ai-daily-video',
               'download_base': 'https://github.com/GJZhou/ai-daily-video/releases/download/'+TAG+'/',
               'archive_sha256': archive_hash, 'archive_bytes': archive.stat().st_size,
               'unpacked_bytes': sum(r['bytes'] for r in records),
               'runtime_files_sha256': digest(payload/'runtime-files.json'), 'parts': parts}
    add_vc_runtime(args.vc_redist.resolve(), output, release)
    print(json.dumps({'status': 'built', 'parts': len(parts), 'archive_GiB': round(archive.stat().st_size/1024**3, 3)}, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError) as error:
        print(f'Error: {error}', file=sys.stderr)
        sys.exit(1)
