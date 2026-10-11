#!/usr/bin/env python3
"""Harvest validity status (estado de vigencia) of national norms from SAIJ's search endpoint.

Writes _raw/ar/saij_status.json: {"LEY:<n>": {...}, "DL:<n>-<year>": ..., "DNU:<n>-<year>": ...}
Only metadata is used (no document texts). Polite: 1 request every 3 s.
"""
import json, os, sys, time
import requests

RAW = os.environ.get("AR_RAW", os.path.join(os.path.dirname(__file__), "..", "..", "_raw", "ar"))
UA = "LawCodex/1.0 (+https://github.com/LawCodex)"
URL = "https://www.saij.gob.ar/busqueda"
FACET = "Total|Tipo de Documento/Legislación/{t}|Fecha{f}|Organismo|Publicación|Tema|Estado de Vigencia{e}|Autor|Jurisdicción/Nacional"
ESTADOS = ["Vigente, de alcance general", "Individual, Solo Modificatoria o Sin Eficacia",
           "Derogada", "Vetada", "categoriavacia"]
PAGE = 500
MAXOFF = 1000  # SAIJ returns HTTP 500 for offset >= 1000


def fetch(sess, t, off, f="", e="", p=PAGE):
    params = {"o": off, "p": p, "f": FACET.format(t=t, f=f, e=e), "s": "fecha-rango|DESC", "v": "colapsada"}
    for a in range(6):
        try:
            r = sess.get(URL, params=params, timeout=120)
            if r.status_code == 200:
                time.sleep(2)
                return r.json()["searchResults"]
            print("HTTP", r.status_code, t, f, e, off, file=sys.stderr)
        except Exception as ex:  # noqa
            print("err", ex, file=sys.stderr)
        time.sleep(10 * (a + 1))
    raise RuntimeError("SAIJ fetch failed %s %s %s %s" % (t, f, e, off))


def total_of(d):
    for cat in d["categoriesResultList"]:
        if cat["facetName"] == "Total":
            return int(sum(ch["facetHits"] for ch in cat["facetChildren"]))
    return 0


def add_docs(out, docs):
    for doc in docs:
        a = json.loads(doc["documentAbstract"])["document"]
        c = a["content"]
        tn = (c.get("tipo-norma") or {}).get("codigo", "")
        rec = {
            "tipo": tn,
            "numero": c.get("numero-norma"),
            "fecha": c.get("fecha"),
            "estado": c.get("estado"),
            "titulo": c.get("titulo-norma"),
            "uuid": a["metadata"]["uuid"],
            "url": "https://www.saij.gob.ar/%s-%s" % (
                a["metadata"]["friendly-url"]["subdomain"],
                a["metadata"]["friendly-url"]["description"]),
        }
        out["%s:%s:%s" % (tn, rec["numero"], str(rec["fecha"] or "")[:4])] = rec


DONE = set()
PARTIAL = os.path.join(RAW, "saij_partial.json")


def save_partial(out):
    json.dump({"done": sorted(DONE), "out": out}, open(PARTIAL, "w"), ensure_ascii=False)


def harvest(sess, out, t, f="", e=""):
    key = "%s|%s|%s" % (t, f, e)
    if key in DONE:
        return
    d = fetch(sess, t, 0, f, e, p=1)
    total = total_of(d)
    if total == 0:
        DONE.add(key)
        return
    if total > MAXOFF:
        if not f:
            for y in range(1810, time.gmtime().tm_year + 1):
                harvest(sess, out, t, "/%d" % y, e)
        elif f.count("/") == 1:
            for m in range(1, 13):
                harvest(sess, out, t, "%s/%02d" % (f, m), e)
        elif not e:
            for es in ESTADOS:
                harvest(sess, out, t, f, "/" + es)
        else:
            print("WARNING: cannot split further", t, f, e, total, file=sys.stderr)
            for off in range(0, MAXOFF, PAGE):
                add_docs(out, fetch(sess, t, off, f, e)["documentResultList"])
        return
    for off in range(0, total, PAGE):
        add_docs(out, fetch(sess, t, off, f, e)["documentResultList"])
    DONE.add(key)
    save_partial(out)
    print(t, f, e, total, len(out), file=sys.stderr, flush=True)


def main():
    os.makedirs(RAW, exist_ok=True)
    sess = requests.Session()
    sess.headers["User-Agent"] = UA
    out = {}
    if os.path.exists(PARTIAL):
        pd = json.load(open(PARTIAL))
        DONE.update(pd["done"])
        out.update(pd["out"])
    for t in ("Ley", "Decreto/Decreto de Necesidad y Urgencia"):
        harvest(sess, out, t)
    json.dump(out, open(os.path.join(RAW, "saij_status.json"), "w"), ensure_ascii=False, indent=0)
    print(len(out), "records")


if __name__ == "__main__":
    main()
