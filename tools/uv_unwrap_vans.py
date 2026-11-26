import sys,numpy as np
from glbio import *
src,dst=sys.argv[1],sys.argv[2];W,H=30.0,21.4
J,B=load(src)
M={m['name']:m for m in J['meshes']}
OFF={'upper__vamp':(0.02,0.3),'upper__tongue':(0.5,0.05),'upper__quarter_lateral':(0.03,0.02),'upper__quarter_medial':(0.3,0.5)}
def setp(m,P,N,uv):
    if m['name'] in OFF:
        uv=uv-uv.min(0)+np.array(OFF[m['name']]);print(m['name'],'uv max',uv.max(0).round(2))
    p=m['primitives'][0];A=p['attributes']
    A['POSITION']=add(J,B,P.astype(np.float32),'VEC3',target=34962);A['NORMAL']=add(J,B,N.astype(np.float32),'VEC3',target=34962)
    A['TEXCOORD_0']=add(J,B,uv.astype(np.float32),'VEC2',target=34962)
    p['indices']=add(J,B,np.arange(len(P),dtype=np.uint32),'SCALAR',5125,34963)
def tri(m):
    p=m['primitives'][0];A=p['attributes'];I=rd(J,B,p['indices']).ravel().astype(np.int64)
    return rd(J,B,A['POSITION']).astype(float)[I],rd(J,B,A['NORMAL']).astype(float)[I]
# --- dome flatten for vamp + tongue (shared centre so they line up)
PV,_=tri(M['upper__vamp']);ytop=PV[:,1].max()
top=PV[PV[:,1]>ytop-0.8];cx,cz=top[:,0].mean(),top[:,2].mean()
for nm in ['upper__vamp','upper__tongue']:
    P,N=tri(M[nm]);dx,dz=P[:,0]-cx,P[:,2]-cz;d=np.hypot(dx,dz)+1e-9
    yt=P[:,1].max() if nm=='upper__tongue' else ytop
    r=d+np.clip(yt-P[:,1],0,None)*np.clip(1-0.6*np.exp(-d/3),0,1)
    uv=np.c_[cx+dx/d*r, cz+dz/d*r]/np.array([W,H]);setp(M[nm],P,N,uv);print(nm,'dome')
# --- cylindrical for quarters
Q=[tri(M[n]) for n in ['upper__quarter_lateral','upper__quarter_medial']]
allP=np.concatenate([q[0] for q in Q]+[PV]);qx,qz=(allP[:,0].min()+allP[:,0].max())/2,(allP[:,2].min()+allP[:,2].max())/2
for nm,(P,N) in zip(['upper__quarter_lateral','upper__quarter_medial'],Q):
    # quarters: lateral z>0, medial z<0; unwrap angle from heel(+X,theta=0) towards toe on each side (no wrap issue)
    t=np.arctan2(P[:,2]-qz,P[:,0]-qx)          # lateral 0..pi, medial 0..-pi
    rr=np.hypot(P[:,0]-qx,P[:,2]-qz)
    # arc length: integrate median radius by angle bins
    bins=np.linspace(-np.pi,np.pi,721);idx=np.clip(np.digitize(t,bins)-1,0,719)
    R=np.array([np.median(rr[idx==i]) if (idx==i).any() else np.nan for i in range(720)])
    R=np.where(np.isnan(R),np.nanmedian(R),R);mid=360
    cum=np.zeros(721);cum[mid+1:]=np.cumsum(R[mid:]*(2*np.pi/720));cum[:mid]=-np.cumsum(R[:mid][::-1]*(2*np.pi/720))[::-1]
    s=np.interp(t,bins,cum)
    uv=np.c_[-np.abs(s)+ (0 if nm.endswith('lateral') else 7.3), -P[:,1]]/np.array([W,H]);setp(M[nm],P,N,uv);print(nm,'cyl')
# --- planar decals
for nm,(ua,us),(va,vs) in [('upper__vamp_lateral_woven_label',(0,1),(1,-1)),('outsole__foxing_heel_logo',(2,-1),(1,-1))]:
    P,N=tri(M[nm]);u=P[:,ua]*us;v=P[:,va]*vs
    uv=np.c_[(u-u.min())/(u.max()-u.min()),(v-v.min())/(v.max()-v.min())];setp(M[nm],P,N,uv)
    print(nm,'planar size',round(u.max()-u.min(),2),round(v.max()-v.min(),2))
save(J,B,dst)
