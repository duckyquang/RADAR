import time, json, re, statistics, concurrent.futures
from pathlib import Path
from collections import Counter
from typing import Optional

from pipeline.config import COUNTRY_VALID_CODES as COUNTRY_CODES
from . import fetcher, demographics

CONTINENTS = {
    "USA":"North America","CAN":"North America","GBR":"United Kingdom",
    "DEU":"Germany","FRA":"France","ITA":"Italy","ESP":"Spain",
    "NLD":"Netherlands","SWE":"Sweden","NOR":"Norway","FIN":"Finland",
    "CHN":"China","JPN":"Japan","AUS":"Australia","BRA":"Brazil",
    "IND":"India","ZAF":"South Africa","RUS":"Russia","KOR":"South Korea",
    "MEX":"Mexico","TWN":"Taiwan","CHE":"Switzerland","DNK":"Denmark",
    "PRT":"Portugal","AUT":"Austria","BEL":"Belgium","IRL":"Ireland",
    "NZL":"New Zealand","ISR":"Israel","POL":"Poland","GRC":"Greece",
    "TUR":"Turkey","HKG":"Hong Kong","SGP":"Singapore","ARG":"Argentina",
    "CHL":"Chile","COL":"Colombia","EGY":"Egypt","NGA":"Nigeria","KEN":"Kenya",
    "THA":"Thailand","ARE":"UAE","SAU":"Saudi Arabia","CZE":"Czech Republic",
    "ROU":"Romania","HUN":"Hungary","UKR":"Ukraine",
}
COUNTRY_NAMES = {k:k if len(v)<=12 else v for k,v in CONTINENTS.items()}
COUNTRY_NAMES["USA"]="United States"

MAX_STUDIES=100; MAX_WORKERS=5; MAX_WORKERS_PMC=3

DESIGN_KEYWORDS = [
    ("randomized","RCT / Clinical Trial"),("rct","RCT / Clinical Trial"),
    ("trial","RCT / Clinical Trial"),("clinical trial","RCT / Clinical Trial"),
    ("cross-sectional","Cross-sectional"),("cross sectional","Cross-sectional"),
    ("cohort","Cohort"),("prospective","Cohort"),("longitudinal","Cohort"),
    ("retrospective","Cohort"),("observational","Observational"),
    ("meta-analysis","Review / Meta-analysis"),("meta analysis","Review / Meta-analysis"),
    ("systematic review","Review / Meta-analysis"),("review","Review / Meta-analysis"),
    ("survey","Survey"),("case-control","Case-Control"),
    ("case control","Case-Control"),
]


def get_crossref_refs(doi):
    import requests
    try:
        r=requests.get(f"https://api.crossref.org/works/{doi}",headers={"User-Agent":"RADAR/1.0"},timeout=15)
        if r.status_code!=200: return []
        msg=r.json().get("message",{})
        refs=msg.get("reference",[])
        return [ref.get("DOI") for ref in refs if ref.get("DOI")]
    except: return []


DATA_SOURCE_PRIORITY = {
    "pmc_fulltext_xml": 5,
    "unpaywall_pdf": 4,
    "pmc_table": 3,
    "pubmed_abstract": 2,
    "openalex_meta": 1,
    "crossref_only": 0,
}

DATA_SOURCE_LABELS = {
    "pmc_fulltext_xml": "PMC Full-text",
    "unpaywall_pdf": "Unpaywall OA",
    "pmc_table": "PMC Table",
    "pubmed_abstract": "PubMed Abstract",
    "openalex_meta": "OpenAlex",
    "crossref_only": "CrossRef",
}


def _best_data_source(sources):
    if not sources:
        return "crossref_only"
    return max(sources, key=lambda x: DATA_SOURCE_PRIORITY.get(x, 0))


def enrich_single(ref_doi):
    s={"doi":ref_doi, "data_sources": [], "_quality": 0, "pmid": None}
    sources = []

    # Parallelize independent source fetches (CrossRef + OpenAlex + Unpaywall)
    meta = None; oa = None; up_text = None
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        f_cr = ex.submit(fetcher.get_crossref_meta, ref_doi)
        f_oa = ex.submit(fetcher.search_openalex, ref_doi)
        f_up = ex.submit(fetcher.get_fulltext_via_unpaywall, ref_doi)
        try: meta = f_cr.result()
        except: pass
        try: oa = f_oa.result()
        except: pass
        try: up_text = f_up.result()
        except: pass

    if meta:
        s.update(title=meta.get("title",""),author_str=meta.get("author_str",""),
                 year=meta.get("year"),journal=meta.get("journal",""),type=meta.get("type",""))
        sources.append("crossref_only")

    if oa:
        sources.append("openalex_meta")
        if not s.get("title") and oa.get("title"):
            s["title"] = oa["title"]
        if not s.get("author_str") and oa.get("author_str"):
            s["author_str"] = oa["author_str"]
        if oa.get("author_countries"):
            s["author_countries"] = oa["author_countries"]
        if oa.get("institutions"):
            s["institutions"] = oa["institutions"]

    if up_text:
        sources.append("unpaywall_pdf")
        pi = demographics.parse_pmc_fulltext(up_text)
        if pi:
            demo_keys = {k:v for k,v in pi.items() if k not in ("title","journal","year","authors","affiliations","abstract")}
            for k, v in demo_keys.items():
                if k not in s or not s.get(k):
                    s[k] = v
            if pi.get("affiliations"):
                aff = demographics.infer_country_from_affiliations(pi["affiliations"])
                if aff and not s.get("country"):
                    s["country"] = aff

    # Short-circuit: if we already have sample_size + sex + any race + country from above, skip PubMed/PMC
    has_all_from_first_pass = (
        s.get("sample_size")
        and s.get("male_pct") and s.get("female_pct")
        and any(s.get(k) for k in ["white_pct","black_pct","hispanic_pct","asian_pct","other_pct"])
        and s.get("country") and s["country"] not in ("Unknown","")
    )
    if not has_all_from_first_pass:
        try:
            pmid=fetcher.search_pubmed_by_doi(ref_doi)
            if pmid:
                s["pmid"] = pmid
                pmcid=fetcher.pmid_to_pmcid(pmid)
                fulltext=None
                if pmcid:
                    fulltext=fetcher.fetch_pmc_fulltext(pmcid)
                if fulltext:
                    sources.append("pmc_fulltext_xml" if "<body>" in fulltext else "pmc_table")
                    pi=demographics.parse_pmc_fulltext(fulltext)
                    s.update({k:v for k,v in pi.items() if k not in ("title","journal","year","authors","affiliations","abstract")})
                    if "sample_size" not in s:
                        xml=fetcher.fetch_pubmed_xml(pmid)
                        if xml:
                            pi2=demographics.parse_pubmed_xml(xml)
                            abstract=pi2.get("abstract","")
                            if abstract:
                                demo=demographics.extract_demographics_from_text(abstract)
                                s.update(demo)
                                if not s.get("title") and pi2.get("title"): s["title"]=pi2["title"]
                                sources.append("pubmed_abstract")
                    if pi.get("affiliations"):
                        aff=demographics.infer_country_from_affiliations(pi["affiliations"])
                        if aff: s["country"]=aff
                    if pi.get("title") and len(pi["title"])>len(s.get("title","")): s["title"]=pi["title"]
                    if not s.get("year") and pi.get("year"): s["year"]=pi["year"]
                else:
                    xml=fetcher.fetch_pubmed_xml(pmid)
                    if xml:
                        sources.append("pubmed_abstract")
                        pi2=demographics.parse_pubmed_xml(xml)
                        abstract=pi2.get("abstract","")
                        if abstract:
                            demo=demographics.extract_demographics_from_text(abstract)
                            s.update(demo)
                        if not s.get("country"):
                            aff=demographics.infer_country_from_affiliations(pi2.get("affiliations",[]))
                            if aff: s["country"]=aff
                        if pi2.get("title") and len(pi2["title"])>len(s.get("title","")): s["title"]=pi2["title"]
                        if not s.get("year") and pi2.get("year"): s["year"]=pi2["year"]
        except Exception as e:
            s["_error"] = str(e)

    s["data_sources"] = sources
    best = _best_data_source(sources)
    s["best_source"] = best
    s["best_source_label"] = DATA_SOURCE_LABELS.get(best, "Unknown")

    # Quality score: 0-100 based on data depth
    has_sample = 1 if s.get("sample_size") else 0
    has_sex = 1 if s.get("male_pct") and s.get("female_pct") else 0
    has_race = 1 if any(s.get(k) for k in ["white_pct","black_pct","hispanic_pct","asian_pct","other_pct"]) else 0
    has_country = 1 if s.get("country") and s["country"] not in ("Unknown","") else 0
    source_score = DATA_SOURCE_PRIORITY.get(best, 0) / 5 * 30
    data_score = (has_sample + has_sex*2 + has_race*3 + has_country) / 7 * 70
    s["_quality"] = round(source_score + data_score, 1)

    return s


def parse_continent(c):
    if not c or c in ("Unknown","Multicentre","Systematic review"): return "Other / Unknown"
    for code,cont in CONTINENTS.items():
        if code.upper()==c.strip().upper() or code.lower() in c.lower(): return cont
    return "Other / Unknown"


def check_study(s):
    sample=(s.get("sample_size") or 0)>0
    country=s.get("country") and s["country"] not in ("Unknown","Multicentre")
    has_sex=s.get("male_pct") is not None and s.get("female_pct") is not None and (s["male_pct"]>0 or s["female_pct"]>0)
    race_cats=sum(1 for k in ["white_pct","black_pct","hispanic_pct","asian_pct","other_pct"] if s.get(k) is not None and s[k]>0)
    has_any_race=race_cats>0
    return sample and country, has_sex, has_any_race, race_cats


def infer_design(typ,title):
    t=f"{typ} {title}".lower()
    for kw,d in DESIGN_KEYWORDS:
        if kw in t: return d
    return "Other"


def calc_bias_score(entries):
    if not entries: return 0
    n=len(entries)
    age_gap=sum(1 for e in entries if not e.get("age") or e["age"]=="NR" or e["age"]=="")
    sex_gap=sum(1 for e in entries if not (e.get("male_pct") and e.get("female_pct")))
    race_gap=sum(1 for e in entries if not e.get("has_any_race"))
    country_gap=sum(1 for e in entries if e.get("country") in ("Unknown",""))
    geo_bias=abs(sum(1 for e in entries if "USA" in e.get("country","").upper())-n/2)*100/n
    gaps=[(age_gap,0.25),(sex_gap,0.25),(race_gap,0.30),(country_gap,0.15),(min(geo_bias,100),0.05)]
    return round(sum(g[0]/n*100*g[1] for g in gaps),1)


def gen_report(data,bias_score):
    j=data.get("journal",{})
    s=data.get("summary",{})
    c=data.get("completeness",{})
    e=data.get("eligible_completeness",{})
    lines=[]
    lines.append(f"CLINICAL BIAS ASSESSMENT REPORT")
    lines.append(f"{'='*60}")
    lines.append(f"Guideline: {j.get('title','')}")
    lines.append(f"Year: {j.get('year')} | Society: {j.get('society','N/A')}")
    lines.append(f"")
    lines.append(f"BIAS SCORE: {bias_score}%")
    verdict="USABLE" if bias_score<30 else "QUESTIONABLE" if bias_score<60 else "NOT USABLE"
    lines.append(f"VERDICT: {verdict}")
    lines.append(f"")
    lines.append(f"KEY FINDINGS:")
    lines.append(f"- Studies analyzed: {s.get('eligible',0)} of {s.get('total_with_data',0)} eligible")
    age_pct=round(100-e.get('age',{}).get('pct',0),1)
    if age_pct>30: lines.append(f"⚠ Age data MISSING in {age_pct}% of studies")
    sex_pct=100-e.get('sex_both',{}).get('pct',0) if e.get('sex_both') else 100
    if sex_pct>30: lines.append(f"⚠ Sex data INCOMPLETE in {round(sex_pct,1)}% of studies")
    race_pct=100-e.get('any_race',{}).get('pct',0) if e.get('any_race') else 100
    if race_pct>40: lines.append(f"⚠ Race data MISSING in {round(race_pct,1)}% of studies")
    geo=data.get('geography',{})
    usa_pct=geo.get('usa_pct',0)
    if usa_pct>70: lines.append(f"⚠ Geographic bias: {usa_pct}% USA-only studies")
    lines.append(f"")
    lines.append(f"USABILITY ASSESSMENT:")
    lines.append(f"This guideline's cited studies have {'ADEQUATE' if verdict=='USABLE' else 'INSUFFICIENT' if verdict=='QUESTIONABLE' else 'INADEQUATE'} demographic reporting.")
    lines.append(f"Recommend: {'Proceed with analysis' if verdict=='USABLE' else 'Exercise caution' if verdict=='QUESTIONABLE' else 'Do not use for diversity metrics'}")
    return "\n".join(lines)


def run(guideline_doi):
    try:
        meta=fetcher.get_crossref_meta(guideline_doi)
        if not meta: return {"error":f"Could not resolve DOI: {guideline_doi}"}
        ji={"doi":f"https://doi.org/{guideline_doi}","disease":meta.get("title","Unknown") or "Unknown",
            "society":"","year":meta.get("year"),"title":meta.get("title","") or "Untitled",
            "id":guideline_doi.replace("/","_").replace(".","_")}

        refs=get_crossref_refs(guideline_doi)
        total=len(refs)
        if refs and len(refs)>MAX_STUDIES: refs=refs[:MAX_STUDIES]

        raw_studies=[]
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            fs={ex.submit(enrich_single,r):r for r in refs}
            for f in concurrent.futures.as_completed(fs):
                try: raw_studies.append(f.result())
                except: pass

        entries=[]
        for s in raw_studies:
            mp=s.get("male_pct"); fp=s.get("female_pct")
            rc=sum(1 for k in ["white_pct","black_pct","hispanic_pct","asian_pct","other_pct"] if s.get(k) is not None and s[k]>0)
            author_countries = s.get("author_countries", [])
            author_geo_diversity = len(author_countries) if author_countries else 0
            entries.append({
                "title":s.get("title","Untitled"),"link":f"https://doi.org/{s.get('doi','')}" if s.get("doi") else "",
                "author":s.get("author_str",""),"country":s.get("country","Unknown"),
                "year":s.get("year"),"journal":s.get("journal",""),"sample_size":s.get("sample_size"),
                "age":"","male_pct":mp,"female_pct":fp,
                "white_pct":s.get("white_pct"),"black_pct":s.get("black_pct"),
                "hispanic_pct":s.get("hispanic_pct"),"asian_pct":s.get("asian_pct"),
                "other_pct":s.get("other_pct"),"design":infer_design(s.get("type",""),s.get("title","")),
                "race_cats":rc,
                "has_sex":1 if mp is not None and fp is not None and (mp>0 or fp>0) else 0,
                "has_age":0,"has_any_race":1 if rc>0 else 0,"has_all_5_race":1 if rc==5 else 0,
                "quality_score": s.get("_quality", 0),
                "best_source": s.get("best_source_label", "CrossRef"),
                "author_countries": author_countries,
                "author_geo_diversity": author_geo_diversity,
                "pmid": s.get("pmid"),
            })

        n_all=len(entries)

        eligible=[e for e in entries if (e.get("sample_size") or 0)>0]
        for e in eligible: e["eligibility_tier"] = 1
        if not eligible:
            eligible=[e for e in entries if e["has_sex"] or e["has_any_race"]]
            for e in eligible: e["eligibility_tier"] = 2
        if not eligible:
            eligible=[e for e in entries if e.get("country") and e["country"]!="Unknown"]
            for e in eligible: e["eligibility_tier"] = 3
        if not eligible:
            eligible=entries[:10] if entries else []
            for e in eligible: e["eligibility_tier"] = 4

        n_eligible=len(eligible)
        samples=[e["sample_size"] for e in eligible if (e.get("sample_size") or 0)>0]
        yrs=set(e["year"] for e in eligible if e.get("year"))
        sm=statistics.mean(samples) if samples else 0
        smed=statistics.median(samples) if samples else 0

        comp=lambda n,t:{"n":n,"total":t,"pct":round(n/t*100,1) if t else 0}
        c=comp(sum(1 for e in entries if e.get("country")!="Unknown"),n_all)
        cy=comp(sum(1 for e in entries if e.get("year")),n_all)
        cs=comp(sum(1 for e in entries if (e.get("sample_size") or 0)>0),n_all)
        csb=comp(sum(1 for e in entries if e["has_sex"]),n_all)
        car=comp(sum(1 for e in entries if e["has_any_race"]),n_all)
        ca5=comp(sum(1 for e in entries if e["has_all_5_race"]),n_all)

        ec_age=comp(sum(1 for e in eligible if e.get("age") and e["age"] not in ("NR","")),n_eligible)
        ec_sb=comp(sum(1 for e in eligible if e["has_sex"]),n_eligible)
        ec_ar=comp(sum(1 for e in eligible if e["has_any_race"]),n_eligible)
        ec_a5=comp(sum(1 for e in eligible if e["has_all_5_race"]),n_eligible)

        smv=[e["male_pct"] for e in eligible if e.get("male_pct") is not None]
        sfv=[e["female_pct"] for e in eligible if e.get("female_pct") is not None]

        race_mean={}
        for rk,rl in [("white","white_pct"),("black","black_pct"),("hispanic","hispanic_pct"),
                       ("asian","asian_pct"),("other","other_pct")]:
            vals=[e[rl] for e in eligible if e.get(rl) is not None and e[rl]>0]
            race_mean[rk]={
                "mean":round(statistics.mean(vals),1) if vals else 0,
                "sd":round(statistics.stdev(vals),1) if len(vals)>1 else 0,
                "reported":len(vals),"total":n_eligible,
                "pct":round(len(vals)/n_eligible*100,1) if n_eligible else 0,
            }

        usac=sum(1 for e in eligible if "USA" in (e.get("country","").upper()) or "UNITED STATES" in e.get("country","").upper())
        nonus=sum(1 for e in eligible if e.get("country","") not in ("USA","UNITED STATES","","Unknown") and "USA" not in e.get("country","").upper())
        multic=n_eligible-usac-nonus if n_eligible>=usac+nonus else 0

        geo={"usa":usac,"usa_pct":round(usac/n_eligible*100,1) if n_eligible else 0,
             "multi_incl_usa":0,"multi_incl_usa_pct":0,
             "multi":multic,"multi_pct":round(multic/n_eligible*100,1) if n_eligible else 0,
             "non_usa":nonus,"non_usa_pct":round(nonus/n_eligible*100,1) if n_eligible else 0}

        designs=Counter(e.get("design","Other") for e in entries)
        conts=Counter(parse_continent(e.get("country","")) for e in eligible)
        ctrs=Counter(e.get("country","Unknown") for e in eligible if e.get("country") not in ("Unknown","Multicentre"))
        sb=Counter()
        for e in eligible:
            if e["has_sex"] and (e["male_pct"] or 0)>0 and (e["female_pct"] or 0)>0: sb["Both sexes reported"]+=1
            elif e["male_pct"] and e["male_pct"]>0: sb["Male only"]+=1
            elif e["female_pct"] and e["female_pct"]>0: sb["Female only"]+=1
            else: sb["Neither reported"]+=1

        rcd=Counter(e["race_cats"] for e in entries)
        jc=Counter(e.get("journal","Unknown") for e in eligible if e.get("journal"))
        dec=Counter()
        for e in eligible:
            y=e.get("year")
            if y: dec[f"{(y//10)*10}s"]+=1

        author_countries_all = []
        for e in eligible:
            ac = e.get("author_countries") or []
            if isinstance(ac, list):
                author_countries_all.extend(ac)
        author_geo_set = set(author_countries_all)
        quality_scores = [e.get("quality_score", 0) for e in eligible if e.get("quality_score", 0) > 0]

        res={
            "journal":ji,
            "author_geography": {
                "unique_countries": sorted(author_geo_set) if author_geo_set else [],
                "country_count": len(author_geo_set),
                "avg_author_diversity": round(statistics.mean([e.get("author_geo_diversity", 0) for e in eligible]), 1) if eligible else 0,
                "max_author_diversity": max([e.get("author_geo_diversity", 0) for e in eligible]) if eligible else 0,
            },
            "data_quality": {
                "avg_quality_score": round(statistics.mean(quality_scores), 1) if quality_scores else 0,
                "quality_distribution": {
                    "high": sum(1 for q in quality_scores if q >= 70),
                    "medium": sum(1 for q in quality_scores if 40 <= q < 70),
                    "low": sum(1 for q in quality_scores if q < 40),
                },
                "source_breakdown": dict(Counter(e.get("best_source", "Unknown") for e in entries)),
            },
            "summary":{"total_screened":total,"total_with_data":n_all,"eligible":n_eligible,
                       "total_participants":sum((e.get("sample_size") or 0) for e in eligible),
                       "sample_size_mean":round(sm,1),"sample_size_median":round(smed,1),
                       "sample_size_min":min(samples) if samples else 0,"sample_size_max":max(samples) if samples else 0,
                       "sample_size_sd":round(statistics.stdev(samples),1) if len(samples)>1 else 0,
                       "year_min":min(yrs) if yrs else None,"year_max":max(yrs) if yrs else None},
            "completeness":{"country":c,"year":cy,"sample_size":cs,"sex_both":csb,"any_race":car,"all_5_race":ca5,"age":{"n":0,"total":n_all,"pct":0}},
            "eligible_completeness":{"age":ec_age,"sex_both":ec_sb,"any_race":ec_ar,"all_5_race":ec_a5,"all_5_sum_100":ec_a5},
            "sex_distribution":{"mean_male":round(statistics.mean(smv),1) if smv else 0,
                                "mean_female":round(statistics.mean(sfv),1) if sfv else 0,
                                "sd_male":round(statistics.stdev(smv),1) if len(smv)>1 else 0,
                                "sd_female":round(statistics.stdev(sfv),1) if len(sfv)>1 else 0},
            "race_distribution":race_mean,"geography":geo,"years":sorted(yrs),"year_counts":{},
            "study_design":dict(sorted(designs.items(),key=lambda x:-x[1])),
            "continent_breakdown":{k:{"count":v,"pct":round(v/n_eligible*100,1) if n_eligible else 0}
                                  for k,v in sorted(conts.items(),key=lambda x:-x[1])},
            "top_countries":[{"country":COUNTRY_NAMES.get(k,k),"code":k,"count":v,
                             "pct":round(v/n_eligible*100,1) if n_eligible else 0}
                            for k,v in sorted(ctrs.items(),key=lambda x:-x[1])[:15]],
            "sex_breakdown":{k:{"count":v,"pct":round(v/n_eligible*100,1) if n_eligible else 0}
                           for k,v in sorted(sb.items(),key=lambda x:-x[1])},
            "race_cats_distribution":{str(k):{"count":v,"pct":round(v/n_all*100,1) if n_all else 0}
                                    for k,v in sorted(rcd.items())},
            "decade_breakdown":{k:{"count":v,"pct":round(v/n_eligible*100,1) if n_eligible else 0}
                              for k,v in sorted(dec.items())},
            "top_journals":[{"journal":k,"count":v,"pct":round(v/n_eligible*100,1) if n_eligible else 0}
                           for k,v in sorted(jc.items(),key=lambda x:-x[1])[:10]],
            "criteria_pass_rates":{
                "sample_size_gt_0":{"n":sum(1 for e in entries if (e.get("sample_size") or 0)>0),"total":n_all},
                "country_valid":{"n":sum(1 for e in entries if e.get("country") not in ("Unknown","","Multicentre")),"total":n_all},
                "sex_sum_100":{"n":sum(1 for e in entries if e["has_sex"]),"total":n_all},
                "all_5_race":{"n":sum(1 for e in entries if e["has_all_5_race"]),"total":n_all},
                "both_sex_and_race":{"n":sum(1 for e in entries if e["has_sex"] and e["has_any_race"]),"total":n_all},
            },
            "eligible_studies":eligible,
            "live_pipeline":True,
        }

        if samples:
            sq=sorted(samples)
            res["sample_size_quartiles"]={
                "q1":sq[len(sq)//4],"q2":round(statistics.median(sq)),"q3":sq[3*len(sq)//4],"min":sq[0],"max":sq[-1],
            }

        if yrs:
            bins={}
            for e in eligible:
                y=e.get("year")
                if y:
                    bk="2015+" if y>=2015 else f"{(y//5)*5}-{(y//5)*5+4}"
                    bins.setdefault(bk,[]).append(e)
            res["reporting_trends"]={}
            for lb,gr in sorted(bins.items()):
                n=len(gr)
                res["reporting_trends"][lb]={"n":n,
                    "sex_reported":round(sum(1 for s in gr if s["has_sex"])/n*100,1),
                    "any_race":round(sum(1 for s in gr if s["has_any_race"])/n*100,1),
                    "all_5_race":round(sum(1 for s in gr if s["has_all_5_race"])/n*100,1),
                }

        bias_score=calc_bias_score(eligible)
        report_text=gen_report(res,bias_score)
        res["bias_score"]=bias_score
        res["report"]=report_text

        return res
    except Exception as e:
        import traceback
        return {"error":str(e)+"\n"+traceback.format_exc()}
