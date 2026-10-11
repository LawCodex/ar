# LawCodex — Argentina (`ar`)

Argentina's national legislation as Markdown, one file per norm. Part of [LawCodex](https://github.com/LawCodex).
The texts are in Spanish, the official language.

Retrieved 2026-10-12. InfoLEG open-data CSV dated 2026-10-01. Laws run up to Ley 27.826 (September 2026).

## Contents

| Directory | Content | Files | `status: in_force` | `status: repealed` | consolidated text (`texto actualizado`) |
|---|---|---:|---:|---:|---:|
| `constitucion/` | Constitución de la Nación Argentina, 1853 with the reforms up to 1994 (official text ordered by Ley 24.430) | 1 | 1 | 0 | n/a (not amended since 1994) |
| `codigos/` | National codes (see below) | 11 | 10 | 0 | 10 |
| `leyes/<year>/` | Leyes del Congreso, including laws passed by de facto governments and numbered as laws | 8,226 | 3,247 | 382 | 714 |
| `decretos-ley/<year>/` | Decretos-ley (de facto decree-laws, mostly 1943–1946, 1955–1958 and 1962–1963) | 634 | 339 | 35 | 79 |
| `dnu/<year>/` | Decretos de Necesidad y Urgencia (DNU) | 1,130 | 989 | 71 | 106 |
| `decretos/<year>/` | Other executive decrees, **only** those for which InfoLEG keeps a consolidated text. These include the *textos ordenados* of the tax laws (Ganancias, IVA, Procedimiento Tributario...) and the main regulatory decrees. | 1,050 | (not checked) | (not checked) | 1,050 |
| **Total** | | **11,052** | | | |

`codigos/` contains:

- Código Civil y Comercial (Ley 26.994)
- Código Penal (Ley 11.179, t.o. 1984)
- Código Procesal Civil y Comercial de la Nación (Ley 17.454)
- Código Procesal Penal Federal (Ley 27.063)
- Código Procesal Penal (Ley 23.984)
- Código Aduanero (Ley 22.415)
- Código de Minería (Ley 1.919)
- Código Aeronáutico (Ley 17.285)
- Código Electoral Nacional (Ley 19.945)
- Ley de la Navegación (Ley 20.094)
- Ley 18.284, the law that sets up the Código Alimentario Argentino. The Código Alimentario itself is an annex to a decree and is not included.

Other key laws, such as the Ley de Contrato de Trabajo (20.744), Sociedades (19.550), Concursos y Quiebras (24.522) and Procedimiento Tributario (11.683), are in `leyes/<year>/`.

### Validity status (`status`)

InfoLEG does not publish whether a norm is still in force. That information comes from **SAIJ**, the Sistema Argentino de Información Jurídica, which belongs to the same Ministry. SAIJ classifies each national norm, and that classification is mapped to `status` as follows:

- `Vigente, de alcance general` → `status: in_force`
- `Derogada` → `status: repealed`
- everything else → `status: unknown`. This covers `Individual, Solo Modificatoria o Sin Eficacia` (private laws, pensions, laws that only amend others or have no further effect), `Vetada`, and norms SAIJ does not list.

The raw SAIJ value is kept in `saij_status`, with a `saij_url`. The repository includes every norm that has an online text, whatever its status. To get only the law in force, filter on `status: in_force`.

## Not included

- **Laws without an online text.** About 19,500 of the 27,620 national laws in InfoLEG (mostly 1862–1990) have only metadata and a summary, with no text. These are overwhelmingly private laws: pensions, grants, honours, expropriations, budgets and the like. They are skipped. Of the laws SAIJ marks *Vigente, de alcance general*, 124 had no InfoLEG text. They were taken from SAIJ instead (see Sources). After that, all 3,251 laws SAIJ marks in force are covered.
- **Annexes published only as PDF, images or scanned tables.** These appear as links (`[VER TEXTO COMPLETO](...pdf)`, `[imagen: ...]`) to the official InfoLEG file. Images and binaries are not copied.
- **Other decrees.** About 75,000 ordinary executive decrees are not included, because InfoLEG has no consolidated text for them. Also excluded: resoluciones, disposiciones, decisiones administrativas, comunicaciones of the BCRA and similar (about 320,000 secondary norms), and provincial legislation. Laws approving treaties are included in `leyes/` whenever InfoLEG has their text, but the treaty text itself is often published only as an attachment.
- **Decrees without SAIJ status.** No validity status was harvested for `decretos/`, so all of them are `status: unknown`.

## Sources

1. **InfoLEG** (Información Legislativa y Documental, Ministerio de Justicia de la Nación), https://www.infoleg.gob.ar
   - Open-data index: [Base de datos legislativos InfoLEG](https://datos.jus.gob.ar/dataset/base-de-datos-legislativos-infoleg), file `base-infoleg-normativa-nacional.zip`. It lists every norm with links to its *texto original* (`norma.htm`) and, where one exists, *texto actualizado* (`texact.htm`).
   - Texts: `https://servicios.infoleg.gob.ar/infolegInternet/anexos/<range>/<id>/{texact,norma}.htm`. The consolidated text (`texact.htm`) is used whenever InfoLEG has one; otherwise the original text. The front matter field `text_version` says which.
2. **SAIJ** (Sistema Argentino de Información Jurídica, Ministerio de Justicia), https://www.saij.gob.ar
   - Validity status: harvested from the JSON search endpoint `https://www.saij.gob.ar/busqueda` (metadata only, about 32,000 national Leyes, Decretos-ley and DNU).
   - Fallback texts: 219 norms that SAIJ marks in force but InfoLEG has no text for (124 leyes, 42 decretos-ley, 53 DNU). They come from SAIJ's document JSON at `https://www.saij.gob.ar/view-document?guid=<uuid>`, which is SAIJ's own text with articles separated. These files have `text_version: "texto SAIJ ..."`.

Front matter fields:

- `identifier`: the official number, e.g. `Ley 26994` or `Decreto-Ley 1285/1958`
- `infoleg_id` or `saij_id`
- `date`: date of sanción or signature
- `published`: date in the Boletín Oficial
- `issuer`
- `status`, `saij_status`
- `source`: the InfoLEG norm page
- `source_text`: the exact HTML that was converted

Headings follow each norm's own structure: Anexo, Parte, Libro, Título, Capítulo, Sección, Parágrafo, then the article as the deepest heading. Structure levels are capped at `#####`. Article texts quoted inside amending laws ("Sustitúyese el artículo X por el siguiente: ...") are shown as **bold** labels, not headings. InfoLEG's editorial notes on modifications are kept as they appear, e.g. "(Artículo sustituido por art. 1° de la Ley N° ...)", along with the "Antecedentes Normativos" lists.

## Licence

The InfoLEG database is published by the Ministerio de Justicia under **Creative Commons Attribution 4.0** ([datos.jus.gob.ar](https://datos.jus.gob.ar/dataset/base-de-datos-legislativos-infoleg)).

Official legislative texts are generally treated as freely reproducible public acts. The texts here are faithful conversions. They are **not** the official publication: only the Boletín Oficial is authentic.

## Regenerating

```sh
pip install -r scripts/requirements.txt
mkdir -p ../_raw/ar/csv && cd ../_raw/ar
curl -LO https://datos.jus.gob.ar/dataset/d9a963ea-8b1d-4ca3-9dd9-07a4773e8c23/resource/bf0ec116-ad4e-4572-a476-e57167a84403/download/base-infoleg-normativa-nacional.zip
unzip base-infoleg-normativa-nacional.zip -d csv
AR_RAW=$PWD python ../../ar/scripts/ar_saij.py              # SAIJ validity status -> saij_status.json
AR_RAW=$PWD python ../../ar/scripts/ar_fetch.py             # InfoLEG HTML -> html/<id>.htm (2 workers, cached)
AR_RAW=$PWD python ../../ar/scripts/ar_convert.py ../../ar  # HTML -> Markdown
AR_RAW=$PWD python ../../ar/scripts/ar_saij_text.py ../../ar  # SAIJ fallback texts
```

InfoLEG has no `robots.txt`. The downloads used 2 concurrent workers, with a pause between requests on each worker. SAIJ's `robots.txt` (no crawl-delay) does not disallow the endpoints used, and requests to it were spaced 2–3 s apart.
