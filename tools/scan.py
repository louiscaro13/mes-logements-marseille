#!/usr/bin/env python3
"""Recherche quotidienne de logements à louer à Marseille.

Sources lues : Bien'ici (API JSON publique du site) et Le Figaro Immobilier
(données de la page de résultats). SeLoger, Leboncoin, PAP et Logic-Immo
bloquent la lecture automatique : ils ne sont pas interrogés.

Critères (voir CRITERES) : T2/T3, 900 € CC max, balcon ou terrasse, parking/box,
arrondissements préférés dans l'ordre 6, 5, 10, 4, 9, 3, 2, 8.
Un logement qui coche tout est « parfait ». Sinon on accepte UN assouplissement :
budget jusqu'à 1 000 €, T1, sans extérieur ou sans parking.

Les annonces déjà présentes sur le site (table Supabase `logements`) sont exclues.

Usage : python3 tools/scan.py [--out DOSSIER] [--sans-supabase]
Sortie : DOSSIER/rapport.md, DOSSIER/resultats.json ; met à jour data/propositions.json
"""
import json, re, sys, time, unicodedata, urllib.parse, urllib.request, argparse, datetime, os

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
SUPABASE = "https://chvagxyhghsvtjdxnfqd.supabase.co"
CRITERES = {
    "pieces": (2, 3),
    "budget": 900,
    "budget_max_assoupli": 1000,
    "arr_pref": [6, 5, 10, 4, 9, 3, 2, 8],
}
ECHECS = []  # sources indisponibles pendant cette analyse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get(url, headers=None, tries=3):
    h = {"User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9"}
    h.update(headers or {})
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=40) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa
            if i == tries - 1:
                print(f"  ! échec {url[:90]} : {e}", file=sys.stderr)
                return None
            time.sleep(3 + 3 * i)


def norm(s):
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


RE_EXT = re.compile(r"\b(balcon|balcons|terrasse|terrasses|loggia|loggias)\b")
RE_PARK = re.compile(r"\b(parking|parkings|garage|box|place de stationnement|stationnement privatif|place privative)\b")
RE_PARK_NEG = re.compile(r"(sans (parking|garage|box)|parking (public|gratuit|a proximite|facile)|stationnement (facile|aise|gratuit|dans la rue)|proche (du |d un )?parking|parking relais)")


def mots(desc):
    d = norm(desc)
    ext = None
    m = RE_EXT.search(d)
    if m:
        ext = "terrasse" if "terrass" in m.group(1) else ("balcon" if "balcon" in m.group(1) else "loggia")
    park = bool(RE_PARK.search(d)) and not RE_PARK_NEG.search(d)
    if park:
        m = RE_PARK.search(d)
        apres = d[m.start():m.end() + 90]
        if re.search(r"(en sus|en supplement|en option|moyennant|possibilite|possible|disponible a la location|pour \d+ ?(eur|e|euros)? ?(par )?mois)", apres):
            park = "option"
    return ext, park


def arr_from_cp(cp):
    m = re.match(r"130(\d\d)$", str(cp or "").strip())
    return int(m.group(1)) if m and 1 <= int(m.group(1)) <= 16 else None


# ---------------------------------------------------------------- Bien'ici
def bienici():
    out = []
    base = {"size": 100, "from": 0, "filterType": "rent", "propertyType": ["flat"], "maxPrice": CRITERES["budget_max_assoupli"],
            "minRooms": 1, "maxRooms": 3, "sortBy": "publicationDate", "sortOrder": "desc", "onTheMarket": [True],
            "zoneIdsByTypes": {"zoneIds": ["-76469"]}}  # Marseille
    total, frm = None, 0
    while total is None or frm < min(total, 1000):
        f = dict(base, **{"from": frm})
        t = get("https://www.bienici.com/realEstateAds.json?filters=" + urllib.parse.quote(json.dumps(f)))
        if not t:
            break
        d = json.loads(t)
        total = d.get("total", 0)
        ads = d.get("realEstateAds", [])
        if not ads:
            break
        out += ads
        frm += 100
        time.sleep(1)
    if not out:
        ECHECS.append("Bien'ici")
    print(f"Bien'ici : {len(out)} annonces (≤ {CRITERES['budget_max_assoupli']} €, 1 à 3 pièces)", file=sys.stderr)
    res = []
    for a in out:
        arr = arr_from_cp(a.get("postalCode"))
        rooms = a.get("roomsQuantity")
        price = a.get("price")
        if not arr or not rooms or not price:
            continue
        res.append({
            "source": "bienici", "id": "bi:" + a["id"], "titre": a.get("title") or "",
            "loyer": price, "pieces": rooms, "surface": a.get("surfaceArea"), "arr": arr,
            "quartier": ((a.get("district") or {}).get("libelle") or ""),
            "agence": a.get("accountDisplayName") or "", "pro": a.get("adCreatedByPro"),
            "meuble": a.get("isFurnished"), "publie": a.get("publicationDate"),
            "url_bienici": "https://www.bienici.com/annonce/" + urllib.parse.quote(a["id"]),
            "description": a.get("description") or "", "_bid": a["id"],
        })
    return res


def bienici_detail(x):
    t = get("https://www.bienici.com/realEstateAd.json?id=" + urllib.parse.quote(x["_bid"]))
    if not t:
        return
    d = json.loads(t)
    x["description"] = d.get("description") or x["description"]
    ext = None
    if (d.get("terracesQuantity") or 0) > 0 or d.get("hasTerrace"):
        ext = "terrasse"
    elif (d.get("balconyQuantity") or 0) > 0 or d.get("hasBalcony") or (d.get("loggiasQuantity") or 0) > 0 or (d.get("balconySurfaceArea") or 0) > 0:
        ext = "balcon"
    park = any((d.get(k) or 0) > 0 for k in ("parkingPlacesQuantity", "enclosedParkingQuantity", "garagesQuantity", "boxesQuantity")) or bool(d.get("hasParking"))
    x["_struct"] = (ext, park)
    c = d.get("contactRelativeData") or {}
    if c.get("agencyNameToDisplay"):
        x["agence"] = c["agencyNameToDisplay"]
    fee = d.get("agencyFeeUrl") or ""
    if fee.startswith("http"):
        u = urllib.parse.urlparse(fee)
        x["url_agence"] = f"{u.scheme}://{u.netloc}/"
    x["reference"] = d.get("reference")
    if d.get("charges") is not None:
        x["charges"] = d.get("charges")


# ---------------------------------------------------------------- Le Figaro
def figaro_page(html):
    m = re.search(r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return []
    arr = json.loads(m.group(1))

    def rv(i, d=0):
        if d > 40:
            return None
        v = arr[i]
        if isinstance(v, list):
            if v and isinstance(v[0], str) and v[0] in ("Reactive", "ShallowReactive", "Ref", "ShallowRef"):
                return rv(v[1], d + 1) if len(v) > 1 else None
            if v and isinstance(v[0], str) and v[0] in ("Set", "Map", "Date", "RegExp", "undefined", "NaN", "EmptyRef", "EmptyShallowRef"):
                return None
            return [rv(x, d + 1) if isinstance(x, int) else x for x in v]
        if isinstance(v, dict):
            return {k: (rv(x, d + 1) if isinstance(x, int) else x) for k, x in v.items()}
        return v
    return [rv(i) for i, v in enumerate(arr) if isinstance(v, dict) and "recordLink" in v and "roomCount" in v]


def figaro():
    res, seen = [], set()
    for page in range(1, 31):
        url = "https://immobilier.lefigaro.fr/annonces/immobilier-location-appartement-marseille+13000.html" + (f"?page={page}" if page > 1 else "")
        t = get(url)
        if not t:
            if page == 1:
                ECHECS.append("Le Figaro")
            break
        objs = figaro_page(t)
        new = [o for o in objs if o.get("id") not in seen]
        if not new:
            break
        for o in new:
            seen.add(o.get("id"))
            if o.get("transaction") != "location" or o.get("type") != "appartement":
                continue
            loc = o.get("location") or {}
            arr = arr_from_cp(loc.get("postalCode"))
            rooms = (o.get("roomCount") or [None])[0]
            price = o.get("price")
            if not arr or not rooms or not price or price > CRITERES["budget_max_assoupli"] or rooms > 3:
                continue
            opts = o.get("options") or []
            ext = "terrasse" if "terrasse" in opts else ("balcon" if "balcon" in opts or "loggia" in opts else None)
            park = any(k in opts for k in ("parking", "garage", "box"))
            cl = o.get("client") or {}
            res.append({
                "source": "figaro", "id": "fi:" + str(o["id"]), "titre": f"{o.get('roomCountLabel','')} {o.get('area','')} m²",
                "loyer": price, "pieces": rooms, "surface": o.get("area"), "arr": arr,
                "quartier": loc.get("district") or "", "agence": cl.get("name") or "",
                "url_agence": cl.get("url") or "", "pro": o.get("origin") == "professionnel",
                "publie": o.get("firstPublicationDate") or o.get("creationDate"),
                "url_figaro": o.get("recordLink"), "description": o.get("descriptionSeo") or o.get("description") or "",
                "reference": o.get("reference"), "_struct": (ext, park),
            })
        time.sleep(1.2)
    print(f"Le Figaro : {len(seen)} annonces lues, {len(res)} dans le budget", file=sys.stderr)
    return res


# ---------------------------------------------------------------- Site (Supabase)
def existants():
    t = get(SUPABASE + "/rest/v1/logements?select=id,data", headers={"apikey": os.environ.get("SUPABASE_KEY", "proxy-injected")})
    if t is None:
        return None
    d = json.loads(t)
    if not isinstance(d, list):
        print("  ! Supabase :", d, file=sys.stderr)
        return None
    return [dict(r.get("data") or {}, id=r["id"]) for r in d]


def deja_sur_site(x, sites):
    urls = {u for u in (x.get("url_bienici"), x.get("url_figaro")) if u}
    ids = set(re.findall(r"\d{6,}", " ".join(urls)))
    for s in sites:
        su = " ".join(str(s.get(k) or "") for k in ("urlSeloger", "urlAgence", "titre"))
        if any(u.split("?")[0] in su for u in urls):
            return s
        if ids & set(re.findall(r"\d{6,}", su)):
            return s
        try:
            same_arr = int(s.get("arr") or 0) == x["arr"]
            same_price = s.get("loyer") and abs(float(s["loyer"]) - x["loyer"]) <= 15
            t = {"T1": 1, "T2": 2, "T3": 3}.get(s.get("type"))
            same_rooms = t is None or t == x["pieces"]
            same_surf = not (s.get("surface") and x.get("surface")) or abs(float(s["surface"]) - float(x["surface"])) <= 2
            if same_arr and same_price and same_rooms and same_surf:
                return s
        except (TypeError, ValueError):
            pass
    return None


# ---------------------------------------------------------------- Fusion, notes
def fusion(items):
    """Regroupe la même annonce publiée sur Bien'ici et Le Figaro."""
    out = []
    for x in items:
        twin = None
        for y in out:
            if y["arr"] == x["arr"] and y["pieces"] == x["pieces"] and abs(y["loyer"] - x["loyer"]) <= 10 and \
               y.get("surface") and x.get("surface") and abs(float(y["surface"]) - float(x["surface"])) <= 1.5:
                twin = y
                break
        if twin:
            for k in ("url_bienici", "url_figaro", "url_agence", "reference"):
                if x.get(k) and not twin.get(k):
                    twin[k] = x[k]
            twin["description"] = max(twin["description"], x["description"], key=len)
            twin["sources"] = sorted(set(twin.get("sources", [twin["source"]]) + [x["source"]]))
            se, sp = twin.get("_struct") or (None, False)
            xe, xp = x.get("_struct") or (None, False)
            twin["_struct"] = (se or xe, sp or xp)
        else:
            x["sources"] = [x["source"]]
            out.append(x)
    return out


def evalue(x):
    se, sp = x.get("_struct") or (None, False)
    de, dp = mots(x.get("description"))
    x["exterieur"] = se or de
    x["parking"] = bool(sp or dp)
    x["parking_option"] = (not sp) and dp == "option"
    plat = ("immo-facile.com", "hektor", "apimo", "ubiflow", "netty", "lefigaro.fr", "bienici.com", "twimmo", "adaptimmo")
    if not x.get("url_agence") or any(p in x["url_agence"] for p in plat):
        x["url_agence"] = "https://www.google.com/search?q=" + urllib.parse.quote(f"{x.get('agence','')} agence immobilière Marseille")
    x["ext_source"] = "annonce" if se else ("description" if de else None)
    x["park_source"] = "annonce" if sp else ("description" if dp else None)
    ass = []
    if x["loyer"] > CRITERES["budget"]:
        ass.append(f"budget {x['loyer']} € (> {CRITERES['budget']} €)")
    if x["pieces"] == 1:
        ass.append("T1")
    if not x["exterieur"]:
        ass.append("sans balcon ni terrasse")
    if not x["parking"]:
        ass.append("sans parking")
    x["assouplissements"] = ass
    pref = CRITERES["arr_pref"]
    x["rang_arr"] = pref.index(x["arr"]) if x["arr"] in pref else len(pref) + (0 if x["arr"] in (1, 7) else 1)
    surf = float(x.get("surface") or 0)
    x["suspect"] = bool(surf and (x["loyer"] / surf < 7 or x["loyer"] / surf > 45)) or (x["pieces"] >= 2 and surf and surf < 22)
    return x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "rapports"))
    ap.add_argument("--sans-supabase", action="store_true")
    ap.add_argument("--site", action="store_true", help="écrit suggestions.json à la racine (lu par le site)")
    a = ap.parse_args()
    today = datetime.date.today().isoformat()

    bi = bienici()
    fi = figaro()
    # pré-filtre avant de lire le détail Bien'ici
    pre = [x for x in bi if x["pieces"] <= 3 and x["loyer"] <= CRITERES["budget_max_assoupli"]]
    print(f"Détail Bien'ici pour {len(pre)} annonces…", file=sys.stderr)
    for i, x in enumerate(pre):
        bienici_detail(x)
        time.sleep(0.4)
    items = fusion(pre + fi)
    items = [evalue(x) for x in items]

    sites = None if a.sans_supabase else existants()
    if sites is None and not a.sans_supabase:
        print("  ! Impossible de lire le site : la vérification des doublons avec « Mes logements » est sautée.", file=sys.stderr)
    for x in items:
        x["deja_sur_site"] = bool(sites and deja_sur_site(x, sites))

    hist_path = os.path.join(ROOT, "data", "propositions.json")
    try:
        hist = json.load(open(hist_path))
    except Exception:
        hist = {}

    cands = [x for x in items if not x["deja_sur_site"] and not x["suspect"] and len(x["assouplissements"]) <= 1 and x["pieces"] >= 1]
    def cle(x):
        return (len(x["assouplissements"]), x["rang_arr"], 0 if x["pieces"] in CRITERES["pieces"] else 1, x["loyer"])
    cands.sort(key=cle)
    top = cands[:10]
    if len(top) < 10:  # compléter avec deux assouplissements si besoin
        extra = sorted([x for x in items if not x["deja_sur_site"] and not x["suspect"] and len(x["assouplissements"]) == 2], key=cle)
        top += extra[:10 - len(top)]

    # le site filtre lui-même les annonces déjà enregistrées : on lui en donne davantage
    pool = cands[:60]
    if len(pool) < 60:
        pool += sorted([x for x in items if not x["deja_sur_site"] and not x["suspect"] and len(x["assouplissements"]) == 2], key=cle)[:60 - len(pool)]
    for x in {id(y): y for y in top + pool}.values():
        k = x.get("url_bienici") or x.get("url_figaro")
        x["deja_propose"] = hist.get(k)
        hist.setdefault(k, today)
    if a.site:
        champs = ("id", "sources", "loyer", "pieces", "surface", "arr", "quartier", "agence", "url_agence", "reference",
                  "url_bienici", "url_figaro", "exterieur", "parking", "parking_option", "ext_source", "park_source",
                  "assouplissements", "publie", "deja_propose")
        sug = {"genere": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
               "lues": {"bienici": len(bi), "figaro": len(fi)},
               "echecs": ECHECS,
               "parfaits": sum(1 for x in items if not x["assouplissements"] and not x["suspect"]),
               "criteres": CRITERES,
               "annonces": [{k: x.get(k) for k in champs} for x in pool]}
        json.dump(sug, open(os.path.join(ROOT, "suggestions.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    os.makedirs(os.path.dirname(hist_path), exist_ok=True)
    json.dump(hist, open(hist_path, "w"), indent=1, ensure_ascii=False)

    # ---- rapport
    os.makedirs(a.out, exist_ok=True)
    nb_parfaits = sum(1 for x in items if not x["assouplissements"] and not x["deja_sur_site"] and not x["suspect"])
    L = [f"# Top 10 logements à contacter — {datetime.date.today().strftime('%d/%m/%Y')}", "",
         f"Annonces lues : {len(bi)} sur Bien'ici, {len(fi)} dans le budget sur Le Figaro. "
         f"Parfaits trouvés : {nb_parfaits}. "
         + ("Doublons avec « Mes logements » exclus : " + str(sum(1 for x in items if x['deja_sur_site'])) + "." if sites is not None else "⚠️ Site « Mes logements » non consulté : les doublons n'ont pas été vérifiés."), ""]
    for n, x in enumerate(top, 1):
        etiquette = "⭐ PARFAIT" if not x["assouplissements"] else "≈ " + " + ".join(x["assouplissements"])
        arr = "1er" if x["arr"] == 1 else f"{x['arr']}e"
        ext = (x["exterieur"] or "—") + (" (d'après la description)" if x["ext_source"] == "description" else "")
        park = ("en option, payant en plus" if x.get("parking_option") else ("oui" if x["parking"] else "non")) + (" (d'après la description)" if x["park_source"] == "description" else "")
        L.append(f"## {n}. {etiquette} — T{x['pieces']} {arr} ({x['quartier'] or 'quartier ?'}) — {x['loyer']} € CC")
        L.append(f"- {x.get('surface') or '?'} m² · extérieur : {ext} · parking : {park}" + (" · déjà proposé le " + x['deja_propose'] if x.get('deja_propose') and x['deja_propose'] != today else " · 🆕 nouveau"))
        if x.get("url_bienici"):
            L.append(f"- Bien'ici : {x['url_bienici']}")
        if x.get("url_figaro"):
            L.append(f"- Le Figaro : {x['url_figaro']}")
        L.append("- SeLoger : non vérifiable (le site bloque la lecture automatique)")
        L.append(f"- Agence : {x['agence'] or '?'}" + (f" — {x['url_agence']}" if x.get("url_agence") else "") + (f" (réf. {x['reference']})" if x.get("reference") else ""))
        L.append("")
    if not top:
        L.append("Aucune annonce ne correspond aujourd'hui, même en assouplissant un critère.")
    open(os.path.join(a.out, "rapport.md"), "w").write("\n".join(L))
    json.dump([{k: v for k, v in x.items() if not k.startswith("_") and k != "description"} for x in top],
              open(os.path.join(a.out, "resultats.json"), "w"), indent=1, ensure_ascii=False)
    print("\n".join(L))


if __name__ == "__main__":
    main()
