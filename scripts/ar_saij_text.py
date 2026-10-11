#!/usr/bin/env python3
"""Fallback source: national norms that SAIJ marks "Vigente, de alcance general" (Leyes,
Decretos-Ley, DNU) but for which InfoLEG has no online text. Texts are taken from SAIJ's
document JSON (https://www.saij.gob.ar/view-document?guid=<uuid>) and written as Markdown.

Usage: ar_saij_text.py <repo_dir>
Needs _raw/ar/saij_status.json (ar_saij.py) and the InfoLEG CSV. Cache: _raw/ar/saij/<uuid>.json
"""
import csv, datetime, json, os, re, sys, time
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ar_convert import slugify, yq, ws, esc_md, RAW, CSV, RETRIEVED  # noqa: E402

UA = "LawCodex/1.0 (+https://github.com/LawCodex)"
VIEW = "https://www.saij.gob.ar/view-document?guid="
CACHE = os.path.join(RAW, "saij")
UNKNOWN_KEYS = {}


def missing():
    csv.field_size_limit(10 ** 9)
    have = set()
    for r in csv.DictReader(open(CSV, encoding="utf-8")):
        if not (r["texto_original"] or r["texto_actualizado"]):
            continue
        t = r["tipo_norma"]
        y = r["fecha_sancion"][:4]
        if t == "Ley":
            have.add(("LEY", r["numero_norma"]))
        elif t == "Decreto/Ley":
            have.add(("DLE", r["numero_norma"], y))
        elif t == "Decreto" and r["clase_norma"] == "DNU":
            have.add(("DNU", r["numero_norma"], y))
    out = []
    for v in json.load(open(os.path.join(RAW, "saij_status.json"))).values():
        if v["estado"] != "Vigente, de alcance general" or v["tipo"] not in ("LEY", "DLE", "DNU"):
            continue
        k = ("LEY", str(v["numero"])) if v["tipo"] == "LEY" else (v["tipo"], str(v["numero"]), str(v["fecha"])[:4])
        if k not in have:
            out.append(v)
    return out


def get(sess, uuid):
    p = os.path.join(CACHE, uuid + ".json")
    if os.path.exists(p):
        return json.load(open(p))
    for a in range(5):
        try:
            r = sess.get(VIEW + uuid, timeout=120)
            if r.status_code == 200:
                d = json.loads(r.json()["data"])
                json.dump(d, open(p, "w"), ensure_ascii=False)
                time.sleep(2)
                return d
            print("HTTP", r.status_code, uuid, file=sys.stderr)
        except Exception as e:
            print("ERR", uuid, e, file=sys.stderr)
        time.sleep(10 * (a + 1))
    return None


def paras(s):
    if not s:
        return []
    if not isinstance(s, str):
        s = str(s)
    s = re.sub(r"\[\[/?p\]\]", "\n\n", s)
    s = re.sub(r"\[\[/?[^\]]*\]\]", "", s)
    return [ws(x) for x in s.split("\n\n") if ws(x)]


ART_LABEL = re.compile(r"^(?:ART[IÍ]CULO|Art[íi]culo|ART\.|Art\.)\s*\d+\s*(?:bis|ter|quater)?\s*[°º]?\s*[-.:—–]*\s*", re.I)


def render_seg(seg, depth, lines):
    if isinstance(seg, list):
        for s in seg:
            render_seg(s, depth, lines)
        return
    if not isinstance(seg, dict):
        return
    for k, v in seg.items():
        if k == "titulo-particion":
            lines.append("#" * min(5, depth) + " " + ws(str(v)))
        elif k == "segmento":
            render_seg(v, depth + 1, lines)
        elif k == "articulo":
            for a in (v if isinstance(v, list) else [v]):
                n = a.get("numero-articulo")
                ps = paras(a.get("texto"))
                h = "###### Artículo %s" % n if n is not None else "###### Artículo"
                if a.get("titulo-articulo"):
                    h += " — " + ws(str(a["titulo-articulo"]))
                lines.append(h)
                if ps:
                    ps[0] = ART_LABEL.sub("", ps[0], count=1)
                for p in ps:
                    if p:
                        lines.append(esc_md(p))
                for kk in a:
                    if kk not in ("numero-articulo", "texto", "referencias-normativas", "modifica-a",
                                  "modificado-por", "derogado-por", "deroga-a", "id", "nota",
                                  "titulo-articulo", "observado-por", "observa-a"):
                        UNKNOWN_KEYS[kk] = UNKNOWN_KEYS.get(kk, 0) + 1
                if a.get("nota"):
                    for p in paras(a.get("nota")):
                        lines.append(esc_md(p))
        elif k in ("texto", "anexo", "texto-anexo"):
            for p in paras(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)):
                lines.append(esc_md(p))
        else:
            UNKNOWN_KEYS["seg:" + k] = UNKNOWN_KEYS.get("seg:" + k, 0) + 1


def main():
    repo = sys.argv[1]
    os.makedirs(CACHE, exist_ok=True)
    sess = requests.Session()
    sess.headers["User-Agent"] = UA
    todo = missing()
    print("SAIJ fallback documents:", len(todo), file=sys.stderr)
    n = 0
    for v in todo:
        d = get(sess, v["uuid"])
        if not d:
            continue
        c = d["document"]["content"]
        num = str(v["numero"])
        date = str(v["fecha"])[:10]
        year = date[:4]
        titulo = ws(str(c.get("titulo-norma") or v.get("titulo") or "")).rstrip(".")
        if v["tipo"] == "LEY":
            label, typ, rel = "Ley %s" % num, "act", "leyes/%s/ley-%s-%s.md" % (year, num, slugify(titulo))
        elif v["tipo"] == "DLE":
            label, typ = "Decreto-Ley %s/%s" % (num, year), "decree-law"
            rel = "decretos-ley/%s/decreto-ley-%s-%s-%s.md" % (year, num, year, slugify(titulo))
        else:
            label, typ = "Decreto de Necesidad y Urgencia %s/%s" % (num, year), "decree"
            rel = "dnu/%s/dnu-%s-%s-%s.md" % (year, num, year, slugify(titulo))
        title = "%s: %s" % (label, titulo) if titulo else label
        lines = []
        if c.get("sancion"):
            lines.append(esc_md(ws(c["sancion"])))
        for k, lab in (("visto", "VISTO"), ("considerando", "CONSIDERANDO")):
            v2 = c.get(k)
            ps = paras(v2.get("texto") if isinstance(v2, dict) else v2)
            if ps:
                lines.append("**%s:** %s" % (lab, ps[0]))
                lines.extend(esc_md(p) for p in ps[1:])
        render_seg({k: c[k] for k in ("segmento", "articulo") if c.get(k)}, 2, lines)
        for k in ("anexo", "anexos"):
            if c.get(k):
                lines.append("## Anexo")
                for p in paras(c[k] if isinstance(c[k], str) else json.dumps(c[k], ensure_ascii=False)):
                    lines.append(esc_md(p))
        fi = c.get("firmantes")
        if isinstance(fi, dict):
            fi = fi.get("firmantes")
        if fi:
            lines.append(esc_md(ws(str(fi))))
        if not any(l.startswith("###### ") for l in lines) and len(lines) < 2:
            print("no text", label, v["url"], file=sys.stderr)
            continue
        pub = ((c.get("publicacion-codificada") or {}).get("publicacion-decodificada") or {})
        fm = ["---", "title: " + yq(title), "identifier: " + yq(label), "saij_id: " + yq(v["uuid"]),
              "type: " + typ, "jurisdiction: ar", "language: es", "date: " + date]
        if pub.get("organismo") == "Boletín Oficial" and pub.get("fecha"):
            fm.append("published: " + pub["fecha"].replace(" ", "-"))
        fm += ["status: in_force", "saij_status: " + yq(v["estado"]),
               "text_version: " + yq("texto SAIJ (InfoLEG has no online text for this norm)"),
               "source: " + yq(v["url"].replace(" ", "-")), "source_text: " + yq(VIEW + v["uuid"]),
               "retrieved: " + RETRIEVED, "---"]
        md = "\n".join(fm) + "\n\n# " + title + "\n\n" + "\n\n".join(lines) + "\n"
        p = os.path.join(repo, rel)
        if os.path.exists(p):
            continue
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(md)
        n += 1
    print("written", n, "unknown keys", UNKNOWN_KEYS, file=sys.stderr)


if __name__ == "__main__":
    main()
