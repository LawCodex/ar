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
FACET = "Total|Tipo de Documento/Legislación/{t}|Fecha|Organismo|Publicación|Tema|Estado de Vigencia|Autor|Jurisdicción/Nacional"
PAGE = 500


def fetch(sess, t, off):
    params = {"o": off, "p": PAGE, "f": FACET.format(t=t), "s": "fecha-rango|DESC", "v": "colapsada"}
    for a in range(6):
        try:
            r = sess.get(URL, params=params, timeout=120)
            if r.status_code == 200:
                return r.json()
        except Exception as e:  # noqa
            print("err", e, file=sys.stderr)
        time.sleep(10 * (a + 1))
    raise RuntimeError("SAIJ fetch failed %s %s" % (t, off))


def main():
    os.makedirs(RAW, exist_ok=True)
    sess = requests.Session()
    sess.headers["User-Agent"] = UA
    out = {}
    for t in ("Ley", "Decreto/Decreto de Necesidad y Urgencia"):
        off = 0
        while True:
            d = fetch(sess, t, off)["searchResults"]
            docs = d["documentResultList"]
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
                key = "%s:%s:%s" % (tn, rec["numero"], (rec["fecha"] or "")[:4])
                out[key] = rec
            total = 0
            for cat in d["categoriesResultList"]:
                if cat["facetName"] == "Total":
                    total = sum(ch["facetHits"] for ch in cat["facetChildren"])
            print(t, off, len(docs), total, file=sys.stderr)
            off += PAGE
            if not docs or off >= total:
                break
            time.sleep(3)
    json.dump(out, open(os.path.join(RAW, "saij_status.json"), "w"), ensure_ascii=False, indent=0)
    print(len(out), "records")


if __name__ == "__main__":
    main()
