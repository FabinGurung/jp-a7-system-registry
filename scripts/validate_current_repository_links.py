#!/usr/bin/env python3
"""A7 canonical repository links. Offline source gate and bounded public HTTP smoke."""
from __future__ import annotations
import argparse
import concurrent.futures
import json
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
CURRENT=ROOT/"registry/providers/canonical-owner-repository-links-20261117.json"
REPOS=ROOT/"registry/entities/repositories.json"
MODULES=ROOT/"registry/entities/modules.json"
OLD=ROOT/"registry/providers/galactic-atlas-arc02-observation-20261020.json"
SITE=ROOT/"site/index.html"

def load(path):
    return json.loads(path.read_text(encoding="utf-8"))

def offline():
    current=load(CURRENT)
    repos=load(REPOS)["repositories"]
    modules=load(MODULES)["modules"]
    historical=load(OLD)["records"]
    assert current["observed_date"]=="2026-11-17" and current["count"]==len(repos)==10
    byid={x["repository_id"]:x for x in current["links"]}
    assert len(byid)==10 and len({x["provider_object_id"] for x in current["links"]})==10
    assert {x["repository_id"] for x in repos}==set(byid)
    assert len(historical)==9 and "REPO-000010" not in {x["id"] for x in historical}
    assert all(x["has_pages"] and x["archived"] is False for x in current["links"])
    for record in repos:
        id_=record["repository_id"]
        link=byid[id_]
        assert str(link["provider_object_id"])==str(record["provider_object_id"]),(id_,"provider ID")
        assert record["repository_full_name"]==link["repository_full_name"],(id_,"slug")
        assert record["current_slug"]==link["current_slug"],(id_,"current_slug")
        assert record["public_site_url"]==link["homepage"]=="https://fabingurung.github.io/"+link["current_slug"]+"/",(id_,"Pages")
        assert link["github_url"]=="https://github.com/"+link["repository_full_name"]
        assert record["link_observed_date"]==current["observed_date"]
    for module in modules:
        link=byid[module["repository_id"]]
        assert str(module["provider_repository_id"])==str(link["provider_object_id"]),(module["module_id"],"provider")
        assert module["repository_full_name"]==link["repository_full_name"],(module["module_id"],"repository")
        assert module["public_site_url"]==link["homepage"],(module["module_id"],"Pages")
    html=SITE.read_text(encoding="utf-8")
    assert "https://github.com/FabinGurung/jp-a7-system-registry" in html
    assert "github.com/FabinGurung/JP_A7_System_Registry_and_Knowledge_Graph" not in html
    library=current["live_published_evidence"]
    assert library["repository_id"]=="REPO-000010" and library["run_id"]==43987395477
    assert library["deploy"]=="success" and library["browser_qa"]=="success"
    return current

def check_link(link):
    url=link["homepage"]
    result={"id":link["repository_id"],"repo":link["repository_full_name"],"url":url,"status":"INCONCLUSIVE","http_status":None}
    for attempt in range(2):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"A7-Public-Link-Smoke/1.0","Accept":"text/html,*/*"})
            with urllib.request.urlopen(req,timeout=15) as res:
                code=res.status
                final=res.geturl()
                mime=res.headers.get("Content-Type","").lower()
                snippet=res.read(30000).lower()
            result.update(http_status=code,final_url=final,content_type=mime)
            if code==200 and ("html" in mime or b"<html" in snippet or b"<!doctype html" in snippet):
                result["status"]="PASS_HTML"
            else:
                result["status"]="BROKEN_NON_HTML" if code==200 else "BROKEN_HTTP"
            break
        except urllib.error.HTTPError as e:
            result["http_status"]=e.code
            result["status"]="BROKEN_HTTP" if e.code in (404,410) else "INCONCLUSIVE_HTTP"
            result["reason"]="HTTP "+str(e.code)
            if attempt==0 and e.code in (429,500,502,503,504):
                time.sleep(2)
                continue
            break
        except (urllib.error.URLError,TimeoutError,OSError) as e:
            result["status"]="INCONCLUSIVE_NETWORK"
            result["reason"]=type(e).__name__+": "+str(e)[:100]
            if attempt==0:
                time.sleep(2)
                continue
            break
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--online",action="store_true")
    p.add_argument("--output",default="")
    a=p.parse_args()
    try:
        source=offline()
    except (AssertionError,ValueError,KeyError) as exc:
        print("A7 CANONICAL LINK SOURCE GATE FAIL",exc)
        return 1
    print("A7 CANONICAL LINK SOURCE GATE PASS 10 stable IDs, 10 Pages homepages, 7 module routes")
    if not a.online:
        return 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        report=sorted(pool.map(check_link,source["links"]),key=lambda x:x["id"])
    summary={"observation_id":source["observation_id"],"checks":report,
             "passed":sum(x["status"]=="PASS_HTML" for x in report),
             "broken":sum(x["status"].startswith("BROKEN") for x in report),
             "inconclusive":sum(x["status"].startswith("INCONCLUSIVE") for x in report)}
    for item in report:
        print(item["id"],item["status"],item["http_status"],item["url"])
    if a.output:
        dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    print("A7 PUBLIC URL SMOKE",json.dumps({k:summary[k] for k in ("passed","broken","inconclusive")}))
    return 1 if summary["broken"] else 0

if __name__=="__main__":
    sys.exit(main())
