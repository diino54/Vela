"""Verify real scene blur on a static checkerboard, sharp HUD text and clean off state."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from PIL import Image,ImageChops,ImageStat
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from vela import mangohud,runtime
from native_capture import capture

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend',choices=('opengl','vulkan'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--vulkan-checker',type=Path)
    parser.add_argument('--validation',type=Path)
    parser.add_argument('--srgb',action='store_true')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    base=('position=top-left\noffset_x=120\noffset_y=80\nwidth=360\nlegacy_layout=0\n'
          'background_alpha=0\nround_corners=12\nfont_size=32\nfont_size_secondary=32\n'
          'text_color=FFFFFF\ntext_outline=0\nfps=0\nframetime=0\nframe_timing=0\ngpu_stats=0\ncpu_stats=0\ncustom_text=SHARP\n')
    results=[]
    with tempfile.TemporaryDirectory(prefix='vela-blur-test-') as directory:
        directory=Path(directory);config=directory/'hud.conf'
        config.write_text(mangohud.managed_content(base,60,'early',True,{'vela_background_blur':0}))
        env=runtime.environment(directory);env.update(MANGOHUD_CONFIGFILE=str(config),DISABLE_LSFGVK='1',QT_QPA_PLATFORM='xcb')
        env.pop('MANGOHUD_CONFIG',None)
        if args.srgb: env['VELA_TEST_SRGB']='1'
        if args.validation:
            env['VK_ADD_LAYER_PATH']+=os.pathsep+str(args.validation)
            env['VK_INSTANCE_LAYERS']+=':VK_LAYER_KHRONOS_validation'
            env['VK_LAYER_VALIDATE_SYNC']='1'
        command=([sys.executable,'-B',str(ROOT/'tests/blur_checker_gl.py')] if args.backend=='opengl' else [str(args.vulkan_checker)])
        with (args.output/'renderer.log').open('w') as log:
            child=subprocess.Popen(command,env=env,stdout=log,stderr=log)
            try:
                time.sleep(2)
                assert child.poll() is None,'Renderer failed to start'
                frames=[]
                for name,radius in [('off',0),('blur12',12),('blur24',24),('blur32',32),('off-again',0)]:
                    mangohud.replace_watched(config,mangohud.managed_content(base,60,'early',True,{'vela_background_blur':radius}).encode())
                    time.sleep(1)
                    assert child.poll() is None,'Renderer exited'
                    target=args.output/(name+'.png');capture(child.pid,target)
                    image=Image.open(target).convert('RGB');frames.append(image.copy())
                    deviation=ImageStat.Stat(image.crop((240,88,300,108)).convert('L')).stddev[0]
                    results.append(dict(state=name,radius=radius,scene_stddev=deviation));print(results[-1],flush=True)
                assert results[1]['scene_stddev']<results[0]['scene_stddev']*.35,results
                assert results[2]['scene_stddev']<results[0]['scene_stddev']*.35,results
                assert results[3]['scene_stddev']<results[0]['scene_stddev']*.35,results
                for image in frames[1:]:
                    original_mean=ImageStat.Stat(frames[0].crop((430,92,450,104))).mean
                    blurred_mean=ImageStat.Stat(image.crop((430,92,450,104))).mean
                    assert max(abs(a-b) for a,b in zip(original_mean,blurred_mean))<=2,('Uniform color changed',original_mean,blurred_mean)
                    assert ImageChops.difference(frames[0].crop((20,20,80,80)),image.crop((20,20,80,80))).getbbox() is None,'Scene outside HUD changed'
                assert ImageChops.difference(frames[0],frames[-1]).getbbox() is None,'Off state did not restore the original scene'
                def white_mask(image):
                    r,g,b=image.crop((120,80,260,125)).split()
                    return ImageChops.multiply(ImageChops.multiply(r.point(lambda x:255 if x>=255 else 0),g.point(lambda x:255 if x>=255 else 0)),b.point(lambda x:255 if x>=255 else 0))
                original=white_mask(frames[0]);count=ImageStat.Stat(original).sum[0]
                assert count>0,'HUD text missing'
                for frame in frames[1:-1]:
                    overlap=ImageStat.Stat(ImageChops.multiply(original,white_mask(frame))).sum[0]/count
                    assert overlap>.98,('Text lost sharpness',overlap)
                print('PASS: scene is blurred, text stays sharp, outside unchanged, off restores original',flush=True)
            finally:
                child.terminate();child.wait(timeout=10)
                (args.output/'measurements.json').write_text(json.dumps(results,indent=2))
    if args.validation:
        log=(args.output/'renderer.log').read_text()
        assert 'Validation Error' not in log and 'SYNC-HAZARD' not in log,log[-4000:]

if __name__=='__main__':main()
