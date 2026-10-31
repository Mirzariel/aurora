from PIL import Image
from pathlib import Path
p=Path(__file__).resolve().parents[2]/'renders-v2'
i=Image.open(p/'aurora-old-model-hero-v2.png').convert('RGBA')
print('hero alpha bounds',i.getchannel('A').getbbox())
i=i.crop((0,120,1600,1050)); i.save(p/'aurora-old-model-hero-v3.png'); i.save(p/'aurora-old-model-hero-v3.webp',quality=88,method=6)
for stem in ('top','detail','back'):
 im=Image.open(p/f'aurora-old-model-{stem}-v2.png').convert('RGBA'); im.save(p/f'aurora-old-model-{stem}-v2.webp',quality=88,method=6)
 print(stem,im.size,im.getchannel('A').getbbox())
