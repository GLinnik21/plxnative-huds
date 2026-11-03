"""Deliberately incompatible app-release protocol fixtures exercise the complete registry pipeline.

These tiny executables are explicitly test fixtures, never app release artifacts. The production
Simulator still verifies/extracts their pinned bytes and invokes real child processes; no network,
GitHub write, native UI or compiler correctness is claimed by this protocol integration test.
"""
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from catalog import Invalid, canonical, packages, read_json
from calibrate import RENDERER_FILES
from releases import accept
from recheck import recheck


class ReleasePipeline(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        self.cache=self.root/'cache'; self.cache.mkdir()
        self.calibration=self.root/'calibration'; self.calibration.mkdir()
        source=ROOT/'huds/com.plxnative.examples.minimal/hud.plxhud.json'
        value=json.loads(source.read_text()); self.ident=value['id']
        target=self.root/'huds'/self.ident; target.mkdir(parents=True)
        (target/'hud.plxhud.json').write_bytes(source.read_bytes())
        (target/'README.md').write_text('Protocol fixture\n')
        (self.root/'revoked.json').write_text('[]')
        (self.root/'compatibility.json').write_bytes(canonical({'format':1,'packages':{}}))
        (self.root/'maintainers.json').write_bytes(canonical({self.ident:['example-author']}))
        self.package=packages(self.root)[0]
        self.original=self.package.content
        self.tv={'protocol':1,'source_sha':'native-test-fixture','font_hashes':{'face':'same-bytes'},'metrics':[
            {'lang':lang,'rung':'BODY','size':28,'bold':bold,'role':'label','text':'label','width':100}
            for lang in ('en','de') for bold in (False,True)]}
        (self.calibration/'tv-metrics.json').write_bytes(canonical(self.tv))
        (self.root/'toolchains.json').write_bytes(canonical({'format':1,'simulators':[]}))

    def release(self,version,source,mode):
        stage=self.root/('bundle-'+version); (stage/'bin').mkdir(parents=True)
        info={'protocol':1,'app_version':version,'source_sha':source[:9],'formats':['1.0'],
              'languages':['en','de'],'rungs':{'BODY':28}}
        findings=[]
        if mode=='translation':
            findings=[{'code':'HUD-E0601','path':'/layout/block/0','message':'Test release lengthened German text',
                       'context':{'lang':'de'}}]
        elif mode=='invariant':
            findings=[{'code':'HUD-E1001','path':'/layout','message':'Deliberately incompatible non-text rule'}]
        program=('#!/usr/bin/env python3\nimport json,sys\n'
                 f'info=json.loads({json.dumps(info)!r})\n'
                 f'findings=json.loads({json.dumps(findings)!r})\n'
                 'if sys.argv[1]=="--hud-info":\n print(json.dumps(info))\nelse:\n'
                 ' print(json.dumps({"findings":findings,"costs":[]}))\n sys.exit(bool(findings))\n')
        binary=stage/'bin/plxnative-sim'; binary.write_text(program); binary.chmod(0o755)
        host={**self.tv,'source_sha':source[:9],'app_version':version,
              'metrics':[{**row,'text':('Ein deutlich längerer deutscher Text' if mode=='translation' and row['lang']=='de' else row['text'])} for row in self.tv['metrics']]}
        (stage/'text-metrics.json').write_bytes(canonical(host))
        renderer_files={}
        for name in RENDERER_FILES:
            path=stage/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(b'Protocol fixture renderer identity')
            renderer_files[name]=hashlib.sha256(path.read_bytes()).hexdigest()
        manifest={'protocol':1,'app_version':version,'reported_version':version,'development':False,
                  'source_sha':source,'formats':['1.0'],'font_hashes':self.tv['font_hashes'],
                  'files':{**renderer_files,'bin/plxnative-sim':hashlib.sha256(binary.read_bytes()).hexdigest(),
                           'text-metrics.json':hashlib.sha256((stage/'text-metrics.json').read_bytes()).hexdigest()}}
        (stage/'bundle.json').write_bytes(canonical(manifest))
        archive=self.root/(version+'.tar.gz')
        with tarfile.open(archive,'w:gz') as tar:
            for path in sorted(stage.rglob('*')):
                if path.is_file(): tar.add(path,arcname=str(path.relative_to(stage)))
        digest=hashlib.sha256(archive.read_bytes()).hexdigest()
        (self.cache/(digest+'.tar.gz')).write_bytes(archive.read_bytes())
        return {'app_version':version,'source_sha':source,'formats':['1.0'],'development':False,
                'sha256':digest,'manifest_sha256':hashlib.sha256((stage/'bundle.json').read_bytes()).hexdigest(),
                'bytes':archive.stat().st_size,'url':'https://github.com/GLinnik21/plx-native/releases/download/v'+version+'/sim.tar.gz'}

    def test_release_translation_regression_notifies_author_without_rewriting_pack(self):
        baseline=self.release('0.10.0','a'*40,'clean')
        incompatible=self.release('0.11.0','b'*40,'translation')
        self.assertTrue(accept(self.root,self.cache,baseline))
        original_pin=read_json(self.root/'toolchains.json')['simulators'][0]
        self.assertTrue(accept(self.root,self.cache,incompatible))
        self.assertFalse(accept(self.root,self.cache,incompatible),'repeat dispatch is idempotent')
        carried=read_json(self.root/read_json(self.root/'toolchains.json')['simulators'][1]['calibration'])
        self.assertEqual(carried['measured_host_source_sha'],'a'*9)
        self.assertEqual(carried['host_source_sha'],'b'*9)
        self.assertEqual(carried['carried_from'],'a'*9)
        with patch('recheck.notify') as notify:
            result=recheck(self.root,self.cache,{'format':1,'packages':{}},notify_repo='example/registry')
        entry=result['packages'][self.package.sha256]
        self.assertEqual(entry['unfit'],[{'from':'0.11.0','langs':['de']}])
        self.assertNotIn('app_max',entry)
        self.assertEqual(read_json(self.root/'toolchains.json')['simulators'][0],original_pin)
        notify.assert_called_once()
        self.assertEqual(notify.call_args.args[3]['langs'],['de'])
        self.assertEqual(self.package.path.read_bytes(),self.original)

    def test_changed_text_cannot_invent_headroom_without_matching_renderer(self):
        accept(self.root,self.cache,self.release('0.10.0','a'*40,'clean'))
        baseline=read_json(self.root/'toolchains.json')['simulators'][0]
        path=self.root/baseline['calibration']; profile=read_json(path)
        profile['renderer_hashes'][RENDERER_FILES[0]]='0'*64
        path.write_bytes(canonical(profile))
        with self.assertRaisesRegex(Invalid,'matching measured renderer'):
            accept(self.root,self.cache,self.release('0.11.0','b'*40,'translation'))
        self.assertEqual(len(read_json(self.root/'toolchains.json')['simulators']),1)

    def test_nontext_failure_caps_at_last_pass_then_a_repaired_release_restores_range(self):
        for version,source,mode in [('0.10.0','a'*40,'clean'),('0.11.0','b'*40,'invariant')]:
            accept(self.root,self.cache,self.release(version,source,mode))
        result=recheck(self.root,self.cache,{'format':1,'packages':{}})
        entry=result['packages'][self.package.sha256]
        self.assertEqual(entry['app_max'],'0.10.0')
        self.assertEqual(entry['unfit'],[{'from':'0.11.0','langs':['de','en']}])
        accept(self.root,self.cache,self.release('0.12.0','c'*40,'clean'))
        repaired=recheck(self.root,self.cache,result)['packages'][self.package.sha256]
        self.assertNotIn('app_max',repaired)
        self.assertEqual(repaired['unfit'][-1],{'from':'0.12.0','langs':[]})
        self.assertEqual(self.package.path.read_bytes(),self.original)


if __name__=='__main__':
    unittest.main()
