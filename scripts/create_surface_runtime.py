"""Pack approved native surface maps into tiny GLB material carriers for shared loading."""
import hashlib
import argparse
import io
import json
from pathlib import Path
import struct
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--assets',default='ground_dirt,ground_stone,weathered_wood,aged_metal,fabric_red,fabric_black');args=parser.parse_args()
    original=(ROOT/'assets/source/environment/material_carrier.glb').read_bytes()
    length=struct.unpack_from('<I',original,12)[0]
    template=json.loads(original[20:20+length]); binary=original[28+length:]
    for asset in args.assets.split(','):
        base=ROOT/'assets/generated/meshy/scene'/asset/'surface/v1/finished'
        output=base/'runtime';output.mkdir(exist_ok=True)
        report={'asset':asset,'native_source':'../surface.json','files':{}}
        for tier,size in (('desktop',4096),('mobile',2048)):
            destination=output/f'{asset}_{tier}.glb'
            assert not destination.exists()
            doc=json.loads(json.dumps(template));chunks=[binary];offset=len(binary)
            doc['images']=[];doc['textures']=[];doc['samplers']=[{'magFilter':9729,'minFilter':9987,'wrapS':10497,'wrapT':10497}]
            image_reports=[]
            for index,channel in enumerate(('base_color','normal','orm')):
                im=Image.open(base/f'{channel}.png').convert('RGB');im.thumbnail((size,size),Image.Resampling.LANCZOS)
                stream=io.BytesIO();im.save(stream,format='WEBP',quality=95,method=6);data=stream.getvalue()
                view=len(doc['bufferViews']);doc['bufferViews'].append({'buffer':0,'byteOffset':offset,'byteLength':len(data)})
                data+=b'\0'*((-len(data))%4);chunks.append(data);offset+=len(data)
                doc['images'].append({'mimeType':'image/webp','bufferView':view})
                doc['textures'].append({'sampler':0,'extensions':{'EXT_texture_webp':{'source':index}}})
                image_reports.append({'channel':channel,'size':list(im.size)})
            doc['materials']=[{'name':asset,'pbrMetallicRoughness':{'baseColorFactor':[1,1,1,1],
                'baseColorTexture':{'index':0},'metallicRoughnessTexture':{'index':2},'metallicFactor':1,'roughnessFactor':1},
                'normalTexture':{'index':1}}]
            for mesh in doc['meshes']:
                for primitive in mesh['primitives']:primitive['material']=0
            doc['extensionsUsed']=['EXT_texture_webp'];doc['extensionsRequired']=['EXT_texture_webp'];doc['buffers']=[{'byteLength':offset}]
            encoded=json.dumps(doc,separators=(',',':')).encode();encoded+=b' '*((-len(encoded))%4)
            raw=struct.pack('<4sII',b'glTF',2,28+len(encoded)+offset)+struct.pack('<I4s',len(encoded),b'JSON')+encoded+struct.pack('<I4s',offset,b'BIN\0')+b''.join(chunks)
            destination.write_bytes(raw)
            report['files'][tier]={'file':destination.name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'images':image_reports}
            print('SURFACE_PACKED',asset,tier,len(raw),flush=True)
        (output/'runtime.json').write_text(json.dumps(report,indent=2),encoding='utf8')


if __name__=='__main__':main()
