# Smoke + calculator tests. Usage: python3 tools/serve.py site 8811 &  then  python3 tests/test.py   (needs: pip install playwright)
import re, json
from playwright.sync_api import sync_playwright
B="http://127.0.0.1:8811"
urls=[u.replace("https://stoplineinvestor.org","") for u in re.findall(r"<loc>(.*?)</loc>",open('site/sitemap.xml').read())]+['/embed/position-size/','/nope-404/']
res={"pages":[], "cases":[]}
def stats(pg):
    pg.wait_for_function("document.querySelectorAll('#gres .stat').length>0")
    return {x.query_selector('span').inner_text():x.query_selector('b').inner_text() for x in pg.query_selector_all('#gres .stat')}
with sync_playwright() as p:
    import os
    br=p.chromium.launch(executable_path='/usr/bin/google-chrome' if os.path.exists('/usr/bin/google-chrome') else None,args=['--no-sandbox'])
    ctx=br.new_context()
    for u in urls:
        pg=ctx.new_page(); errs=[]
        pg.on("console", lambda m, errs=errs: errs.append(('console',m.text,m.location.get('url',''))) if m.type=='error' else None)
        pg.on("pageerror", lambda e, errs=errs: errs.append(('pageerror',str(e),'')))
        r=pg.goto(B+u, wait_until="load")
        pg.wait_for_timeout(400)
        own=[x for x in errs if '127.0.0.1' in x[2] or x[0]=='pageerror']
        third=[x for x in errs if x not in own]
        res["pages"].append({"url":u,"status":r.status,"title":pg.title(),"own_errors":own,"third_party_errors":len(third)})
        pg.close()
    pg=ctx.new_page(); perr=[]; pg.on("pageerror", lambda e: perr.append(str(e)))
    def case(name, url, expect):
        pg.goto(B+url); s=stats(pg)
        ok=all(s.get(k)==v for k,v in expect.items())
        res["cases"].append({"name":name,"url":url,"got":s,"pass":ok})
    case("Apex PA exactly 50% (strict)","/prop-consistency/?p=apex-pa&t=3000&b=1500",{"Best day as % of profit":"50%","Status":"Exactly at the limit: not enough","Total profit needed":"More than $3,000"})
    case("Topstep Combine $1,800 best day","/prop-consistency/?p=topstep-combine&t=3000&b=1800",{"Best day as % of profit":"60%","Status":"Over the limit","Total profit needed":"$3,272.73","Extra profit to fix it":"$272.73"})
    case("Tradeify Select exactly 40% (inclusive)","/prop-consistency/?p=tradeify-select&t=5000&b=2000",{"Status":"Within the limit","Total profit needed":"$5,000","Extra profit to fix it":"$0"})
    case("TPT example from help center","/prop-consistency/?p=tpt-test&t=3100&b=2000",{"Best day as % of profit":"64.52%","Status":"Over the limit","Total profit needed":"More than $4,000","Extra profit to fix it":"More than $900"})
    case("Tradeify Lightning 1st payout example","/prop-consistency/?p=tradeify-lightning-1&t=2570.14&b=643.34",{"Total profit needed":"$3,216.70","Extra profit to fix it":"$646.56"})
    case("Legacy link without preset still works","/prop-consistency/?t=2400&b=1500&r=50",{"Status":"Over the limit","Total profit needed":"$3,000"})
    # dropdown interaction
    pg.goto(B+"/prop-consistency/"); pg.select_option('#preset','lucid-flex'); pg.wait_for_timeout(100)
    res["cases"].append({"name":"Dropdown: Lucid Flex fills 40% + inclusive + source line","got":{"r":pg.input_value('#r'),"e":pg.input_value('#e'),"psrc":pg.inner_text('#psrc')},
      "pass": pg.input_value('#r')=='40' and pg.input_value('#e')=='Passes' and 'Rules verified Nov 13, 2026 from support.lucidtrading.com' in pg.inner_text('#psrc')})
    pg.select_option('#preset',''); res["cases"].append({"name":"Dropdown: back to Custom resets hint","got":pg.inner_text('#psrc')[:60],"pass":pg.inner_text('#psrc').startswith('Pick your firm')})
    case("Apex Intraday PA 50K, before lock","/prop-drawdown/?p=apex-ipa-50k&h=51200&c=50800",{"Liquidation level":"$49,200","Room left":"$1,600","Status":"Active"})
    case("Apex Intraday PA 50K, locked","/prop-drawdown/?p=apex-ipa-50k&h=52500&c=51000",{"Liquidation level":"$50,100","Room left":"$900"})
    case("Topstep Combine 50K, locked at start","/prop-drawdown/?p=topstep-combine-50k&h=52500&c=51000",{"Liquidation level":"$50,000","Room left":"$1,000"})
    case("MFF Rapid eval 50K keeps trailing","/prop-drawdown/?p=mff-rapid-eval-50k&h=52500&c=51000",{"Liquidation level":"$50,500","Room left":"$500"})
    pg.goto(B+"/prop-drawdown/"); pg.select_option('#preset','tpt-test-100k'); s=stats(pg)
    res["cases"].append({"name":"Dropdown: TPT 100K resets balances to $100,000","got":s,"pass":s.get("Liquidation level")=="$97,000" and s.get("Room left")=="$3,000"})
    pg.goto(B+"/prop-target/"); pg.select_option('#preset','tradeify-select-150k'); s=stats(pg)
    res["cases"].append({"name":"Dropdown: Tradeify Select 150K target","got":{"t":pg.input_value('#t'),**s},"pass":pg.input_value('#t')=='9000'})
    # Sign-in chip must not collide with the account-size input (id=acct).
    pg.goto(B+"/position-size/")
    pg.wait_for_selector("#account-btn", timeout=8000)
    pg.wait_for_function("document.querySelector('#size')&&document.querySelector('#size').innerText!=='-'")
    collision=pg.evaluate("()=>{const el=document.getElementById('acct');return el?{tag:el.tagName,type:el.type,id:el.id}:null}")
    pg.fill("#acct","")
    pg.fill("#acct","20000")
    pg.wait_for_function("document.querySelector('#size')&&document.querySelector('#size').innerText.replace(/,/g,'')==='100'")
    size=pg.inner_text("#size"); grade=pg.inner_text("#grade")
    res["cases"].append({"name":"Position size still computes after Sign in chip loads","got":{"collision":collision,"size":size,"grade":grade},"pass":collision and collision["tag"]=="INPUT" and size.replace(",","")=="100" and grade=="S"})
    res["calc_pageerrors"]=perr
    br.close()
json.dump(res,open('tests/results.json','w'),indent=1)
bad=[x for x in res["pages"] if x["own_errors"] or x["status"] not in (200,404)]
print("pages:",len(res["pages"]),"ok:",len(res["pages"])-len(bad)); print("bad:",bad)
print("3rd-party console errors total:",sum(x["third_party_errors"] for x in res["pages"]))
for c in res["cases"]: print("PASS" if c["pass"] else "FAIL", c["name"], "" if c["pass"] else c["got"])
print("pageerrors:",perr)
