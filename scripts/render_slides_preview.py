"""Raster preview using the actual slide shapes, text, geometry and Windows fonts."""
from pathlib import Path
from pptx import Presentation
from PIL import Image,ImageDraw,ImageFont
from pptx.enum.shapes import MSO_SHAPE

root=Path(__file__).resolve().parents[1]
prs=Presentation(root/'presentation/Cadence_Case_Study_Solution.pptx')
out=root/'tmp/slides-preview';out.mkdir(parents=True,exist_ok=True)
scale=1280/prs.slide_width
for index,slide in enumerate(prs.slides,1):
 im=Image.new('RGB',(1280,720),'white');draw=ImageDraw.Draw(im)
 for shape in slide.shapes:
  x,y,w,h=[round(v*scale) for v in (shape.left,shape.top,shape.width,shape.height)]
  assert x>=0 and y>=0 and x+w<=1282 and y+h<=722,'Off-slide content'
  if shape.shape_type==1:
   try:color=tuple(shape.fill.fore_color.rgb)
   except (AttributeError,TypeError):color=(255,255,255)
   draw.rounded_rectangle((x,y,x+w,y+h),radius=14,fill=color)
  if shape.has_text_frame:
   yy=y+round(shape.text_frame.margin_top*scale)
   for para in shape.text_frame.paragraphs:
    size=round((para.font.size.pt if para.font.size else 22)*1280/(prs.slide_width/914400)/72)
    font=ImageFont.truetype('C:/Windows/Fonts/calibrib.ttf' if para.font.bold else 'C:/Windows/Fonts/calibri.ttf',size)
    try:color=tuple(para.font.color.rgb)
    except (AttributeError,TypeError):color=(20,40,60)
    xx=x+round(shape.text_frame.margin_left*scale); available=w-round((shape.text_frame.margin_left+shape.text_frame.margin_right)*scale)
    words=para.text.split();lines=[];line=''
    for word in words:
     candidate=(line+' '+word).strip()
     if line and draw.textlength(candidate,font=font)>available:lines.append(line);line=word
     else:line=candidate
    lines.append(line)
    for line in lines:
     draw.text((xx,yy),line,font=font,fill=color);yy+=round(size*1.2)
    assert yy<=y+h+20,'Text overflows its box'
 im.save(out/f'slide-{index:02}.png')
print('Rendered and bounded',len(prs.slides),'slide previews.')
