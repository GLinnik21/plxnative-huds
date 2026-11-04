import json
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import preview_media
from catalog import Invalid


class GeneratedMedia(unittest.TestCase):
    def test_every_source_has_a_verified_generation_record(self):
        declaration=preview_media.inputs()
        self.assertEqual([s['id'] for s in declaration['scenes']],['coast','daylight','neon'])
        self.assertTrue(all(s['prompt'] and s['origin'] and len(s['sha256'])==64 for s in declaration['scenes']))

    def test_a_changed_image_is_refused_before_rendering(self):
        with tempfile.TemporaryDirectory() as temporary:
            art=Path(temporary)/'art'
            shutil.copytree(preview_media.ART,art)
            image=art/'coast.png'
            image.write_bytes(image.read_bytes()+b'tampered')
            with patch('preview_media.ART',art), self.assertRaises(Invalid):
                preview_media.inputs()

    def test_catalog_art_and_media_refer_only_to_generated_sources(self):
        cat=preview_media.catalog()
        self.assertEqual(cat['movies'][1]['id'],'after-rain') # SDK state fixture's item102
        self.assertEqual(len(cat['shows'][0]['seasons'][0]['episodes']),3)
        self.assertNotIn('sintel',json.dumps(cat).lower())
        records=cat['movies']+cat['shows']+cat['shows'][0]['seasons'][0]['episodes']
        for record in records:
            for role in ('poster','art','thumb'):
                if role in record:
                    self.assertIn(record[role]['asset'],{'coast','daylight','neon'})
        self.assertEqual(cat['movies'][1]['media'],'coast-video')

    def test_generated_video_is_bound_before_the_native_sdk_builds_episode_states(self):
        spec={'name':'up-next','background':'dark','open':0,'slot':'up_next'}
        source={'Media':[{'Part':[{'id':103}]}]}
        media={'Part':[{'id':103,'key':'generated-only'}]}
        lib=SimpleNamespace(items={102:source},_verified_media=Mock(return_value=(media,900000)))
        def original(pms,runtime):
            self.assertIs(pms.lib.items[102]['Media'][0],media)
        native=SimpleNamespace(fixture=Mock(return_value=original))
        prepare=preview_media.fixture(spec,Path('sample.plxhud'),native,Path('generated'))
        prepare(SimpleNamespace(lib=lib),Path('runtime'))
        lib._verified_media.assert_called_once_with(Path('generated/src/neon-video.mp4'),102,103)
        native.fixture.assert_called_once_with(spec,Path('sample.plxhud'))

    def test_the_optional_logo_probe_has_no_film_or_placeholder_ink(self):
        import struct
        import zlib
        image=preview_media.empty_logo()
        self.assertEqual(struct.unpack('>II',image[16:24]),(1,1))
        offset=image.index(b'IDAT')
        size=int.from_bytes(image[offset-4:offset],'big')
        self.assertEqual(zlib.decompress(image[offset+4:offset+4+size]),b'\0'*5)
