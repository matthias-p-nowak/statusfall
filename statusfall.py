import asyncio,yaml,os,time,signal
from PIL import Image, ImageDraw, ImageShow
import pysnmp,pysnmp.hlapi,pysnmp.hlapi.asyncio

running=True
snmpEngine = pysnmp.hlapi.SnmpEngine()

def sigHandler(signum, frame):
  global running
  print('sigHandler',signum,'stopping loop')
  running=False

class SnmpHost:
  picLeft=0
  picWidth=0
  watch={}

  def __init__(self,addr,hostCfg):
    self.watch=hostCfg.setdefault('watch',{})
    self.picWidth=len(self.watch)
    community=hostCfg.setdefault('community','public')
    self.comdat=pysnmp.hlapi.CommunityData(community, mpModel=1)
    port=hostCfg.setdefault('port',161)
    self.transport=pysnmp.hlapi.asyncio.UdpTransportTarget((addr,port),timeout=1,retries=1)

class DynConfig:
  config={}
  cfgTime=0
  upperIteration=0
  middleIteration=0
  
  def sanityCheck(self):
    if 'hosts' not in self.config:
      self.config['hosts']={}
  
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
          self.sanityCheck()
          return True
    return False
    
  def __init__(self,fileName):
    print('init dyn config')
    self.fileName=fileName
    self.check()
  
  def get(self,*va,default):
    # print('va=',va,'default=',default)
    cfg=self.config
    for i in range(len(va)-1):
      if not isinstance(cfg,dict):
        return default
      if va[i] not in cfg:
        return default
      cfg=cfg[va[i]]
    return cfg.setdefault(va[len(va)-1],default)
      

class SnmpMain:
  hosts={}
  picture=None
  
  def newPic(self):
    oldPic=self.picture
    width=1
    hosts=self.dc.get('hosts',default={})
    for h in hosts:
      w=hosts[h].setdefault('watch',{})
      width+=len(w)
      width+=1
    height=4
    for part in ['upper','middle','lower']:
      height+= self.dc.get(part,default=256)
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
    hosts=self.dc.get('hosts',default={})
    oldHosts=self.hosts
    newHosts={}
    sw=1
    for hostKey in hosts:
      hostCfg=hosts[hostKey]
      host=SnmpHost(hostKey,hostCfg)
      newHosts[hostKey]=host
      host.picLeft=sw
      sw+=host.picWidth+1
      
    self.hosts=newHosts
  
  async def main(self):
    # TODO: make config file an optional argument
    self.dc=DynConfig('statusfall.yaml')
    self.newPic()
    self.updateHosts()
    t=self.dc.get('interval',default=8)
    await asyncio.sleep(t - (time.time() % t))
    # ## ###
    while running:
      print('ok',time.time())
      if  self.dc.check():
        print('new config')
        self.newPic()
            
      t=self.dc.get('interval',default=8)
      await asyncio.sleep(t - (time.time() % t ))
   

if __name__ == '__main__':
  print('main started')
  signal.signal(signal.SIGINT,sigHandler)  
  m=SnmpMain()
  asyncio.run(m.main())
  print('all done')

