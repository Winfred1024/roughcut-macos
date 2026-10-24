import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'deploy'))
sys.path.insert(0, str(ROOT / 'payload/skill/local-video-rough-cut-jianying/scripts'))
import install_macos
import mac_common
import roughcut_cli
import subtitle_module


class DraftSafetyTests(unittest.TestCase):
    def test_backup_failure_keeps_existing_skill(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); source = root / 'source'; target = root / 'target'
            source.mkdir(); target.mkdir(); (source / 'SKILL.md').write_text('# 本地视频粗剪并生成剪映草稿\n')
            (target / 'user-file').write_text('keep me')
            with patch.object(Path, 'rename', side_effect=PermissionError('occupied')):
                with self.assertRaises(PermissionError):
                    install_macos.install_skill(source, target, {'config_path':'config','draft_root':'drafts'})
            self.assertEqual((target / 'user-file').read_text(), 'keep me')

    def test_replacement_failure_restores_backup(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); source=root/'source'; target=root/'target'
            source.mkdir(); target.mkdir(); (source/'SKILL.md').write_text('# 本地视频粗剪并生成剪映草稿\n')
            (target/'user-file').write_text('original')
            original = Path.rename
            def rename(path, dest):
                if '.roughcut-stage-' in str(path):
                    raise OSError('disk error')
                return original(path, dest)
            with patch.object(Path, 'rename', rename):
                with self.assertRaises(OSError):
                    install_macos.install_skill(source,target,{'config_path':'config','draft_root':'drafts'})
            self.assertEqual((target/'user-file').read_text(), 'original')

    def test_atomic_draft_write_preserves_original_on_failure(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t); (p/'draft_content.json').write_text('{"original": true}')
            with patch.object(subtitle_module.os, 'replace', side_effect=OSError('disk error')):
                with self.assertRaises(OSError):
                    subtitle_module._write_draft(p, {'changed':True})
            self.assertEqual(json.loads((p/'draft_content.json').read_text()), {'original':True})

    def test_titles_require_explicit_all_text_flag(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t); d={'materials':{'texts':[{'id':'t','content':json.dumps({'text':'标题'}),'type':'text'}]},
                         'tracks':[{'type':'text','name':'标题','segments':[{'material_id':'t','target_timerange':{'duration':1000000}}]}]}
            (p/'draft_content.json').write_text(json.dumps(d))
            with self.assertRaises(ValueError):
                subtitle_module.promote_draft_to_subtitles(p)
            self.assertEqual(json.loads((p/'draft_content.json').read_text()), d)
            subtitle_module.promote_draft_to_subtitles(p,prefer_subtitle_tracks_only=False)
            self.assertEqual(json.loads((p/'draft_content.json').read_text())['materials']['texts'][0]['type'],'subtitle')


class PlanTests(unittest.TestCase):
    def validate(self, clips):
        with patch.object(roughcut_cli, 'probe', return_value={'duration':10,'path':'/video.mov'}):
            return roughcut_cli.validate_plan({'clips':clips},Path('/tmp'))

    def test_valid_source_ranges(self):
        out=self.validate([{'source':'x.mov','start':1,'end':4,'subtitles':[{'start':1.2,'end':3.5,'text':'口播'}]}])
        self.assertEqual(out[0]['source'],'/video.mov')

    def test_out_of_bounds_and_non_finite_ranges(self):
        for start,end in [(-1,2),(0,11),(3,2),(0,float('nan'))]:
            with self.subTest(start=start,end=end), self.assertRaises(ValueError):
                self.validate([{'source':'x','start':start,'end':end}])

    def test_subtitles_cannot_cross_cut(self):
        with self.assertRaises(ValueError):
            self.validate([{'source':'x','start':1,'end':4,'subtitles':[{'start':0.5,'end':2,'text':'跨切点'}]}])

    def test_overlapping_subtitles_rejected(self):
        with self.assertRaises(ValueError):
            self.validate([{'source':'x','start':0,'end':4,'subtitles':[
                {'start':0,'end':2,'text':'甲'},{'start':1,'end':3,'text':'乙'}]}])

    def test_rotation_in_both_directions(self):
        import subprocess
        with tempfile.NamedTemporaryFile(suffix='.mov') as f:
            for rotation in [-90,90,270]:
                d={'format':{'duration':'5'},'streams':[{'codec_type':'video','width':1920,'height':1080,
                                                       'side_data_list':[{'rotation':rotation}]}]}
                with patch.object(roughcut_cli.subprocess,'run',return_value=subprocess.CompletedProcess([],0,json.dumps(d))):
                    result=roughcut_cli.probe(f.name)
                    self.assertEqual((result['width'],result['height']),(1080,1920))

    def test_portrait_without_rotation_keeps_dimensions(self):
        import subprocess
        with tempfile.NamedTemporaryFile() as f:
            d={'format':{'duration':'5'},'streams':[{'codec_type':'video','width':1080,'height':1920}]}
            with patch.object(roughcut_cli.subprocess,'run',return_value=subprocess.CompletedProcess([],0,json.dumps(d))):
                result=roughcut_cli.probe(f.name)
                self.assertEqual((result['width'],result['height']),(1080,1920))

class MacIdentityTests(unittest.TestCase):
    def test_mac_active_timeline_and_unique_identity(self):
        from mac_draft import finalize_draft
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); ids=[]
            for name in ['甲', '乙']:
                p=root/name; p.mkdir()
                (p/'draft_content.json').write_text(json.dumps({'duration':3000000,'id':'STATIC','platform':{'os':'windows'}}))
                (p/'draft_meta_info.json').write_text(json.dumps({'draft_id':'STATIC'}))
                ids.append(finalize_draft(p,root))
                d=json.loads((p/'draft_info.json').read_text())
                meta=json.loads((p/'draft_meta_info.json').read_text())
                self.assertEqual(d['platform']['os'],'mac')
                self.assertEqual(d['new_version'],'103.0.0')
                self.assertEqual(d,json.loads((p/'draft_content.json').read_text()))
                self.assertEqual(meta['draft_id'],d['id'])
                self.assertEqual(meta['draft_name'],name)
                self.assertEqual(meta['tm_duration'],3000000)
            self.assertNotEqual(*ids)


class DurationTests(unittest.TestCase):
    def test_container_audio_tail_does_not_extend_video_clip(self):
        import subprocess
        with tempfile.NamedTemporaryFile() as f:
            data={'format':{'duration':'9.530431'},'streams':[{'codec_type':'video','width':540,'height':960,'duration':'9.5'}]}
            with patch.object(roughcut_cli.subprocess,'run',return_value=subprocess.CompletedProcess([],0,json.dumps(data))):
                result=roughcut_cli.probe(f.name)
                self.assertEqual(result['duration'],9.5)
                self.assertEqual(result['container_duration'],9.530431)


if __name__ == '__main__':
    unittest.main()
