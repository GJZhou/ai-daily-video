#!/usr/bin/env python3
"""Offline reference-driven Qwen3-TTS helper; output belongs to the current episode."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / 'assets/audio-reference/reference-driven-v1/声音参考配置.json'

def resolve(value):
    p = Path(value)
    return p if p.is_absolute() else ROOT / p

def load_config(path):
    cfg = json.loads(path.read_text(encoding='utf-8-sig'))
    if cfg.get('model') != 'Qwen/Qwen3-TTS-12Hz-1.7B-Base':
        raise ValueError('Expected the approved reference-driven Base model.')
    if cfg.get('icl_mode') is not True or cfg.get('x_vector_only_mode') is not False:
        raise ValueError('Full ICL with the exact reference transcript is required.')
    if cfg['runtime'].get('offline') is not True:
        raise ValueError('The helper requires offline local inference.')
    for name, item in cfg['files'].items():
        source = resolve(item['path'])
        if hashlib.sha256(source.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError(f'Reference checksum mismatch: {name}')
    runtime = cfg['runtime']
    for key in ('python_executable','dependency_record','model_manifest','license_file'):
        if not resolve(runtime[key]).is_file():
            raise FileNotFoundError(f'Missing runtime binding: {key}')
    model_dir = resolve(runtime['model_directory'])
    manifest = json.loads(resolve(runtime['model_manifest']).read_text(encoding='utf-8-sig'))
    if manifest['revision'] != cfg['model_revision'] or manifest['repo'] != cfg['model']:
        raise ValueError('Model revision does not match the packaged source manifest.')
    for item in manifest['artifacts']:
        normalized = item['path'].replace(chr(92),'/')
        relative = normalized.split('Qwen3-TTS-12Hz-1.7B-Base/',1)[1]
        artifact = model_dir / relative
        if not artifact.is_file() or artifact.stat().st_size != item['bytes']:
            raise ValueError(f'Missing or incorrect model artifact: {relative}')
    for name in ('torch','qwen_tts','soundfile','numpy'):
        if importlib.util.find_spec(name) is None:
            raise RuntimeError(f'Missing dependency: {name}; use the configured Python environment.')
    return cfg, model_dir

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=DEFAULT_CONFIG)
    parser.add_argument('--check',action='store_true',help='Verify local references and runtime without loading the model.')
    parser.add_argument('--text-file',type=Path,help='Approved UTF-8 narration; blank lines separate paragraphs.')
    parser.add_argument('--output',type=Path,help='New WAV output outside the Skill directory.')
    args=parser.parse_args()
    cfg, model_dir=load_config(args.config.resolve())
    if args.check:
        print(json.dumps({'status':'local-files-ready','model':cfg['model'],
                          'revision':cfg['model_revision'],'model_directory':str(model_dir),
                          'reference_hashes_verified':len(cfg['files']),
                          'model_integrity_check':'expected files and sizes; full hashes remain in manifest',
                          'model_loaded':False,'audio_generated':False},ensure_ascii=False))
        return
    if args.text_file is None or args.output is None:
        parser.error('Use --check, or provide both --text-file and --output.')
    output=args.output.resolve()
    if output.suffix.lower() != '.wav':
        parser.error('--output must be a WAV file.')
    if output.is_relative_to(ROOT):
        parser.error('Write episode output outside the installed Skill directory.')
    if output.exists():
        raise FileExistsError('Output already exists; choose a new versioned filename.')
    text=args.text_file.read_text(encoding='utf-8-sig').strip()
    paragraphs=[p.strip() for p in re.split(chr(10)+'[ '+chr(9)+']*'+chr(10),text) if p.strip()]
    if not paragraphs:
        raise ValueError('Narration is empty.')
    for name in ('HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE'):
        os.environ[name]='1'
    os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
    os.environ['DO_NOT_TRACK']='1'
    import numpy as np
    import soundfile as sf
    import torch
    from qwen_tts import Qwen3TTSModel
    from transformers import set_seed
    torch.set_num_threads(int(cfg['runtime'].get('cpu_threads', 6)))
    set_seed(int(cfg['seed']))
    model=Qwen3TTSModel.from_pretrained(str(model_dir),device_map='cpu',
        dtype=torch.float32,attn_implementation='eager',local_files_only=True)
    reference=resolve(cfg['files']['参考音频.wav']['path'])
    transcript=resolve(cfg['files']['参考原文.txt']['path']).read_text(encoding='utf-8-sig').strip()
    with torch.inference_mode():
        prompt=model.create_voice_clone_prompt(ref_audio=str(reference),ref_text=transcript,
                                               x_vector_only_mode=False)
        audio=[]
        sample_rate=None
        for index, paragraph in enumerate(paragraphs):
            wavs, sr=model.generate_voice_clone(text=paragraph,language='Chinese',
                voice_clone_prompt=prompt,temperature=float(cfg['temperature']))
            if sample_rate is not None and sr != sample_rate:
                raise RuntimeError('Unexpected sample-rate change between paragraphs.')
            if index:
                audio.append(np.zeros(round(sr*0.5),dtype=np.float32))
            wave=np.asarray(wavs[0],dtype=np.float32)
            if wave.ndim != 1 or not wave.size or not np.isfinite(wave).all():
                raise RuntimeError('Model returned invalid audio.')
            audio.append(wave);sample_rate=sr
            print(f'Paragraph {index+1}/{len(paragraphs)} generated.',flush=True)
    output.parent.mkdir(parents=True,exist_ok=True)
    # Reserve a new filename only after inference; never truncate an existing file.
    with output.open('xb') as stream:
        sf.write(stream,np.concatenate(audio),sample_rate,format='WAV',subtype='PCM_16')
    print(json.dumps({'output':str(output),'sample_rate':sample_rate,
                      'seconds':sum(len(w) for w in audio)/sample_rate,
                      'paragraphs':len(paragraphs),'listening_approval':'pending'},ensure_ascii=False))

if __name__=='__main__':
    try:
        main()
    except (OSError,ValueError,RuntimeError,KeyError,IndexError) as error:
        print(f'Error: {error}',file=sys.stderr)
        sys.exit(1)
