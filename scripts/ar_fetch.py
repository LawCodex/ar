#!/usr/bin/env python3
"""Download InfoLEG HTML texts (texto actualizado when available, else texto original) for
national Leyes, Decretos-Ley and DNU listed in the InfoLEG open-data CSV.

Usage: ar_fetch.py            (expects _raw/ar/csv/base-infoleg-normativa-nacional.csv)
Cache: _raw/ar/html/<id>.htm (skips existing files). Concurrency 2, ~0.5 s between requests/worker.
"""
import csv, os, sys, time, threading, queue
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.environ.get("AR_RAW", os.path.join(HERE, "..", "..", "_raw", "ar"))
CSV = os.path.join(RAW, "csv", "base-infoleg-normativa-nacional.csv")
UA = "LawCodex/1.0 (+https://github.com/LawCodex)"
WORKERS = 2
DELAY = 0.5


def selected(row):
    t = row["tipo_norma"]
    if t in ("Ley", "Decreto/Ley"):
        return True
    if t == "Decreto" and row["clase_norma"] == "DNU":
        return True
    return False


def norm_url(u):
    return u.replace("http://", "https://", 1) if u.startswith("http://") else u


def jobs():
    csv.field_size_limit(10 ** 9)
    for row in csv.DictReader(open(CSV, encoding="utf-8")):
        if not selected(row):
            continue
        u = row["texto_actualizado"] or row["texto_original"]
        if u:
            yield row["id_norma"], norm_url(u)


def worker(q, sess, outdir, stats):
    while True:
        item = q.get()
        if item is None:
            return
        nid, url = item
        path = os.path.join(outdir, nid + ".htm")
        ok = False
        for a in range(5):
            try:
                r = sess.get(url, timeout=120)
                if r.status_code == 200:
                    tmp = path + ".part"
                    open(tmp, "wb").write(r.content)
                    os.replace(tmp, path)
                    ok = True
                    break
                if r.status_code == 404:
                    break
                print("HTTP", r.status_code, url, file=sys.stderr)
            except Exception as e:
                print("ERR", url, e, file=sys.stderr)
            time.sleep(5 * (a + 1))
        if not ok:
            stats["fail"].append(url)
            print("FAIL", nid, url, file=sys.stderr)
        stats["n"] += 1
        if stats["n"] % 200 == 0:
            print("progress", stats["n"], file=sys.stderr, flush=True)
        time.sleep(DELAY)


def main():
    outdir = os.path.join(RAW, "html")
    os.makedirs(outdir, exist_ok=True)
    todo = [(i, u) for i, u in jobs() if not os.path.exists(os.path.join(outdir, i + ".htm"))]
    print("to fetch:", len(todo), file=sys.stderr)
    q = queue.Queue()
    for j in todo:
        q.put(j)
    stats = {"n": 0, "fail": []}
    ths = []
    for _ in range(WORKERS):
        s = requests.Session()
        s.headers["User-Agent"] = UA
        t = threading.Thread(target=worker, args=(q, s, outdir, stats))
        t.start()
        ths.append(t)
        q.put(None)
    for t in ths:
        t.join()
    open(os.path.join(RAW, "fetch_failures.txt"), "w").write("\n".join(stats["fail"]))
    print("done", stats["n"], "failures", len(stats["fail"]), file=sys.stderr)


if __name__ == "__main__":
    main()
