"""Calibrate LDR cube continuity and extract alpha from approved isolated sprites."""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.meshy/pydeps'))
from scipy.ndimage import gaussian_filter1d, map_coordinates


def main():
    base=ROOT/'assets/generated/meshy/scene';out=ROOT/'public/assets/environment/atmosphere'
    out.mkdir(parents=True,exist_ok=True)
    ids=['sky_px','sky_nx','sky_py','sky_ny','sky_pz','sky_nz']
    arrays=[];report={'sky_native_face_size':[1024,1024],'sky_delivered_face_size':[1024,1024],
        'resolution_note':'The documented API profile returns native 1K faces. Kept at native size and reviewed at gameplay distance; the initial >=2K aspiration was not met.',
        'sky_type':'LDR background, not HDR lighting','processing':'Horizon/exposure alignment, direction-space cube blending; no source overwrite or enlargement','sources':{},'horizons':{}}
    for name in ids:
        p=base/name/'image/v1/image.png';report['sources'][name]=hashlib.sha256(p.read_bytes()).hexdigest()
        a=np.asarray(Image.open(p).convert('RGB'),dtype=np.float32)/255
        if name not in ('sky_py','sky_ny'):
            mean=gaussian_filter1d(a.mean(axis=(1,2)),3)
            lo,hi=int(len(mean)*.33),int(len(mean)*.75)
            horizon=int(np.argmin(np.diff(mean)[lo:hi])+lo)
            report['horizons'][name]=horizon
            y=np.interp(np.arange(1024),[0,512,1023],[0,horizon,1023])
            x=np.arange(1024);xx,yy=np.meshgrid(x,y)
            a=np.stack([map_coordinates(a[:,:,c],[yy,xx],order=1,mode='nearest')for c in range(3)],axis=-1)
        arrays.append(a)
    sides=[0,1,4,5]
    mean_rows=np.mean([a.mean(axis=1)for i,a in enumerate(arrays)if i in sides],axis=0)
    for i in sides:
        current=gaussian_filter1d(arrays[i].mean(axis=1),20,axis=0)
        target=gaussian_filter1d(mean_rows,20,axis=0)
        arrays[i]=np.clip(arrays[i]+(target-current)[:,None,:],0,1)
    for i,row in ((2,0),(3,-1)):
        arrays[i]=np.clip(arrays[i]+mean_rows[row]-arrays[i].mean(axis=(0,1)),0,1)
    size=1024;u,v=np.meshgrid(np.linspace(-1,1,size),np.linspace(-1,1,size));one=np.ones_like(u)
    directions=[(one,-v,-u),(-one,-v,u),(u,one,v),(u,-one,-v),(u,-v,one),(-u,-v,-one)]
    for face,(x,y,z) in enumerate(directions):
        result=np.zeros((size,size,3),np.float32);total=np.zeros((size,size),np.float32)
        dominant=np.maximum(np.maximum(np.abs(x),np.abs(y)),np.abs(z))
        for index,component,su,sv in ((0,x,-z,-y),(1,-x,z,-y),(2,y,x,z),(3,-y,x,-z),(4,z,x,-y),(5,-z,-x,-y)):
            ratio=np.maximum(component,0)/dominant
            weight=np.maximum((ratio-.5)*2,0)**3
            denom=np.maximum(component,.001)
            xx=(np.clip(su/denom,-1,1)+1)*.5*(size-1);yy=(np.clip(sv/denom,-1,1)+1)*.5*(size-1)
            for c in range(3):result[:,:,c]+=map_coordinates(arrays[index][:,:,c],[yy,xx],order=1,mode='nearest')*weight
            total+=weight
        result=np.clip(result/total[:,:,None]*255,0,255).astype('uint8')
        Image.fromarray(result).save(out/f'{ids[face]}.webp',quality=95,method=6)
    for asset in ('distant_mountains','distant_camp','fx_embers','fx_smoke'):
        p=base/asset/'image/v2/image.png';im=Image.open(p).convert('RGBA');a=np.array(im,dtype=np.float32)/255
        report['sources'][asset]=hashlib.sha256(p.read_bytes()).hexdigest()
        if asset.startswith('fx_'):
            intensity=a[:,:,:3].max(axis=2)
            alpha=np.clip((intensity-.008)/.992,0,1)
            a[:,:,:3]/=np.maximum(intensity[:,:,None],.008)
            a[:,:,3]=alpha
        else:
            # Fade the isolation cutout into fog/ground at its four boundaries.
            h,w=a.shape[:2];alpha=a[:,:,3]
            occupied=np.flatnonzero(alpha.max(axis=1)>.08)
            if len(occupied):
                bottom=occupied[-1];fade=np.clip((bottom-np.arange(h))/max(8,h*.035),0,1)
                alpha*=fade[:,None]
            alpha*=np.minimum(1,np.minimum(np.arange(w),np.arange(w)[::-1])/max(1,w*.045))[None,:]
            a[:,:,3]=alpha
        pixels=np.clip(np.rint(a*255),0,255).astype('uint8');Image.fromarray(pixels).save(out/f'{asset}.webp',quality=96,method=6)
        report[asset]={'native_size':list(im.size),'delivered_size':list(im.size),'alpha_range':[int(pixels[:,:,3].min()),int(pixels[:,:,3].max())]}
    (out/'environment.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print('Calibrated six native 1K cube faces and four RGBA layers',flush=True)


if __name__=='__main__':main()
