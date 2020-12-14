#!python

import asyncio,yaml,os,time,signal,datetime,sys,struct
from PIL import Image, ImageDraw, ImageShow, ImageFont
from pysnmp.hlapi import *
from pysnmp.hlapi.asyncio import *
from pysnmp.proto import *
running=True
snmpEngine = SnmpEngine()
FloatBB=bytearray([159,120,4])

def sigHandler(signum, frame):
  global running
  print('sigHandler',signum,'stopping loop')
  running=False

def getColor(val):
  if val <0:
    val=0
  if val>1:
    val=1
  r=int(255*val)
  g=int(192*(1-val))
  b=int(val*(1-val)*128)
  return (r,g,b)

def getOrDefault(cfg,*va,default):
  # print('va=',va,'default=',default)
  for i in range(len(va)-1):
    if not isinstance(cfg,dict):
      return default
    if va[i] not in cfg:
      return default
    cfg=cfg[va[i]]
  return cfg.setdefault(va[len(va)-1],default)
  

def vb2dict(varBinds):
  rv={}
  for k,v in varBinds:
    v2=''
    if isinstance(v,Counter32):
      v2=int(v)
    elif isinstance(v,Counter64):
      v2=int(v)
    elif isinstance(v,Integer):
      v2=int(v)
    elif isinstance(v,Gauge32):
      v2=int(v)
    elif isinstance(v,TimeTicks):
      v2=int(v)
    elif isinstance(v,OctetString):
      v2=str(v)
    elif isinstance(v,Opaque):
      try:
        bb=v.asOctets()
        if bb[0:3]==FloatBB:
          v2=struct.unpack('>f',bb[3:])
        else:
          print('first 3 bytes' , list(bb[0:3]))
      except ValueError as ve:
        print('opaque not resolved ve:',ve)
      except TypeError as te:
        print('opaque not resolved te:q',te)
    else:
      print('### nope ###')
      print('got',k,type(v),v)
    rv[str(k)]=v2
  return rv

      
# ##### ##### SNMP ##### #####
class SnmpHost:
  picLeft=0
  picWidth=0
  watch=[]

  def __init__(self,addr,hostCfg):
    self.watch=getOrDefault(hostCfg,'watch',default={})
    self.picWidth=len(self.watch)
    community=getOrDefault(hostCfg,'community',default='public')
    self.comdat=CommunityData(community, mpModel=1)
    port=getOrDefault(hostCfg,'port',default=161)
    self.transport=UdpTransportTarget((addr,port),timeout=1,retries=1)
    self.cntx=ContextData()
  
  async def updatePic(self):
    for i in range(len(self.watch)):
      errInd, errStat, errIdx, varBinds = await getCmd(snmpEngine, 
        self.comdat, self.transport, self.cntx, *self.oids)
      if errStat >0:
        break
      rv=vb2dict(varBinds)
        
          
# ##### ##### DynConfig ##### #####
class DynConfig:
  config={}
  cfgTime=0
  
  def check(self):
    # print('checking')
    st=os.stat(self.fileName)
    if st.st_mtime != self.cfgTime:
      print('reading new config')
      self.cfgTime=st.st_mtime
      with open(self.fileName) as inp:
        c=yaml.safe_load(inp.read())
        if isinstance(c,dict):
          print('got new config')
          self.config=c
          self.debug=getOrDefault(c,'debug',default=0)
          self.upperLen=getOrDefault(c,'upper',default=256)
          self.middleLen=getOrDefault(c,'middle',default=256)
          self.lowerLen=getOrDefault(c,'lower',default=256)
          self.interval=getOrDefault(c,'interval',default=5)
          self.div1=getOrDefault(c,'div1',default=4)
          self.div2=getOrDefault(c,'div2',default=4)
          self.picFileName=getOrDefault(c,'picture',default='status.pnp')
          parts=os.path.splitext(self.picFileName)
          self.tmpPicFileName=parts[0]+'-tmp'+parts[1]
          
          return True
    return False
    
  def __init__(self,fileName):
    print('init dyn config')
    self.fileName=fileName
    self.check()

# ##### ##### SnmpMain ##### #####
class SnmpMain:
  picture=None
  hosts={}
  itUpper=0
  itMiddle=0

  
  def __init__(self):
    self.font=ImageFont.truetype('FreeMono.ttf',14)
    
  def newPic(self):
    oldPic=self.picture
    width=1
    hosts=getOrDefault(self.dc.config,'hosts',default={})
    for h in hosts:
      w= getOrDefault(hosts[h],'watch',default={})
      width+=len(w)
      width+=1
    height=4
    for part in ['upper','middle','lower']:
      height+= getOrDefault(self.dc.config,part,default=256)
    if width < 128:
      width=128
    if height < 128:
      height=128
    size=(0,0)
    if oldPic is not None:
      size=oldPic.size
    if size != (width,height):
      print('size changed')
      im=Image.new('RGB',(width,height))
      self.picture=im
      self.draw=ImageDraw.Draw(im)
      # TODO: copy the older parts or not

  def updateHosts(self):
    hosts=getOrDefault(self.dc.config,'hosts',default={})
    oldHosts=self.hosts
    newHosts={}
    sw=1
    for hostKey in hosts:
      print('configuring host',hostKey)
      hostCfg=hosts[hostKey]
      host=SnmpHost(hostKey,hostCfg)
      newHosts[hostKey]=host
      host.picLeft=sw
      sw+=host.picWidth+1
      host.draw=self.draw
      watching=getOrDefault(hostCfg,'watch',default=[])
      host.watching=watching
      host.oids=[]
      for i in range(len(watching)):
        print('adding watch',i)
        oid=getOrDefault(watching[i],'oid',default=None)
        if oid is None:
          print('no oid specified for host=%s item=%d' % (hostKey,i),file=sys.stderr)
          sys.exit(2)
        host.oids.append(ObjectType(ObjectIdentity(oid)))
        if 'error' in watching[i]:
          host.oids.append(ObjectType(ObjectIdentity(watching[i]['error'])))
        if 'msg' in watching[i]:
          host.oids.append(ObjectType(ObjectIdentity(watching[i]['msg'])))
    self.hosts=newHosts
    
  def rollPic(self):
    savePic=self.picture.copy()
    draw=ImageDraw.Draw(savePic)
    br=savePic.size
    now=datetime.datetime.now()
    t=now.strftime("%a %H:%M:%S")
    sz=self.font.getsize(t)
    br = (br[0]-sz[0]-4, br[1]-sz[1]-4)
    draw.text(br,t, fill=(255,255,50), font=self.font)
    savePic.save(self.dc.tmpPicFileName)
    os.replace(self.dc.tmpPicFileName, self.dc.picFileName)
    sz=self.picture.size
    w=sz[0]-1
    self.itUpper+=1
    if self.itUpper > self.dc.div1:
      self.itUpper=0
      self.itMiddle+=1
      if self.itMiddle > self.dc.div2:
        self.itMiddle=0
        #scroll lower
        # print('scrolling lower')
        t=3+self.dc.upperLen+self.dc.middleLen
        im2c=self.picture.crop((1,t,w,t+self.dc.lowerLen-1))
        self.picture.paste(im2c,(1,t+1))
        im2c=self.picture.crop((1,t-2,w,t-1))
        self.picture.paste(im2c,(1,t))
      # scroll middle
      # print('scrolling middle')
      t=2+self.dc.upperLen
      im2c=self.picture.crop((1,t,w,t+self.dc.middleLen-1))
      self.picture.paste(im2c,(1,t+1))
      im2c=self.picture.crop((1,t-2,w,t-1))
      self.picture.paste(im2c,(1,t))
    # scroll upper
    # print('scrolling upper')
    t=1
    im2c=self.picture.crop((1,t,w,t+self.dc.upperLen-1))
    self.picture.paste(im2c,(1,t+1))

  
  async def main(self):
    # TODO: make config file an optional argument
    self.dc=DynConfig('statusfall.yaml')
    self.newPic()
    self.updateHosts()
    t=self.dc.interval
    await asyncio.sleep(t - (time.time() % t))
    # ## ###
    while running:
      # print('ok',time.time())
      # check config
      if  self.dc.check():
        print('new config')
        self.newPic()
        self.updateHosts()
      # do work
      self.rollPic()
      for h in self.hosts:
        asyncio.create_task(self.hosts[h].updatePic())
      # wait for next
      t=self.dc.interval
      await asyncio.sleep(t - (time.time() % t ))
   

if __name__ == '__main__':
  print('main started')
  signal.signal(signal.SIGINT,sigHandler)  
  m=SnmpMain()
  asyncio.run(m.main())
  print('all done')

