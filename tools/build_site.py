#!/usr/bin/env python3
"""Construit index.html (site GitHub Pages) à partir de src/.
Usage : python3 tools/build_site.py
"""
import json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
SUPABASE = {"url": "https://chvagxyhghsvtjdxnfqd.supabase.co", "key": "sb_publishable_qdFNs59mvsLz39dOm1mUAA_b7YBAaAS"}

def r(n): return open(os.path.join(SRC, n), encoding="utf-8").read()

s = r("app.html")
full = s.replace("/*LEAFLET_CSS*/", r("leaflet.css")).replace("/*COMMUNES*/", r("communes.json")).replace("/*ARRS*/", r("arrondissements.json"))
snap = json.dumps({"id": "site", "site": True, "date": "2026-11-19T00:00:00Z", "items": [], "supabase": SUPABASE})
inj = ('<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.119.2/dist/umd/supabase.js"></script>\n'
       '<script>window.__SNAPSHOT__=' + snap + ';</script>\n<script id="app">')
site = full.replace('<script id="app">', inj, 1).replace("<title>Mes logements à Marseille</title>", '<title>Mes logements à Marseille</title>\n<meta name="robots" content="noindex">', 1)
open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8").write(site)
print("index.html :", len(site), "octets")
