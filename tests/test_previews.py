import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from catalog import canonical, Invalid
from previews import published, differences, verify
from preview_media import proof, scene_for


class PreviewProof(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        self.package=SimpleNamespace(id="com.example.hud",sha256="a"*64,pin={"sha256":"b"*64})
        self.sim=SimpleNamespace(info={"source_sha":"pinned","languages":["en"]})
        self.image=b'\x89PNG\r\n\x1a\n'+(13).to_bytes(4,'big')+b'IHDR'+(1920).to_bytes(4,'big')+(1080).to_bytes(4,'big')+b'fixture'
        self.digest=hashlib.sha256(self.image).hexdigest()
        self.manifest={"media":proof(),"complete":True,"package_sha256":self.package.sha256,"required":["playing"],"simulator":self.sim.info,"sdk":self.package.pin,
                       "scenes":[{"file":self.digest+".png","state":"playing","lang":"en","sha256":self.digest}]}

    def fetch(self,url,**kwargs):
        return io.BytesIO(canonical(self.manifest) if url.endswith('manifest.json') else self.image)

    def test_unchanged_package_reuses_only_its_full_pinned_hash_checked_matrix(self):
        with patch('previews.expected',return_value=['playing']),patch('previews.build_opener') as opener:
            opener.return_value.open.side_effect=self.fetch
            self.assertTrue(published(self.sim,self.package,self.root/'reused','https://example.invalid/huds'))
        self.assertEqual((self.root/'reused'/ (self.digest+'.png')).read_bytes(),self.image)

    def test_tampered_pixels_incomplete_matrix_and_different_compiler_do_not_reuse(self):
        for edit in (lambda: self.manifest.update(complete=False),lambda: self.manifest.update(required=[]),
                     lambda: self.manifest.update(simulator={"source_sha":"other"}),
                     lambda: self.manifest.update(sdk={"sha256":"c"*64}),
                     lambda: self.manifest.pop("sdk"),
                     lambda: self.manifest['scenes'][0].update(sha256='0'*64)):
            original=json.loads(json.dumps(self.manifest)); edit()
            with patch('previews.expected',return_value=['playing']),patch('previews.build_opener') as opener:
                opener.return_value.open.side_effect=self.fetch
                self.assertFalse(published(self.sim,self.package,self.root/'reused','https://example.invalid/huds'))
            self.manifest=original
            self.assertFalse((self.root/'reused').exists())

    def test_diff_pairs_by_state_even_when_published_content_filenames_differ(self):
        current,before=self.root/'current',self.root/'before'
        for directory,name in ((current,'current.png'),(before,'published-hash.png')):
            directory.mkdir(); (directory/name).write_bytes(self.image)
            (directory/'manifest.json').write_bytes(canonical({"scenes":[{"state":"playing","file":name}]}))
        with patch('previews.subprocess.run') as encoder:
            result=differences(current,before,self.root/'diff')
        self.assertEqual(result[0]['status'],'identical')
        encoder.assert_not_called()

    def test_old_film_matrix_cannot_reuse_the_same_package_and_sdk(self):
        self.manifest.pop('media')
        with patch('previews.expected',return_value=['playing']),patch('previews.build_opener') as opener:
            opener.return_value.open.side_effect=self.fetch
            self.assertFalse(published(self.sim,self.package,self.root/'reused','https://example.invalid/huds'))
        self.assertFalse((self.root/'reused').exists())

    def test_changed_scene_recipe_cannot_reuse_stale_background_pixels(self):
        self.manifest['media']['recipe_sha256']='0'*64
        with patch('previews.expected',return_value=['playing']),patch('previews.build_opener') as opener:
            opener.return_value.open.side_effect=self.fetch
            self.assertFalse(published(self.sim,self.package,self.root/'reused','https://example.invalid/huds'))

    def test_the_native_gallery_states_have_the_three_generated_styles(self):
        compact={'name':'sections-0-movie-paused-no-chapters','background':'dark','open':0}
        self.assertEqual(scene_for(compact),'coast')
        self.assertEqual(scene_for(dict(compact,open=3)),'daylight')
        self.assertEqual(scene_for(dict(compact,slot='up_next')),'neon')

    def test_unpinned_local_matrix_cannot_be_relabelled_with_a_replaced_development_sdk(self):
        # A native report can remain identical while a development artifact's fonts or renderer changes.
        self.manifest.pop('sdk')
        directory=self.root/'before'
        directory.mkdir()
        (directory/'manifest.json').write_bytes(canonical(self.manifest))
        (directory/(self.digest+'.png')).write_bytes(self.image)
        replacement=SimpleNamespace(id=self.package.id,sha256=self.package.sha256,pin={'sha256':'c'*64})
        with patch('previews.expected',return_value=['playing']),self.assertRaises(Invalid):
            verify(self.sim,replacement,directory)
