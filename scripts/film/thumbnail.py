"""One real MuJoCo frame with editorial typography, no generated robot imagery."""
import json
from PIL import Image, ImageDraw
from scripts.film.physics import Replay, ROOT
from scripts.film.render import font, PAPER, INK, ORANGE

pair=json.loads((ROOT/'evidence/film/filmed-pair.json').read_text())
family='static_crossing' if 'static_crossing' in pair['suite'] else 'crossing'
replay=Replay(pair['deployed'],family)
pixels,_=replay.frame(pair['deployed']['seconds']-.35,'chase')
replay.close()
image=Image.fromarray(pixels)
draw=ImageDraw.Draw(image)
draw.rectangle((0,0,1920,284),fill=PAPER)
draw.rectangle((72,47,86,67),fill=ORANGE)
draw.text((108,36),'EMBODIWEAVE / BUILT ON FALKORDB',font=font(32,True),fill=INK)
draw.text((72,99),'A graph chooses.',font=font(83),fill=INK)
draw.text((900,99),'Physics checks.',font=font(83),fill=ORANGE)
draw.text((76,219),'Real checkpoints. Real collisions. Decisions you can audit.',font=font(33),fill=INK)
draw.rectangle((0,960,1920,1080),fill=INK)
draw.text((72,992),'MUJOCO SIM-TO-SIM TRANSFER  /  UNCHANGED 2D-TRAINED WEIGHTS',font=font(29,True),fill=PAPER)
image.save(ROOT/'docs/demo/thumbnail.png')
image.save(ROOT/'web/media/demo-v2-poster.webp',quality=88,method=6)
