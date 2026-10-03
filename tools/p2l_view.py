import json, sys, base64, os
from psd2live_mcp import Mcp
def main():
    args=json.loads(sys.argv[1])
    outdir=sys.argv[2] if len(sys.argv)>2 else '_work/flutter'
    os.makedirs(outdir,exist_ok=True)
    m=Mcp(); m.initialize()
    r=m.call('view',args)
    res=(r or {}).get('result',{})
    sc=res.get('structuredContent')
    print('structured:',json.dumps(sc,ensure_ascii=False)[:600] if sc else None)
    n=0
    for c in res.get('content',[]):
        if c.get('type')=='image':
            data=c.get('data'); 
            p=os.path.join(outdir,'view_%d.png'%n)
            open(p,'wb').write(base64.b64decode(data))
            print('image ->',p, c.get('mimeType'))
            n+=1
        elif c.get('type')=='text':
            print('text:',c.get('text','')[:300])
    if n==0: print('no images; raw keys',list(res.keys()))
main()
