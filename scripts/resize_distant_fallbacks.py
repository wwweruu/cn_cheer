from pathlib import Path
import json,struct,io,hashlib
from PIL import Image
root=Path('assets/generated/meshy')
for folder in root.iterdir():
 if folder.name=='scene':continue
 base=folder/'runtime'/('distant-v2' if folder.name=='general_red' else 'distant-v1')
 p=base/'model.glb'
 if not p.exists():continue
 target=folder/'runtime/distant-webp-1k/model.glb'
 if target.exists():continue
 raw=p.read_bytes();ln=struct.unpack_from('<I',raw,12)[0];d=json.loads(raw[20:20+ln]);b=raw[28+ln:];changes={}
 for im in d['images']:
  v=d['bufferViews'][im['bufferView']];pix=Image.open(io.BytesIO(b[v.get('byteOffset',0):v.get('byteOffset',0)+v['byteLength']])).convert('RGB');pix.thumbnail((1024,1024),Image.Resampling.LANCZOS);s=io.BytesIO();pix.save(s,format='WEBP',quality=95,method=6);changes[im['bufferView']]=s.getvalue()
 chunks=[];offset=0
 for i,v in enumerate(d['bufferViews']):
  old=v.get('byteOffset',0);data=changes.get(i,b[old:old+v['byteLength']]);v.update(byteOffset=offset,byteLength=len(data));data+=b'\0'*((-len(data))%4);chunks.append(data);offset+=len(data)
 d['buffers']=[{'byteLength':offset}];j=json.dumps(d,separators=(',',':')).encode();j+=b' '*((-len(j))%4)
 target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(struct.pack('<4sII',b'glTF',2,28+len(j)+offset)+struct.pack('<I4s',len(j),b'JSON')+j+struct.pack('<I4s',offset,b'BIN\0')+b''.join(chunks))
 target.with_suffix('.json').write_text(json.dumps({'source_sha256':hashlib.sha256(raw).hexdigest(),'output_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'image_size':1024,'geometry_unchanged':True},indent=2))
 print('FAR_WEBP_1K',folder.name,target.stat().st_size,flush=True)
