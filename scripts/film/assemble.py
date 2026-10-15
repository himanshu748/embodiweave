"""ffmpeg audio/caption assembly, derivatives and verifiable film receipts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import textwrap
from PIL import Image, ImageDraw

from scripts.film.render import ROOT, OUT, font, W, H


def run(*args):
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *map(str,args)], check=True)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def burn_captions(record, subtitles):
    def clock(value):
        h,m,s=value.replace(',', '.').split(':')
        return int(h)*3600+int(m)*60+float(s)
    captions=[]
    for block in subtitles.read_text().strip().split('\n\n'):
        lines=block.splitlines();a,b=lines[1].split(' --> ')
        captions.append((clock(a),clock(b),' '.join(lines[2:])))
    args=['ffmpeg','-hide_banner','-loglevel','error','-i',str(OUT/'picture-v2.mp4')]
    if (OUT/'scene-06.mp4').exists():
        scene=next(s for s in record['scenes'] if s['id']==6)
        args+=['-i',str(OUT/'scene-06.mp4'),'-filter_complex',
            f"[0:v]split[a][b];[a]trim=end={scene['start']},setpts=PTS-STARTPTS[pre];"
            f"[1:v]setpts=PTS-STARTPTS[mid];[b]trim=start={scene['start']+scene['duration']},setpts=PTS-STARTPTS[post];"
            '[pre][mid][post]concat=n=3:v=1:a=0[v]','-map','[v]']
    args+=['-an','-pix_fmt','rgb24','-f','rawvideo','pipe:1']
    decoder=subprocess.Popen(args,stdout=subprocess.PIPE)
    encoder=subprocess.Popen(['ffmpeg','-y','-hide_banner','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24',
        '-s',f'{W}x{H}','-r','30','-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','21',
        '-maxrate','2600k','-bufsize','5200k','-pix_fmt','yuv420p','-movflags','+faststart',str(OUT/'captioned-v2.mp4')],stdin=subprocess.PIPE)
    index=0
    try:
        while True:
            raw=decoder.stdout.read(W*H*3)
            if not raw:break
            if len(raw)!=W*H*3:raise RuntimeError('Incomplete decoded frame')
            image=Image.frombytes('RGB',(W,H),raw)
            active=next((value for a,b,value in captions if a<=index/30<b),None)
            if active:
                draw=ImageDraw.Draw(image)
                lines=textwrap.wrap(active,width=76)
                for i,line in enumerate(lines):
                    draw.text((W//2,1016-(len(lines)-1)*39+i*39),line,font=font(36),fill='white',anchor='mt',stroke_width=1,stroke_fill='#252d30')
            encoder.stdin.write(image.tobytes());index+=1
        encoder.stdin.close()
        if decoder.wait()!=0 or encoder.wait()!=0:raise RuntimeError('Caption rendering failed')
    finally:decoder.stdout.close()
    assert index==round(record['seconds']*30), f'Unexpected frame count {index}'


def main():
    record=json.loads((ROOT/'evidence/film/timeline.json').read_text())
    seconds=record['seconds']
    assert 90<=seconds<=120
    clips=[]
    for scene in record['scenes']:
        path=OUT/f"voice-{scene['id']:02}.wav"
        run('-i',ROOT/scene['audio'],'-af',f"apad,atrim=duration={scene['duration']}",'-ar','48000','-c:a','pcm_s16le',path)
        clips.append(path)
    concat=OUT/'voice-concat.txt'
    concat.write_text(''.join(f"file '{path}'\n" for path in clips))
    run('-f','concat','-safe','0','-i',concat,'-c:a','pcm_s16le',OUT/'narration.wav')
    # Burn Nova-3 timing with Pillow, so ffmpeg need not have libass installed.
    subtitles=ROOT/'docs/demo/embodiweave-demo-v2.srt'
    burn_captions(record, subtitles)
    music=ROOT.parent/'cipher.mp3'
    if not music.exists():raise RuntimeError('Download the licensed Cipher source from docs/demo/CREDITS.md')
    mix=(f"[0:a]atrim=duration={seconds},asetpts=PTS-STARTPTS,loudnorm=I=-16:TP=-1.5:LRA=11,volume=0.1258925,"
         f"afade=t=in:st=0:d=1,afade=t=out:st={seconds-3}:d=3[m];"
         "[1:a]loudnorm=I=-16:TP=-1.5:LRA=11[v];[m][v]amix=inputs=2:normalize=0,alimiter=limit=0.89[a]")
    run('-i',music,'-i',OUT/'narration.wav','-filter_complex',mix,'-map','[a]','-t',seconds,'-ar','48000',OUT/'mix.wav')
    final=OUT/'embodiweave-demo-v2.mp4'
    run('-i',OUT/'captioned-v2.mp4','-i',OUT/'mix.wav','-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','128k',
        '-t',seconds,'-movflags','+faststart',final)
    backup=OUT/'embodiweave-demo-v2-narration-free.mp4'
    run('-i',OUT/'captioned-v2.mp4','-i',music,'-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','128k',
        '-af',f'loudnorm=I=-20:TP=-1.5:LRA=11,afade=t=out:st={seconds-3}:d=3','-t',seconds,'-movflags','+faststart',backup)
    site=OUT/'embodiweave-demo-v2-720p.mp4'
    run('-i',final,'-vf','scale=1280:720','-c:v','libx264','-preset','fast','-crf','23','-maxrate','1500k','-bufsize','3000k',
        '-c:a','aac','-b:a','96k','-movflags','+faststart',site)
    transfer=next(s for s in record['scenes'] if s['visual']=='transfer')
    gif=OUT/'embodiweave-demo-v2.gif'
    run('-ss',transfer['start'],'-t','10','-i',final,'-filter_complex',
        '[0:v]fps=10,scale=640:-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3',gif)
    assert final.stat().st_size<50_000_000
    assets=[final,backup,site,gif,subtitles]
    data={'seconds':seconds,'fps':30,'width':1920,'height':1080,'narration_model':record['model'],
          'narration_seconds':sum(s['voice_seconds'] for s in record['scenes']),
          'music':{'title':'Cipher','artist':'Kevin MacLeod','licence':'CC BY 3.0','source':'https://incompetech.com/music/royalty-free/mp3-royaltyfree/Cipher2.mp3',
                   'source_sha256':sha(music),'edits':'Excerpt, fades, loudness normalization, music 18 dB below normalized narration'},
          'assets':{p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in assets},
          'robot_motion':'Recorded MuJoCo joint positions from real frozen PPO checkpoints. No pose interpolation, keyframing or generated robot footage.',
          'graphics':'Editorial titles, graph layout/highlights from real database records, measured learning curves, camera moves, sensor rays and path trails.',
          'heldout':'Previously recorded result; not rerun and not ingested into planning graph.'}
    (ROOT/'evidence/film/film-receipt.json').write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(data,indent=2))


if __name__=='__main__':main()
