import cmudict, panphon, panphon.distance, csv, importlib.resources as ir
import sys; sys.path.insert(0,'.')
ARPA2IPA = {'AA':'ɑ','AE':'æ','AH':'ʌ','AO':'ɔ','AW':'aʊ','AY':'aɪ','EH':'ɛ','ER':'ɝ','EY':'eɪ','IH':'ɪ','IY':'i','OW':'oʊ','OY':'ɔɪ','UH':'ʊ','UW':'u','B':'b','CH':'tʃ','D':'d','DH':'ð','F':'f','G':'ɡ','HH':'h','JH':'dʒ','K':'k','L':'l','M':'m','N':'n','NG':'ŋ','P':'p','R':'ɹ','S':'s','SH':'ʃ','T':'t','TH':'θ','V':'v','W':'w','Y':'j','Z':'z','ZH':'ʒ'}
CMU=cmudict.dict()
def ipa(w): return ''.join('ə' if p=='AH0' else ARPA2IPA[p.rstrip('012')] for p in CMU[w][0])
ft=panphon.FeatureTable(); D=panphon.distance.Distance()
# name-aligned weights (feature_weights.csv header order differs from ipa_all.csv order)
with ir.files('panphon').joinpath('data/feature_weights.csv').open() as f:
    r=list(csv.reader(f)); WD=dict(zip(r[0],map(float,r[1])))
NAMES=ft.names; W=[WD.get(n,0.0) for n in NAMES]; SW=sum(W)
print('names',NAMES); print('aligned W',W,'sum',SW,' library zip pairs:',list(zip(NAMES,D.fm.weights))[18:])
def pd(v1,v2): return sum(abs(a-b)*w for w,a,b in zip(W,v1,v2))/(2*SW)
def wlev(s,t,indel=0.5):
    a,b=ft.word_to_vector_list(s,numeric=True),ft.word_to_vector_list(t,numeric=True);n,m=len(a),len(b)
    d=[[0.0]*(m+1) for _ in range(n+1)]
    for i in range(1,n+1): d[i][0]=i*indel
    for j in range(1,m+1): d[0][j]=j*indel
    for i in range(1,n+1):
        for j in range(1,m+1):
            d[i][j]=min(d[i-1][j]+indel,d[i][j-1]+indel,d[i-1][j-1]+pd(a[i-1],b[j-1]))
    return d[n][m],n,m
P=[('cat','cad'),('cat','cash'),('drum','drama'),('knight','night'),('bat','pat'),('pat','pit')]
for x,y in P:
    s,t=ipa(x),ipa(y); d,n,m=wlev(s,t)
    wf=D.weighted_feature_edit_distance(s,t); swf=SW_lib=sum(D.fm.weights)
    print(f"{x}/{y}: wlev_d={d:.4f} sim_maxlen={1-d/max(n,m):.4f} sim_n+m={1-2*d/(n+m):.4f} | lib wfed={wf} sim=1-d/((n+m)*{swf})={1-wf/((n+m)*swf):.4f}")
for p,q in [('t','d'),('t','ʃ'),('b','p'),('æ','ɪ'),('ʌ','ɑ'),('m','ə')]:
    print(p,q,round(pd(ft.word_to_vector_list(p,numeric=True)[0],ft.word_to_vector_list(q,numeric=True)[0]),4))
