"""Original generated media for native HUD previews; no film assets or real Plex data."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import struct
import zlib

from catalog import Invalid, canonical, read_json

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "assets/preview-scenes"


def inputs():
    manifest = read_json(ART / "scenes.json")
    if manifest.get("format") != 1 or [s.get("id") for s in manifest.get("scenes", [])] != ["coast", "daylight", "neon"]:
        raise Invalid("generated preview scenes must declare coast, daylight and neon")
    for scene in manifest["scenes"]:
        name = scene["file"]
        if Path(name).name != name or not name.endswith('.png'):
            raise Invalid("unsafe generated preview image")
        path = ART / name
        data = path.read_bytes()
        if path.is_symlink() or len(data) > 8 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != scene["sha256"]:
            raise Invalid("generated preview image differs from its recorded source")
        if data[:8] != b'\x89PNG\r\n\x1a\n' or tuple(int.from_bytes(data[i:i+4], 'big') for i in (16, 20)) != (scene["width"], scene["height"]):
            raise Invalid("generated preview image dimensions differ")
        if not scene.get("origin") or not scene.get("prompt"):
            raise Invalid("generated preview image needs its generation provenance")
    return manifest


def proof():
    """Invalidate published reuse when source images or the fixture/adapter recipe changes."""
    recipe = hashlib.sha256()
    for name in ('preview_media.py', 'render_previews.py'):
        recipe.update((ROOT / 'scripts' / name).read_bytes())
    return {"kind": "original-ai-scenes", "inputs": inputs(), "recipe_sha256": recipe.hexdigest()}


def scene_for(spec):
    if spec["background"] == "bright" or spec["open"] == 3:
        return "daylight"
    if spec["name"] == "frame-dark" or spec.get("slot") == "up_next":
        return "neon"
    return "coast"


def catalog():
    def film(slug, title, scene):
        return {"id": slug, "title": title, "year": 2026, "originallyAvailableAt": "2026-01-01", "minutes": 15,
                "summary": "A traveler follows the changing weather toward a distant light.", "genres": ["Adventure"],
                "poster": {"asset": scene}, "art": {"asset": scene, "mode": "cover", "anchor": "center"}}
    after = film('after-rain', 'After the Rain', 'coast')
    after.update(media='coast-video', chapters=[{"start": start, "title": title} for start, title in
        [('0:00','The coast'),('1:41','A distant light'),('2:42','The crossing'),('5:53','Changing skies'),
         ('8:04','The headland'),('11:24','Homeward'),('12:24','Credits')]])
    show = {"id": "night-lines", "title": "Night Lines", "year": 2026, "genres": ["Drama"],
            "summary": "Three journeys through the city after dark.", "poster": {"asset": "neon"}, "art": {"asset": "neon"},
            "seasons": [{"index": 1, "episodes": [{"index": i, "title": title, "minutes": 15, "date": "2026-01-01",
                "thumb": {"asset": scene}, "summary": "A fictional episode for the native player preview."}
                for i, title, scene in [(1,'The last train','neon'),(2,'The beacon','coast'),(3,'Morning light','daylight')]]}]}
    return {"now": 1790000000, "server": {"friendlyName": "Generated preview library", "machineIdentifier": "plxnative-generated-preview"},
            "hero": "after-rain", "hero_alternatives": [], "sections": [{"key":"1","type":"movie","title":"Movies"},
            {"key":"2","type":"show","title":"TV Shows"}], "collections": [], "people": {},
            "movies": [film('painted-morning','Painted Morning','daylight'), after], "shows": [show],
            "added_order": ['after-rain','painted-morning','night-lines'], "collection_order": {},
            "continue_watching": [{"item":"after-rain","progress":.49}], "watched": [],
            "hubs": [{"title":"Movies","hubIdentifier":"movie.recentlyadded.1","type":"movie","recent":"movie"}]}


def empty_logo():
    """A technical transparent sentinel for the app's optional-logo probe, with no artwork."""
    def chunk(kind, data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(b'\0'*5))+chunk(b'IEND',b'')


def prepare(cache, demo):
    """Use the SDK's shared artwork deriver and a synthetic, silent H.264/AAC stream."""
    declaration = proof()
    key = hashlib.sha256(canonical(declaration)).hexdigest()
    directory = cache / key
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'derived').mkdir(exist_ok=True)
    (directory / 'src').mkdir(exist_ok=True)
    assets = {s['id']: {"sha256": s['sha256'], "url": s['file']} for s in declaration['inputs']['scenes']}
    for scene in declaration['inputs']['scenes']:
        name = scene['id']
        video = directory / 'src' / (name + '-video.mp4')
        digest = video.with_suffix('.sha256')
        if not video.is_file() or not digest.is_file() or hashlib.sha256(video.read_bytes()).hexdigest() != digest.read_text().strip():
            temporary = video.with_name(name + '-video.tmp.mp4')
            # Match ordinary video cadence so the SDK's streaming decoder receives enough
            # access units to produce a picture before clockstop. A two-second GOP
            # also bounds backward seeks within the SDK's ten-second preroll.
            subprocess.run(['ffmpeg','-v','error','-y','-loop','1','-framerate','24','-i',str(ART / scene['file']),
                '-f','lavfi','-i','anullsrc=r=48000:cl=stereo','-t','900',
                '-vf','scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1',
                '-c:v','libx264','-preset','ultrafast','-tune','stillimage','-crf','24','-g','48','-pix_fmt','yuv420p',
                '-threads','2','-filter_threads','1','-c:a','aac','-b:a','32k','-movflags','+faststart',str(temporary)],check=True,timeout=600)
            temporary.replace(video)
            digest.write_text(hashlib.sha256(video.read_bytes()).hexdigest()+'\n')
        assets[name+'-video'] = {"url": video.name, "sha256": hashlib.sha256(video.read_bytes()).hexdigest()}
    assets['empty-logo'] = {"url":"empty-logo.png","sha256":hashlib.sha256(empty_logo()).hexdigest()}
    data = catalog()
    records = [(m['id'],m) for m in data['movies']] + [(s['id'],s) for s in data['shows']]
    records += [(f"{s['id']}/{season['index']}/{e['index']}",e) for s in data['shows'] for season in s['seasons'] for e in season['episodes']]
    sources = {s['id']: ART / s['file'] for s in declaration['inputs']['scenes']}
    for slug, record in records:
        # Home probes the optional logo even when the server omits its metadata key. Keep that
        # request explicitly empty instead of inventing a film logo or borrowing existing art.
        record['logo'] = {'asset':'empty-logo'}
        logo = demo.derived_file(assets,directory,slug,record,'logo')
        logo.parent.mkdir(parents=True,exist_ok=True)
        logo.write_bytes(empty_logo())
        for role in ('poster','art','thumb'):
            if role not in record:
                continue
            target = demo.derived_file(assets,directory,slug,record,role)
            target.parent.mkdir(parents=True,exist_ok=True)
            if not target.is_file():
                demo.derive_image(sources[record[role]['asset']],target,demo.SIZES[role],record[role])
    (directory/'assets.json').write_bytes(canonical({"assets":assets}))
    path = directory/'catalog.json'
    path.write_bytes(canonical(data))
    return directory, path


def fixture(spec, hud, native, directory):
    original = native.fixture(spec, hud)
    def apply(pms, runtime):
        source = pms.lib.items[102]
        part = source['Media'][0]['Part'][0]['id']
        video = directory/'src'/(scene_for(spec)+'-video.mp4')
        media, duration = pms.lib._verified_media(video,102,part)
        source.update(Media=[media],duration=duration)
        # The SDK supplies the real player states, menu geometry and episode setup unchanged.
        original(pms,runtime)
    return apply
