import json,struct,numpy as np
def load(p):
    d=open(p,'rb').read();jl=struct.unpack('<I',d[12:16])[0]
    J=json.loads(d[20:20+jl]);B=bytearray(d[20+jl+8:]);return J,B
def rd(J,B,ai):
    a=J['accessors'][ai];v=J['bufferViews'][a['bufferView']]
    n={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}[a['type']]
    dt={5126:np.float32,5125:np.uint32,5123:np.uint16,5121:np.uint8}[a['componentType']];it=np.dtype(dt).itemsize
    st=v.get('byteStride',it*n)
    raw=np.frombuffer(bytes(B),np.uint8,st*(a['count']-1)+it*n,v.get('byteOffset',0)+a.get('byteOffset',0))
    return np.ascontiguousarray(np.lib.stride_tricks.as_strided(raw,(a['count'],it*n),(st,1))).view(dt).reshape(-1,n)
def add(J,B,arr,typ,ctype=5126,target=None):
    arr=np.ascontiguousarray(arr);
    while len(B)%4:B.append(0)
    bv={'buffer':0,'byteOffset':len(B),'byteLength':arr.nbytes}
    if target:bv['target']=target
    J['bufferViews'].append(bv);B.extend(arr.tobytes())
    acc={'bufferView':len(J['bufferViews'])-1,'componentType':ctype,'count':len(arr),'type':typ}
    if typ=='VEC3':acc['min']=arr.min(0).tolist();acc['max']=arr.max(0).tolist()
    J['accessors'].append(acc);return len(J['accessors'])-1
def save(J,B,p):
    while len(B)%4:B.append(0)
    J['buffers']=[{'byteLength':len(B)}]
    js=json.dumps(J,ensure_ascii=False,separators=(',',':')).encode();js+=b' '*(-len(js)%4)
    with open(p,'wb') as f:
        f.write(struct.pack('<III',0x46546C67,2,28+len(js)+len(B)));f.write(struct.pack('<II',len(js),0x4E4F534A));f.write(js)
        f.write(struct.pack('<II',len(B),0x004E4942));f.write(B)
