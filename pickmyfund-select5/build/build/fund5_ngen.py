"""PickMyFund Select 5 (gold & silver compete for sector slots) – – selection from an NGEN Markets fund-statistics workbook.
Usage: python3 fund5_ngen.py <ngen_stats.xlsx>   -> prints picks; returns dict via run(path)"""
import openpyxl,pandas as pd,numpy as np,re,sys
AUM_MIN=500
OFF_AUM_MIN=500
# Offshore funds known to be CLOSED to fresh subscriptions. Update at every monthly check (AMC websites).
# Sources (2026): Nippon India international funds closed 21-Apr-2026; Axis select overseas schemes closed 6-May-2026;
# ICICI Pru NASDAQ 100 Index suspended. Kotak global schemes capped at Rs 1 lakh per PAN per month (treated as open).
CLOSED=['nippon india taiwan','nippon india japan','nippon india us','axis nasdaq','axis global','axis greater china','icici pru nasdaq']
def is_closed(n): return any(k in n.lower() for k in CLOSED)
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
    for r in [x for sh in ('Equity','Other','Hybrid') for x in wb[sh].iter_rows(values_only=True)]:
        r=list(r)
        if isinstance(r[0],str) and all(x is None for x in r[1:6]) and r[0] not in ('NGEN MARKETS','All returns for periods over one year are annualised'): cat=r[0]; continue
        if r[0]=='#': hdr=r; continue
        if isinstance(r[0],(int,float)) and hdr and r[1]: d=dict(zip(hdr,r)); d['Category']=cat; rows.append(d)
    return pd.DataFrame(rows)
def amc(n): return n.split()[0].lower()
OFF_CATS=('FoFs Overseas','Equity Index: International (Equity Index Funds)','Sectoral: International (Thematic Fund)')
def region(n):
    n=n.lower()
    if re.search(r'gold|silver|mining|reit|real estate|metal|energy|commodit|india|i d & w|bond|debt',n.replace('nippon india','nippon').replace('invesco india','invesco').replace('pgim india','pgim')): return None
    for g,p in [('Taiwan','taiwan'),('Japan','japan'),('China/HK','china|hang seng'),('Korea','korea'),('Brazil','brazil'),('Europe','europe|european'),('ASEAN/Asia','asean|asian|asia'),('Emerging mkts','emerging'),('US tech','nasdaq|fang|technology|innovation|artificial'),('Developed ex-US','ex us|ex-us|developed'),('US broad',r'\bus\b|u\.s|usa|s&p 500|american|total stock'),('Global','global|world|international|quality|brand|consumer|equity income')]:
        if re.search(p,n): return g
    return 'Global'
def classify(row):
    n=row['Fund Name'].lower().replace('bank of india','boi'); c=row['Category']
    if c in OFF_CATS:
        g=region(row['Fund Name']); return ('Offshore',g) if g else (None,None)
    if c=='Arbitrage Fund': return 'Cash','Arbitrage'
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
    # offshore slot: best region by average 6-month return, if it beats arbitrage
    arb6=df[(df.Role=='Cash')&(df['6 Month'].fillna(0)!=0)]['6 Month'].mean()
    o=df[(df.Role=='Offshore')&(df['6 Month'].fillna(0)!=0)]
    regions=o.groupby('Group').agg(r6=('6 Month','mean'),r3m=('3 Month','mean'),r1y=('1 Year','mean'),n=('Fund Name','count')).sort_values('r6',ascending=False)
    oe=df[(df.Role=='Offshore')&df.has1y&(df['AUM (Cr)']>=OFF_AUM_MIN)&~df['Fund Name'].map(is_closed)]
    off_region=next((g for g in regions.index if regions.loc[g,'r6']>arb6 and (oe.Group==g).any()),None)
    offshore=None
    if off_region:
        cand=oe[(oe.Group==off_region)].sort_values('Score',ascending=False)
        if len(cand): offshore=cand.iloc[0]; amcs.add(offshore.AMC)
    if offshore is None:
        a=df[(df.Role=='Cash')&(df['AUM (Cr)']>=AUM_MIN)].sort_values('AUM (Cr)',ascending=False)
        offshore=a.iloc[0] if len(a) else None
    off_alts=oe[oe.Group.isin(list(regions.index[:3]))].sort_values(['Group','Score'],ascending=[True,False]).groupby('Group').head(4)
    segs=set()
    for _,c in elig[elig.Role=='Core'].sort_values('Score',ascending=False).iterrows():
        if len(picks)>=4: break
        if c.Group in segs or c.AMC in amcs: continue
        picks.append(c); segs.add(c.Group); amcs.add(c.AMC)
    if offshore is not None: picks=[offshore]+picks
    P=pd.DataFrame(picks)
    short={}
    for g in chosen+['Large cap','Diversified','Mid cap','Small cap']:
        short[g]=elig[elig.Group==g].sort_values('Score',ascending=False).head(5)
    if verbose:
        print(sect.round(3).to_string()); print(regions.round(3).to_string()); print('arbitrage 6M',round(arb6,3)); print(P[['Fund Name','Role','Group','AUM (Cr)','TER','6 Month','1 Year','3 Year','Score']].round(3).to_string())
    return dict(df=df,sect=sect,chosen=chosen,picks=P,short=short,regions=regions,off_region=off_region,arb6=arb6,off_alts=off_alts)
if __name__=='__main__': run(sys.argv[1])
