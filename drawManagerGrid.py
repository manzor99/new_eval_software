import sys
import numpy
import os 
from PIL import Image, ImageDraw, ImageFont


def drawThickRectangle(image, box, color,thickness):
  x1, y1, x2, y2=box
  image.rectangle([x1,y1,x1+thickness,y2], color)
  image.rectangle([x1,y1,x2,y1+thickness], color)
  image.rectangle([x2-thickness,y1,x2,y2], color)
  image.rectangle([x1,y2-thickness,x2,y2], color)

def adjustValue(value):
  #return value
  return 5.0-(value -1)


def getColorFromValue( value ):
  
  value=adjustValue(value)
  
  r=g=b=0
  
  adj=int(255*(value-1)/4.0)
  percentage= (value-1)/4.0
  
  five_r=87
  five_g=187
  five_b=138
  
  three_r=255
  three_g=214
  three_b=102
  
  one_r=230
  one_g=124
  one_b=115
  
  
  if value > 3:
    r=three_r -  int( percentage* (three_r-five_r))
    g=three_g -  int( percentage* (three_g-five_g))
    b=three_b +  int( percentage* (five_b-three_b))
  elif value < 3:
    r=one_r +  int( percentage* (three_r-one_r))
    g=one_g +  int( percentage* (three_g-one_g))
    b=one_b -  int( percentage* (one_b-three_b))
  else:
    r=three_r
    g=three_g
    b=three_b
  #print "rgb("+`r`+","+`g`+","+`b`+")"
  return "rgb("+`r`+","+`g`+","+`b`+")"

  
def drawBoxedItem(man, image, values, location, size, nameBlock):
  
  #thickness of perimeter
  thick=0.1
  
  dx= (size*(1.0-thick*2))/3
  dy= (size*(1.0-thick*2))/3
  x, y = location

  sum=0
  
  #print values
  
  for v in values:
    sum+=v
  avg= round( sum/len(values), 1)
  
  #avg= round(adjustValue(avg), 1)
  
  a, b, c, d, e, f, g, h, i = values
  
  color=getColorFromValue(avg)
  
  drawThickRectangle(image, [x, y, x+size, y+size], color, size/10)
  
  image.rectangle([x+(1+thick*0.5)*size,y+size/3   ,x+(1+nameBlock-thick*0.5)*size,y+size*2/3], color )
  
  x+=size*thick
  y+=size*thick
  
  tx=size*thick

  #http://stackoverflow.com/questions/1919044/is-there-a-better-way-to-iterate-over-two-lists-getting-one-element-from-each-l
  #for i in [0,1,2]:
  #  for j in [
  
  #for r, c in range
  
  #first row
  image.rectangle([x,y,x+dx,y+dy], getColorFromValue( a ) )
  image.text([tx+x,tx+y], `round(a,1)`)
  image.rectangle([x+dx,y,x+2*dx,y+dy], getColorFromValue(b) )
  image.text([tx+x+dx,tx+y], `round(b,1)`)
  image.rectangle([x+2*dx,y,x+3*dx,y+dy], getColorFromValue(c) )
  image.text([tx+x+2*dx,tx+y], `round(c,1)`)
  
  #second row
  image.rectangle([x,y+dy,x+dx,y+2*dy], getColorFromValue(d) )
  image.text([tx+x,tx+y+dx], `round(d,1)` )
  image.rectangle([x+dx,y+dy,x+2*dx,y+2*dy], getColorFromValue(e) )
  image.text([tx+x+dx,tx+y+dx], `round(e,1)`)
  image.rectangle([x+2*dx,y+dy,x+3*dx,y+2*dy], getColorFromValue(f) )
  image.text([tx+x+2*dx,tx+y+dx], `round(f,1)`)
  
  #third row
  image.rectangle([x,y+2*dy,x+dx,y+3*dy], getColorFromValue(g) )
  image.text([tx+x,tx+y+2*dx], `round(g,1)`)
  image.rectangle([x+dx,y+2*dy,x+2*dx,y+3*dy], getColorFromValue(h) )
  image.text([tx+x+dx,tx+y+2*dx], `round(h,1)`)
  image.rectangle([x+2*dx,y+2*dy,x+3*dx,y+3*dy], getColorFromValue(i) )
  image.text([tx+x+2*dx,tx+y+2*dx], `round(i,1)`)
  
#  fontsize = 2
#  font = ImageFont.load("arial.pil")  #, fontsize)
  
  image.text([x+size,y+ size/2-size*thick-tx*0.5 ], man)
  
  #RAWLINS REQUEST
  image.text([x+size,y+ size/2-size*thick+tx*0.5 ], `avg`)


def generateCollageImage( manager, filename):

  boxSize = 200
  padding=10
  nameBlock=0.5
  rows=2
  columns=3
  
  maxHeight=int(rows*(boxSize+padding))
  maxWidth=int( (columns*(1+nameBlock))*(boxSize+padding) )
  
  

  im = Image.new('RGBA', (maxWidth, maxHeight), (0, 0, 0, 0)) 
  draw = ImageDraw.Draw(im) 
  
  x=0
  y=0
  for man, box in manager.iteritems():
    
    if (y+boxSize+padding > maxHeight):
      y=0
      x+=(1+nameBlock)*boxSize+padding
    
    if (x+(1+nameBlock)*boxSize+padding > maxWidth):
      print "Ran out of room!"
    #  exit()
    
    drawBoxedItem(man, draw, box, [x,y], boxSize, nameBlock  )
    
    y+=boxSize+padding
    
  #im.show()
  #need to purge these on occassion
  #os.remove("./static/manager_images/*")
  im.save("./static/manager_images/"+filename+".png")


def generateIndividualImages( manager, fileprefix, namesLookup ):
  
  boxSize = 100
  nameBlock=0.5
  padding=10
  
  maxHeight=boxSize
  maxWidth=int( (1+nameBlock)*boxSize )
  
  
  x=0
  y=0
  
  reverseDictionary = {}
  for username, name in namesLookup.iteritems():
    reverseDictionary[name]=username
  
  for man, box in manager.iteritems():
    im = Image.new('RGBA', (maxWidth, maxHeight), (0, 0, 0, 0)) 
    draw = ImageDraw.Draw(im) 
    drawBoxedItem(man, draw, box, [x,y], boxSize, nameBlock  )
    im.save("./static/manager_images/"+fileprefix+reverseDictionary[man]+".png")
    
def demo():

  manager={}
  manager["AMAZING"]=  [5.0, 4.9, 4.8, 4.7, 4.6, 4.5, 4.4, 4.3, 4.2]
  manager["PROBLEM"]=  [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8]
  manager["CRAZY"]=    [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
  manager["MIDDLE"]=   [2.2, 2.4, 2.6, 2.8, 3.0, 3.2, 3.4, 3.6, 3.8]
  manager["MMIDDLE"]=  [2.6, 2.7, 2.8, 2.9, 3.0, 3.1, 3.2, 3.3, 3.4]

  #generateIndividualImages( manager )
  #generateCollageImage(manager)



#init()