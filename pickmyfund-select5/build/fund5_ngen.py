"""PickMyFund Select 5 (gold & silver compete for sector slots) – – selection from an NGEN Markets fund-statistics workbook.
Usage: python3 fund5_ngen.py <ngen_stats.xlsx>   -> prints picks; returns dict via run(path)"""
import openpyxl,pandas as pd,numpy as np,re,sys
AUM_MIN=500
SECT_CAT={'Sectoral: Pharma & Healthcare (Sectoral Fund)':'Healthcare','Sectoral: Banking & Financial Services (Sectoral Fund)':'Banking & Financials',
'Sectoral: IT & Technology (Sectoral Fund)':'IT & Technology','Sectoral: Consumption (Sectoral Fund)':'Consumption','Sectoral: Auto & Transportation (Sectoral Fund)':'Auto & Transport',
'Sectoral: Energy & Resources (Thematic Fund)':'Energy & Resources','Sectoral: Infrastructure (Thematic Fund)':'Infrastructure','Sectoral: Manufacturing (Thematic Fund)':'Manufacturing',
'Sectoral: PSU & MNC (Sectoral Fund)':'PSU'}
KW=[('Defence',r'defen'),('MNC',r'\bmnc\b'),('PSU',r'psu|cpse|public sector|bharat 22'),('Healthcare',r'pharma|health'),('Banking & Financials',r'bank|financ|capital market|insurance'),
('IT & Technology',r'\bit\b|tech|digital'),('Consumption',r'consum|fmcg|rural'),('Auto & Transport',r'auto|\bev\b|mobility|transport|logistic'),
('Energy & Resources',r'energy|oil|gas|commodit|metal|power|resource'),('Infrastructure',r'infra|realty|housing|construction'),('Manufacturing',r'manufactur|industrial|capital goods')]
CORE_CAT={'Large Cap Fund':'Large cap','Equity Index: Large Cap Core (Equity Index Funds)':'Large cap','Flexi Cap Fund':'Diversified','Multi Cap Fund':'Diversified','Focused Fund':'Diversified',
'Value Fund':'Diversified','Contra Fund':'Diversified','Dividend Yield Fund':'Diversified','Large & Mid Cap Fund':'Diversified','Equity Index: Broad Market (Equity Index Funds)':'Diversified',
'Mid Cap Fund':'Mid cap','Equity Index: Mid Cap (Equity Index Funds)':'Mid cap','Small Cap Fund':'Small cap','Equity Index: Small & Micro Cap (Equity Index Funds)':'Small cap'}
def load(path):
    wb=openpyxl.load_workbook(path,read_only=True,data_only=True); rows=[];cat=None;hdr=None
    for r in [x for sh in ('Equity','Other') for x in wb[sh].iter_rows(values_only=True)]:
        r=list(r)
        if isinstance(r[0],str) and all(x is None for x in r[1:6]) and r[0] not in ('NGEN MARKETS','All returns for periods over one year are annualised'): cat=r[0]; continue
        if r[0]=='#': hdr=r; continue
        if isinstance(r[0],(int,float)) and hdr and r[1]: d=dict(zip(hdr,r)); d['Category']=cat; rows.append(d)
    return pd.DataFrame(rows)
def amc(n): return n.split()[0].lower()
def classify(row):
    n=row['Fund Name'].lower().replace('bank of india','boi'); c=row['Category']
    if c in CORE_CAT: return 'Core',CORE_CAT[c]
    if c=='FoFs Domestic':
        if 'mining' in n or ('gold' in n and 'silver' in n): return None,None
        if 'gold' in n: return 'Sector','Gold'
        if 'silver' in n: return 'Sector','Silver'
        return None,None
    if c in SECT_CAT or c=='Equity Index: Sectoral & Thematic (Equity Index Funds)':
        for g,p in KW:
            if re.search(p,n): return 'Sector',g
        return ('Sector',SECT_CAT[c]) if c in SECT_CAT else (None,None)
    return None,None
def run(path,K=2,verbose=True):
    df=load(path)
    cls=df.apply(classify,axis=1,result_type='expand'); df['Role'],df['Group']=cls[0],cls[1]
    df=df[df.Role.notna()].copy()
    for c in ['AUM (Cr)','6 Month','1 Year','Volatility','3 Year','TER']: df[c]=pd.to_numeric(df[c],errors='coerce')
    df['has1y']=(df['1 Year'].fillna(0)!=0)&(df['Volatility'].fillna(0)>0)
    df['Score']=np.where(df.has1y,df['1 Year']/df['Volatility'],np.nan)
    df['AMC']=df['Fund Name'].map(amc)
    # sector strength: equal-weight 6M return of all funds in group with a 6M figure
    s=df[(df.Role=='Sector')&(df['6 Month'].fillna(0)!=0)]
    sect=s.groupby('Group').agg(r6=('6 Month','mean'),r3m=('3 Month','mean'),r1y=('1 Year','mean'),n=('Fund Name','count')).sort_values('r6',ascending=False)
    elig=df[df.has1y&(df['AUM (Cr)']>=AUM_MIN)]
    # top K sectors that have an eligible fund
    chosen=[g for g in sect.index if (elig.Group==g).any()][:K]
    picks=[];amcs=set()
    for g in chosen:
        c=elig[(elig.Role=='Sector')&(elig.Group==g)&~elig.AMC.isin(amcs)].sort_values('Score',ascending=False).head(1)
        if len(c): picks.append(c.iloc[0]); amcs.add(c.iloc[0].AMC)
    segs=set()
    for _,c in elig[elig.Role=='Core'].sort_values('Score',ascending=False).iterrows():
        if len(picks)>=5: break
        if c.Group in segs or c.AMC in amcs: continue
        picks.append(c); segs.add(c.Group); amcs.add(c.AMC)
    P=pd.DataFrame(picks)
    short={}
    for g in chosen+['Large cap','Diversified','Mid cap','Small cap']:
        short[g]=elig[elig.Group==g].sort_values('Score',ascending=False).head(5)
    if verbose:
        print(sect.round(3).to_string()); print(P[['Fund Name','Role','Group','AUM (Cr)','TER','6 Month','1 Year','3 Year','Score']].round(3).to_string())
    return dict(df=df,sect=sect,chosen=chosen,picks=P,short=short)
if __name__=='__main__': run(sys.argv[1])
