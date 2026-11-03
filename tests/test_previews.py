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
from catalog import canonical
from previews import published, differences


class PreviewProof(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        self.package=SimpleNamespace(id="com.example.hud",sha256="a"*64)
        self.sim=SimpleNamespace(info={"source_sha":"pinned","languages":["en"]})
        self.image=b'\x89PNG\r\n\x1a\n'+(13).to_bytes(4,'big')+b'IHDR'+(1920).to_bytes(4,'big')+(1080).to_bytes(4,'big')+b'fixture'
        self.digest=hashlib.sha256(self.image).hexdigest()
        self.manifest={"complete":True,"package_sha256":self.package.sha256,"required":["playing"],"simulator":self.sim.info,
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
