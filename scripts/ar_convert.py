#!/usr/bin/env python3
"""Convert InfoLEG HTML (downloaded by ar_fetch.py) to LawCodex Markdown.

Usage: ar_convert.py <repo_dir>
Reads  _raw/ar/csv/base-infoleg-normativa-nacional.csv, _raw/ar/html/<id>.htm,
       _raw/ar/saij_status.json (optional; from ar_saij.py)
Writes <repo_dir>/{constitucion,codigos,leyes,decretos-ley,dnu}/...
"""
import csv, datetime, json, os, re, sys, unicodedata
from bs4 import BeautifulSoup, NavigableString, Comment, Tag

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.environ.get("AR_RAW", os.path.join(HERE, "..", "..", "_raw", "ar"))
CSV = os.path.join(RAW, "csv", "base-infoleg-normativa-nacional.csv")
HTML = os.path.join(RAW, "html")
RETRIEVED = os.environ.get("AR_RETRIEVED", datetime.date.today().isoformat())

# Codes: law number -> (slug, title)
CODES = {
    "24430": ("constitucion", "Constitución de la Nación Argentina"),
    "26994": ("codigo-civil-y-comercial", "Código Civil y Comercial de la Nación"),
    "11179": ("codigo-penal", "Código Penal de la Nación Argentina"),
    "17454": ("codigo-procesal-civil-y-comercial", "Código Procesal Civil y Comercial de la Nación"),
    "22415": ("codigo-aduanero", "Código Aduanero"),
    "27063": ("codigo-procesal-penal-federal", "Código Procesal Penal Federal"),
    "23984": ("codigo-procesal-penal", "Código Procesal Penal de la Nación"),
    "1919": ("codigo-de-mineria", "Código de Minería"),
    "17285": ("codigo-aeronautico", "Código Aeronáutico"),
    "19945": ("codigo-electoral-nacional", "Código Electoral Nacional"),
    "18284": ("codigo-alimentario-argentino", "Código Alimentario Argentino (ley)"),
    "20094": ("ley-de-navegacion", "Ley de la Navegación"),
}

ESTADO_MAP = {
    "Vigente, de alcance general": "in_force",
    "Derogada": "repealed",
}

BLOCK = {"p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li", "ul", "ol", "blockquote",
         "center", "tr", "hr", "dd", "dt", "dl", "pre", "section", "article", "header", "footer"}

ROMAN = r"[IVXLCDM]+"
ORD = (r"(?:PRIMER[OA]?|SEGUND[OA]|TERCER[OA]?|CUART[OA]|QUINT[OA]|SEXT[OA]|S[EÉ]PTIM[OA]|"
       r"OCTAV[OA]|NOVEN[OA]|D[EÉ]CIM[OA]|UNDÉCIM[OA]|DUOD[EÉ]CIM[OA]|PRELIMINAR|[ÚU]NIC[OA]|"
       r"PRIMERO|ESPECIAL|GENERAL|COMPLEMENTARI[OA])")
NUMTOK = r"(?:%s|\d+(?:\s*[°ºª])?|%s)(?:\s*(?:BIS|TER|QUATER))?" % (ROMAN, ORD)
STRUCT = [
    ("parte", re.compile(r"^(?:(?:PRIMERA|SEGUNDA|TERCERA|CUARTA|QUINTA)\s+PARTE|PARTE\s+(?:%s|%s))\b" % (ROMAN, r"PRIMERA|SEGUNDA|TERCERA|CUARTA|\d+"), re.I)),
    ("libro", re.compile(r"^LIBRO\s+%s\b" % NUMTOK, re.I)),
    ("titulo", re.compile(r"^T[IÍ]TULO\s+%s\b" % NUMTOK, re.I)),
    ("capitulo", re.compile(r"^CAP[IÍ]TULO\s+%s\b" % NUMTOK, re.I)),
    ("seccion", re.compile(r"^SECCI[OÓ]N\s+%s\b" % NUMTOK, re.I)),
    ("parrafo", re.compile(r"^PAR[AÁ]GRAFO\s+%s\b" % NUMTOK, re.I)),
]
ANEXO = re.compile(r"^ANEXO\b")
ART = re.compile(
    r"^(?P<label>(?:ART[IÍ]CULO|Art[íi]culo|ART\.|Art\.)\s*"
    r"(?P<num>\d+(?:\s*[°º])?(?:[\s-]*(?:bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies|BIS|TER|QUATER|QUINQUIES|SEXIES|SEPTIES|OCTIES|NONIES|DECIES)\b)?\s*[°º]?))"
    r"\s*(?:[-.:—–]+\s*)*(?P<rest>.*)$", re.S)
ART_ORD = re.compile(
    r"^(?P<label>(?:ART[IÍ]CULO|Art[íi]culo)\s+(?:PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|S[EÉ]PTIMO|OCTAVO|NOVENO|D[EÉ]CIMO|[ÚU]NICO|Primero|Segundo|Tercero|Cuarto|Quinto|Sexto|S[eé]ptimo|Octavo|Noveno|D[eé]cimo|[ÚUúu]nico)(?:\s+(?:PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|S[EÉ]PTIMO|OCTAVO|NOVENO|primero|segundo|tercero|cuarto|quinto|sexto|s[eé]ptimo|octavo|noveno))?)"
    r"\s*[°º]?\s*(?:[-.:—–]+\s*)+(?P<rest>.*)$", re.S)
INLINE_ART = re.compile(r"(?<=\))\s*(?=ART[IÍ]CULO\s+\d+\s*(?:bis|ter|quater)?\s*[°º]?\s*[-.—–])")
AMEND = re.compile(r"(?i)(siguiente(?:s)?(?: texto| t[eé]rminos| redacci[oó]n)?|como sigue|redactad[oa] de la siguiente manera|este texto)\s*[:.]?\s*[\"“]?\s*$")
TOC_LINE = re.compile(r"^Arts?\.\s*\d", re.I)


def slugify(s, maxlen=70):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if len(s) > maxlen:
        s = s[:maxlen].rsplit("-", 1)[0]
    return s or "sin-titulo"


def decode(b):
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("cp1252", "replace")


def ws(s):
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()


def table_md(tbl, base):
    rows = []
    complex_ = bool(tbl.find(["table"])) or any(
        c.get("colspan") not in (None, "1") or c.get("rowspan") not in (None, "1")
        for c in tbl.find_all(["td", "th"]))
    for tr in tbl.find_all("tr"):
        if tr.find_parent("table") is not tbl:
            continue
        cells = [ws(c.get_text(" ")) for c in tr.find_all(["td", "th"], recursive=False)]
        if any(cells):
            rows.append(cells)
    if not rows:
        return ""
    if complex_:
        # keep as minimal HTML
        out = ["<table>"]
        for tr in tbl.find_all("tr"):
            if tr.find_parent("table") is not tbl:
                continue
            cs = []
            for c in tr.find_all(["td", "th"], recursive=False):
                attrs = "".join(' %s="%s"' % (a, c.get(a)) for a in ("colspan", "rowspan")
                                if c.get(a) not in (None, "1"))
                cs.append("<td%s>%s</td>" % (attrs, ws(c.get_text(" ")).replace("<", "&lt;")))
            out.append("<tr>" + "".join(cs) + "</tr>")
        out.append("</table>")
        return "\n".join(out)
    n = max(len(r) for r in rows)
    rows = [r + [""] * (n - len(r)) for r in rows]
    esc = lambda x: x.replace("|", "\\|")
    lines = ["| " + " | ".join(esc(c) for c in rows[0]) + " |", "|" + "---|" * n]
    for r in rows[1:]:
        lines.append("| " + " | ".join(esc(c) for c in r) + " |")
    return "\n".join(lines)


def blocks_from_html(raw, base):
    soup = BeautifulSoup(decode(raw), "lxml")
    for t in soup(["script", "style", "head", "map", "noscript"]):
        t.decompose()
    for t in soup.select("#wrap, #encabezado_norma, header#branding"):
        t.decompose()
    for c in soup.find_all(string=lambda x: isinstance(x, Comment)):
        c.extract()
    body = soup.body or soup
    out = []  # list of ("p", text) / ("table", md)
    buf = []

    def flush():
        t = ws("".join(buf))
        buf.clear()
        if t:
            out.append(("p", t))

    def walk(node):
        for ch in node.children:
            if isinstance(ch, NavigableString):
                buf.append(str(ch))
                continue
            if not isinstance(ch, Tag):
                continue
            name = ch.name
            if name == "table":
                flush()
                md = table_md(ch, base)
                if md:
                    out.append(("table", md))
                continue
            if name == "img":
                src = ch.get("src")
                if src and not src.startswith("data:"):
                    if src.startswith("//"):
                        src = "https:" + src
                    elif src.startswith("/"):
                        src = "https://servicios.infoleg.gob.ar" + src
                    elif not src.startswith("http"):
                        src = base.rsplit("/", 1)[0] + "/" + src
                    buf.append(" [imagen: %s] " % src)
                continue
            if name in BLOCK:
                flush()
                walk(ch)
                flush()
            else:
                walk(ch)
    walk(body)
    flush()
    # split paragraphs where an article starts right after a closing note parenthesis
    res = []
    for kind, t in out:
        if kind == "p":
            for part in INLINE_ART.split(t):
                part = part.strip()
                if part:
                    res.append(("p", part))
        else:
            res.append((kind, t))
    return res


def struct_kind(t):
    if len(t) > 160:
        return None
    if ANEXO.match(t) and len(t) < 100:
        return "anexo"
    for k, rx in STRUCT:
        m = rx.match(t)
        if m:
            rest = t[m.end():].strip()
            if not rest or rest[0] in "-.:—–" or rest == rest.upper():
                return k
            return None
    return None


def is_art(t):
    return ART.match(t) or ART_ORD.match(t)


def esc_md(t):
    if t[:1] in "#>":
        t = "\\" + t
    if re.match(r"^[-+*]\s", t):
        t = "\\" + t
    if re.match(r"^\d+\.\s", t):
        t = re.sub(r"^(\d+)\.", r"\1\\.", t)
    return t


def to_markdown(blocks):
    # identify heading blocks
    n = len(blocks)
    items = []  # (type, ...)
    i = 0
    kinds_present = []
    while i < n:
        kind, t = blocks[i]
        if kind == "table":
            items.append(("table", t))
            i += 1
            continue
        k = struct_kind(t)
        if k:
            title = t
            j = i + 1
            if j < n and blocks[j][0] == "p":
                nt = blocks[j][1]
                if (len(nt) < 160 and not struct_kind(nt) and not is_art(nt)
                        and not TOC_LINE.match(nt) and not nt.startswith("(")
                        and not nt.endswith((":", ";", ","))):
                    title = t.rstrip(" .-—–:") + " — " + nt
                    j += 1
            if j < n and blocks[j][0] == "p" and TOC_LINE.match(blocks[j][1]):
                # table of contents entry: keep as plain text
                for b in blocks[i:j + 1]:
                    items.append(("p", b[1]))
                i = j + 1
                continue
            items.append(("h", k, title))
            if k not in kinds_present:
                kinds_present.append(k)
            i = j
            continue
        m = is_art(t)
        if m:
            items.append(("art", ws(m.group("label")), m.group("rest").strip()))
            i += 1
            continue
        items.append(("p", t))
        i += 1
    order = ["parte", "libro", "titulo", "capitulo", "seccion", "parrafo"]
    present = [k for k in order if k in kinds_present]
    level = {k: min(5, 2 + idx) for idx, k in enumerate(present)}
    level["anexo"] = 2
    art_level = min(6, 2 + len(present))
    lines = []
    quote = False
    last = 0
    for it in items:
        if it[0] == "h":
            quote = False
            lines.append("#" * level[it[1]] + " " + it[2])
        elif it[0] == "art":
            mnum = re.match(r"\D*(\d+)", it[1])
            num = int(mnum.group(1)) if mnum else None
            suffix = bool(re.search(r"(?i)\b(bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies)\b", it[1]))
            if quote and num is not None and (num == last + 1 or (num == last and suffix)):
                quote = False
            if quote:
                lines.append("**%s.** %s" % (it[1], it[2]) if it[2] else "**%s**" % it[1])
            else:
                if num is not None:
                    last = num
                lines.append("#" * art_level + " " + it[1])
                if it[2]:
                    lines.append(esc_md(it[2]))
            if it[2] and AMEND.search(it[2]):
                quote = True
        elif it[0] == "table":
            lines.append(it[1])
        else:
            if AMEND.search(it[1]):
                quote = True
            lines.append(esc_md(it[1]))
    return "\n\n".join(lines) + "\n"


def yq(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def fmt_num(n):
    return n


def main():
    repo = sys.argv[1]
    csv.field_size_limit(10 ** 9)
    saij = {}
    sp = os.path.join(RAW, "saij_status.json")
    if os.path.exists(sp):
        for k, v in json.load(open(sp)).items():
            tipo, num, year = k.split(":")
            if tipo == "LEY":
                saij[("LEY", num)] = v
            elif tipo == "DL":
                saij[("DL", num, year)] = v
            else:
                saij[(tipo, num, year)] = v
    stats = {}
    manifest = []
    used = set()
    for row in csv.DictReader(open(CSV, encoding="utf-8")):
        t = row["tipo_norma"]
        dnu = t == "Decreto" and row["clase_norma"] == "DNU"
        if not (t in ("Ley", "Decreto/Ley") or dnu):
            continue
        nid = row["id_norma"]
        hp = os.path.join(HTML, nid + ".htm")
        if not os.path.exists(hp):
            continue
        url = (row["texto_actualizado"] or row["texto_original"]).replace("http://", "https://", 1)
        version = "texto actualizado" if row["texto_actualizado"] else "texto original"
        num = row["numero_norma"].strip()
        date = row["fecha_sancion"] or row["fecha_boletin"]
        year = (date or "0000")[:4]
        sum_ = ws(row["titulo_sumario"])
        res = ws(row["titulo_resumido"])
        desc = " — ".join(x for x in (sum_, res) if x)
        if t == "Ley":
            typ = "act"
            label = "Ley %s" % num
            st = saij.get(("LEY", num))
            if num in CODES and nid not in ("",):
                slug, ctitle = CODES[num]
                if slug == "constitucion":
                    rel = "constitucion/constitucion-nacional.md"
                    typ = "constitution"
                    title = ctitle
                else:
                    rel = "codigos/%s.md" % slug
                    typ = "code"
                    title = "%s (%s)" % (ctitle, label)
                cat = "constitucion" if typ == "constitution" else "codigos"
            else:
                cat = "leyes"
                title = "%s: %s" % (label, desc) if desc else label
                rel = "leyes/%s/ley-%s-%s.md" % (year, slugify(num, 20), slugify(sum_ or res))
        elif t == "Decreto/Ley":
            typ = "decree-law"
            cat = "decretos-ley"
            label = "Decreto-Ley %s/%s" % (num, year)
            st = saij.get(("DL", num, year))
            title = "%s: %s" % (label, desc) if desc else label
            rel = "decretos-ley/%s/decreto-ley-%s-%s-%s.md" % (year, slugify(num, 20), year, slugify(sum_ or res))
        else:
            typ = "decree"
            cat = "dnu"
            label = "Decreto de Necesidad y Urgencia %s/%s" % (num, year)
            st = saij.get(("DNU", num, year))
            title = "%s: %s" % (label, desc) if desc else label
            rel = "dnu/%s/dnu-%s-%s-%s.md" % (year, slugify(num, 20), year, slugify(sum_ or res))
        if rel in used:
            rel = rel[:-3] + "-id%s.md" % nid
        used.add(rel)
        blocks = blocks_from_html(open(hp, "rb").read(), url)
        body = to_markdown(blocks)
        if len(body.strip()) < 20:
            continue
        status = ESTADO_MAP.get((st or {}).get("estado"), "unknown")
        fm = ["---",
              "title: " + yq(title),
              "identifier: " + yq(label),
              "infoleg_id: " + yq(nid),
              "type: " + typ,
              "jurisdiction: ar",
              "language: es"]
        if row["fecha_sancion"]:
            fm.append("date: " + row["fecha_sancion"])
        if row["fecha_boletin"]:
            fm.append("published: " + row["fecha_boletin"])
        if row["numero_boletin"]:
            fm.append("boletin_oficial: " + yq(row["numero_boletin"]))
        fm.append("issuer: " + yq(row["organismo_origen"]))
        fm.append("status: " + status)
        if st and st.get("estado"):
            fm.append("saij_status: " + yq(st["estado"]))
            fm.append("saij_url: " + yq(st["url"]))
        fm.append("text_version: " + yq(version))
        fm.append("source: " + yq("https://servicios.infoleg.gob.ar/infolegInternet/verNorma.do?id=" + nid))
        fm.append("source_text: " + yq(url))
        fm.append("retrieved: " + RETRIEVED)
        fm.append("---")
        md = "\n".join(fm) + "\n\n# " + title + "\n\n" + body
        md = re.sub(r"\n{3,}", "\n\n", md)
        p = os.path.join(repo, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(md)
        stats[cat] = stats.get(cat, 0) + 1
        stats[cat + ":" + status] = stats.get(cat + ":" + status, 0) + 1
        manifest.append(rel)
    json.dump(stats, sys.stdout, indent=1, sort_keys=True)
    print()


if __name__ == "__main__":
    main()
