"""Compose original media fixtures with the pinned SDK's native screenshot and HUD state tools."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

import preview_media


def render(sdk, binary, hud, output, cache, only=None, sdk_pin=None):
    if sdk_pin is not None:
        from simulator import verify_bundle
        verify_bundle(sdk, sdk_pin)
    sys.path.insert(0,str(sdk/'tools'))
    import hud_preview as native
    directory, catalog = preview_media.prepare(cache, native.screenshots.demo_library)
    os.environ['PLXNATIVE_DEMO_CACHE'] = str(directory)
    native.screenshots.CATALOG = catalog
    env = {k:v for k,v in os.environ.items() if not k.startswith('PLXNATIVE_')}
    env['PLXNATIVE_APP_DIR'] = str(sdk/'pkg')
    with native.snapshot(binary,hud,env=env) as package:
        matrix = native.plan(package.inspection)
        selected = [s for s in matrix if only is None or s['name'] in only]
        if only is not None and set(only) != {s['name'] for s in selected}:
            raise ValueError('unknown preview scene selection')
        output.mkdir(parents=True,exist_ok=True)
        scenes=[]
        for spec in selected:
            png,log=native.screenshots.capture(binary,native.capture_scene(spec),native.DEFAULTS,'after-rain',False,
                prepare=preview_media.fixture(spec,package.path,native,directory),assets=sdk/'pkg')
            name=spec['name']+'.png'
            (output/name).write_bytes(png)
            (output/(spec['name']+'.log')).write_text(log)
            scenes.append({'file':name,'sha256':hashlib.sha256(png).hexdigest(),'state':spec['name'],'lang':spec['lang']})
        manifest={'protocol':1,'package_sha256':package.sha256,'simulator':package.info,'media':preview_media.proof(),
            'required':[s['name'] for s in matrix],'complete':len(selected)==len(matrix),'scenes':scenes}
        if sdk_pin is not None:
            manifest['sdk'] = sdk_pin
        (output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
        return manifest


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('sdk','bin','hud','out','cache'):
        ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--only')
    ap.add_argument('--sdk-pin', help='Exact verified SDK pin; required for publishable output')
    args=ap.parse_args()
    render(args.sdk.resolve(),args.bin.resolve(),args.hud.resolve(),args.out.resolve(),args.cache.resolve(),args.only.split(',') if args.only else None,json.loads(args.sdk_pin) if args.sdk_pin else None)


if __name__=='__main__':
    main()
