"""
CVE Lookup — enriches Nmap service-version findings with real CVE data.

Lookup chain
------------
1.  **Offline index** (default, fastest): if NVD JSON feeds are present in
    `backend/nvd_offline/`, build an in-memory `(vendor, product) → [CVEs]`
    index once and serve all lookups from it. Zero network calls.
2.  **SQLite cache**: per-CPE results from any previous lookup live here
    for `CACHE_TTL_DAYS` so repeated scans stay fast.
3.  **NVD REST API** (online fallback): when offline data is missing for a
    CPE and `PENTEX_NVD_OFFLINE_ONLY` is NOT set, fall back to the public
    NVD API. Respects rate limits (5 req / 30s, or 50 req / 30s with
    `NVD_API_KEY` set).

Environment switches
--------------------
- `PENTEX_NVD_OFFLINE_DIR`  override the default `backend/nvd_offline/` path
- `PENTEX_NVD_OFFLINE_ONLY` if "1"/"true", disable online fallback entirely
- `NVD_API_KEY`             enables 10× higher online rate limit
"""

from __future__ import annotations

import glob
import gzip
import json
import logging
import os
import re
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────
NVD_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"
CACHE_PATH = os.path.join(os.path.dirname(__file__), "cve_cache.db")
CACHE_TTL_DAYS = 7
HTTP_TIMEOUT = 8
MAX_CVES_PER_PRODUCT = 5

OFFLINE_DIR = os.environ.get(
    "PENTEX_NVD_OFFLINE_DIR",
    os.path.join(os.path.dirname(__file__), "nvd_offline"),
)
_OFFLINE_ONLY = os.environ.get("PENTEX_NVD_OFFLINE_ONLY", "").lower() in ("1", "true", "yes")
# Cap network lookups per scan to bound latency. With an API key the rate
# budget is ~75× higher, so we can afford to look at many more CPEs.
_CAP_NO_KEY = 8     # 8 × 6.5s = ~52 s worst case
_CAP_WITH_KEY = 30  # 30 × 0.7s = ~21 s worst case


def _lookup_cap() -> int:
    return _CAP_WITH_KEY if os.environ.get("NVD_API_KEY") else _CAP_NO_KEY


# Kept for backward-compat callers that imported this name.
MAX_CPE_LOOKUPS_PER_SCAN = _CAP_NO_KEY

# NVD published rate-limits:
#   without API key: 5 req / 30 s  → ~6 s spacing
#   with    API key: 50 req / 30 s → ~0.6 s spacing
_RATE_NO_KEY = 6.5
_RATE_WITH_KEY = 0.7

# Manual NVD rate-limit guard (process-wide)
_last_request_at = 0.0
_rate_lock = threading.Lock()


def _utcnow() -> datetime:
    """Timezone-aware UTC now (replacement for deprecated datetime.utcnow())."""
    return datetime.now(timezone.utc)


def _min_interval() -> float:
    return _RATE_WITH_KEY if os.environ.get("NVD_API_KEY") else _RATE_NO_KEY


# ─── Cache ──────────────────────────────────────────────────────────────
EPSS_API = "https://api.first.org/data/v1/epss"
EPSS_TTL_DAYS = 3   # EPSS scores update daily; refresh every 3 days


def _init_cache() -> None:
    conn = sqlite3.connect(CACHE_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS cve_cache (
              cpe TEXT PRIMARY KEY,
              cves TEXT NOT NULL,
              fetched_at TEXT NOT NULL
           )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS epss_cache (
              cve_id TEXT PRIMARY KEY,
              epss_score REAL,
              epss_percentile REAL,
              fetched_at TEXT NOT NULL
           )"""
    )
    conn.commit()
    conn.close()


_init_cache()


def _epss_cache_get(cve_id: str) -> Optional[Dict]:
    conn = sqlite3.connect(CACHE_PATH)
    try:
        row = conn.execute(
            "SELECT epss_score, epss_percentile, fetched_at FROM epss_cache WHERE cve_id = ?",
            (cve_id,)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    fetched_at = datetime.fromisoformat(row[2])
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    if _utcnow() - fetched_at > timedelta(days=EPSS_TTL_DAYS):
        return None
    return {"epss_score": row[0], "epss_percentile": row[1]}


def _epss_cache_put_batch(entries: List[Dict]) -> None:
    conn = sqlite3.connect(CACHE_PATH)
    now = _utcnow().isoformat()
    try:
        conn.executemany(
            "REPLACE INTO epss_cache (cve_id, epss_score, epss_percentile, fetched_at) VALUES (?,?,?,?)",
            [(e["cve_id"], e["epss_score"], e["epss_percentile"], now) for e in entries]
        )
        conn.commit()
    finally:
        conn.close()


def enrich_with_epss(cves: List[Dict]) -> List[Dict]:
    """Add epss_score and epss_percentile to each CVE dict. Batch API call, cached."""
    if not cves or _OFFLINE_ONLY:
        return cves

    # Split into cached and uncached
    to_fetch: List[str] = []
    cached_scores: Dict[str, Dict] = {}
    for c in cves:
        cid = c.get("cve_id")
        if not cid:
            continue
        hit = _epss_cache_get(cid)
        if hit:
            cached_scores[cid] = hit
        else:
            to_fetch.append(cid)

    # Batch fetch uncached (FIRST API allows up to 100 CVEs per request)
    fetched: Dict[str, Dict] = {}
    for i in range(0, len(to_fetch), 100):
        batch = to_fetch[i:i + 100]
        try:
            resp = requests.get(
                EPSS_API,
                params={"cve": ",".join(batch)},
                headers={"User-Agent": "PentexOne-Scanner/1.0"},
                timeout=HTTP_TIMEOUT,
            )
            if resp.status_code == 200:
                data = resp.json()
                entries = []
                for item in data.get("data", []):
                    cid = item.get("cve")
                    score = float(item.get("epss", 0))
                    pct = float(item.get("percentile", 0)) * 100
                    fetched[cid] = {"epss_score": round(score, 4), "epss_percentile": round(pct, 1)}
                    entries.append({"cve_id": cid, "epss_score": round(score, 4), "epss_percentile": round(pct, 1)})
                if entries:
                    _epss_cache_put_batch(entries)
        except Exception as e:
            logger.debug(f"EPSS fetch failed: {e}")

    # Merge EPSS into CVE dicts
    for c in cves:
        cid = c.get("cve_id")
        if not cid:
            continue
        epss = cached_scores.get(cid) or fetched.get(cid, {})
        c["epss_score"] = epss.get("epss_score")
        c["epss_percentile"] = epss.get("epss_percentile")
        # Convenience flag for UI badge
        c["actively_exploited"] = (epss.get("epss_score") or 0) >= 0.70

    return cves


def _cache_get(cpe: str) -> Optional[List[Dict]]:
    conn = sqlite3.connect(CACHE_PATH)
    try:
        row = conn.execute(
            "SELECT cves, fetched_at FROM cve_cache WHERE cpe = ?", (cpe,)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    fetched_at = datetime.fromisoformat(row[1])
    # Normalise legacy naive timestamps to UTC so comparison is always aware.
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    if _utcnow() - fetched_at > timedelta(days=CACHE_TTL_DAYS):
        return None
    try:
        return json.loads(row[0])
    except json.JSONDecodeError:
        return None


def _cache_put(cpe: str, cves: List[Dict]) -> None:
    conn = sqlite3.connect(CACHE_PATH)
    try:
        conn.execute(
            "REPLACE INTO cve_cache (cpe, cves, fetched_at) VALUES (?, ?, ?)",
            (cpe, json.dumps(cves), _utcnow().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


# ─── CPE normalisation ──────────────────────────────────────────────────
def normalise_cpe(cpe: str) -> Optional[str]:
    """Convert legacy `cpe:/a:vendor:product:version` to CPE 2.3 form."""
    if not cpe:
        return None
    cpe = cpe.strip()
    if cpe.startswith("cpe:2.3:"):
        return cpe
    if cpe.startswith("cpe:/"):
        parts = cpe[5:].split(":")
        while len(parts) < 5:
            parts.append("*")
        kind, vendor, product, version = parts[0], parts[1], parts[2], parts[3]
        return (
            f"cpe:2.3:{kind}:{vendor}:{product}:{version}"
            ":*:*:*:*:*:*:*"
        )
    return None


# ─── Offline NVD feeds ──────────────────────────────────────────────────
# Index shape: { (vendor, product) : [ { ...cve_dict..., "_matches": [...] }, ... ] }
# where each "_matches" entry is a dict with optional version constraints:
#   {"version": "7.2p2"}            exact-version CPE
#   {"version": "*"}                wildcard — applies to all versions
#   {"start_incl": "6.0", "end_excl": "7.4"}  range constraint
_offline_index: Optional[Dict[Tuple[str, str], List[Dict]]] = None
_offline_lock = threading.Lock()


def _parse_version_tuple(v: str) -> Tuple:
    """Convert a version string like '7.2p2' or '2.4.41' to a comparable tuple.
    Non-numeric chunks are kept as strings so '7.2p2' > '7.2'. Good enough for
    the simple range checks NVD ships."""
    if not v or v == "*":
        return ()
    chunks = re.findall(r"\d+|[A-Za-z]+", v)
    out = []
    for c in chunks:
        if c.isdigit():
            out.append((0, int(c)))
        else:
            out.append((1, c.lower()))
    return tuple(out)


def _version_in_range(v: str, m: Dict) -> bool:
    """Return True if version `v` satisfies the CPE-match constraints in `m`."""
    if not v or v == "*":
        return True
    mv = m.get("version")
    if mv and mv != "*":
        return mv == v
    vt = _parse_version_tuple(v)
    if not vt:
        return True
    si = m.get("start_incl"); se = m.get("start_excl")
    ei = m.get("end_incl");   ee = m.get("end_excl")
    if si and vt < _parse_version_tuple(si):
        return False
    if se and vt <= _parse_version_tuple(se):
        return False
    if ei and vt > _parse_version_tuple(ei):
        return False
    if ee and vt >= _parse_version_tuple(ee):
        return False
    return True


def _walk_nodes(nodes, out_matches):
    """Recursively collect cpeMatch entries from NVD configurations nodes."""
    for node in nodes or []:
        # NVD 2.0 uses "cpeMatch"; NVD 1.1 uses "cpe_match".
        for cm in (node.get("cpeMatch") or node.get("cpe_match") or []):
            if not cm.get("vulnerable", True):
                continue
            cpe = cm.get("criteria") or cm.get("cpe23Uri") or ""
            parts = cpe.split(":")
            if len(parts) < 6 or not cpe.startswith("cpe:2.3:"):
                continue
            vendor, product, version = parts[3].lower(), parts[4].lower(), parts[5]
            out_matches.append({
                "vendor": vendor,
                "product": product,
                "version": version,
                "start_incl": cm.get("versionStartIncluding"),
                "start_excl": cm.get("versionStartExcluding"),
                "end_incl":   cm.get("versionEndIncluding"),
                "end_excl":   cm.get("versionEndExcluding"),
            })
        # NVD 1.1 nests further nodes under "children"; recurse.
        if node.get("children"):
            _walk_nodes(node["children"], out_matches)


def _parse_offline_item(item: Dict) -> Optional[Dict]:
    """Parse one CVE record (works for both NVD 1.1 and 2.0 schemas)."""
    cve = item.get("cve", item)
    # ID: 1.1 → cve.CVE_data_meta.ID ; 2.0 → cve.id
    cve_id = (
        cve.get("id")
        or cve.get("CVE_data_meta", {}).get("ID")
    )
    if not cve_id:
        return None

    # Description
    if "descriptions" in cve:  # 2.0
        desc = next((d["value"] for d in cve["descriptions"] if d.get("lang") == "en"), "")
    else:  # 1.1
        dd = cve.get("description", {}).get("description_data", [])
        desc = next((d["value"] for d in dd if d.get("lang") == "en"), "")

    # CVSS
    score, severity = None, "UNKNOWN"
    metrics = cve.get("metrics") or item.get("impact") or {}
    # 2.0 schema
    for k in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        if metrics.get(k):
            cvss = metrics[k][0].get("cvssData", {})
            score = cvss.get("baseScore")
            severity = cvss.get("baseSeverity") or metrics[k][0].get("baseSeverity") or _score_to_severity(score)
            break
    # 1.1 schema
    if score is None:
        if "baseMetricV3" in metrics:
            cvss = metrics["baseMetricV3"].get("cvssV3", {})
            score = cvss.get("baseScore")
            severity = cvss.get("baseSeverity", _score_to_severity(score))
        elif "baseMetricV2" in metrics:
            cvss = metrics["baseMetricV2"].get("cvssV2", {})
            score = cvss.get("baseScore")
            severity = metrics["baseMetricV2"].get("severity", _score_to_severity(score))

    # Configurations (where CPE matches live)
    matches: List[Dict] = []
    configs = item.get("configurations") or cve.get("configurations") or []
    # 2.0 puts configurations as a list at the top of cve; 1.1 wraps in {"nodes": [...]}
    if isinstance(configs, dict):
        _walk_nodes(configs.get("nodes", []), matches)
    elif isinstance(configs, list):
        for cfg in configs:
            _walk_nodes(cfg.get("nodes", []) if isinstance(cfg, dict) else [], matches)

    if not matches:
        return None  # No CPE → can't link to anything.

    return {
        "cve_id": cve_id,
        "description": (desc or "No description.")[:280],
        "cvss_score": score,
        "severity": (severity or "UNKNOWN").upper(),
        "published": cve.get("published") or item.get("publishedDate"),
        "url": f"https://nvd.nist.gov/vuln/detail/{cve_id}",
        "_matches": matches,
    }


def _open_feed(path: str):
    """Yield the parsed JSON from a feed file. Supports .json and .json.gz."""
    if path.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_offline_index() -> Dict[Tuple[str, str], List[Dict]]:
    """Scan OFFLINE_DIR for NVD JSON feeds and build the in-memory index."""
    index: Dict[Tuple[str, str], List[Dict]] = {}
    if not os.path.isdir(OFFLINE_DIR):
        return index
    files = sorted(glob.glob(os.path.join(OFFLINE_DIR, "*.json"))
                   + glob.glob(os.path.join(OFFLINE_DIR, "*.json.gz")))
    if not files:
        return index

    total_cves = 0
    for fpath in files:
        try:
            data = _open_feed(fpath)
        except Exception as e:
            logger.warning(f"Failed to read offline feed {fpath}: {e}")
            continue
        # 1.1: {"CVE_Items": [...]}    2.0 bulk: {"vulnerabilities": [...]}
        items = data.get("CVE_Items") or data.get("vulnerabilities") or []
        for item in items:
            parsed = _parse_offline_item(item)
            if not parsed:
                continue
            total_cves += 1
            # Group by (vendor, product) — one CVE may map to many.
            for m in parsed["_matches"]:
                index.setdefault((m["vendor"], m["product"]), []).append(parsed)

    logger.info(f"Offline NVD index built: {total_cves:,} CVEs across "
                f"{len(index):,} (vendor, product) pairs from {len(files)} file(s)")
    return index


def _get_offline_index() -> Dict[Tuple[str, str], List[Dict]]:
    """Lazy-load the offline index (thread-safe)."""
    global _offline_index
    if _offline_index is not None:
        return _offline_index
    with _offline_lock:
        if _offline_index is None:
            _offline_index = _build_offline_index()
    return _offline_index


def _lookup_offline(cpe23: str) -> Optional[List[Dict]]:
    """Lookup CVEs for a CPE 2.3 string using the offline index.

    Returns:
      - None if the offline index is empty (signals 'no offline data available').
      - [] if the index is present but the (vendor, product) isn't covered.
      - [cve_dict, ...] when matches are found.
    """
    idx = _get_offline_index()
    if not idx:
        return None
    parts = cpe23.split(":")
    if len(parts) < 6:
        return []
    vendor, product, version = parts[3].lower(), parts[4].lower(), parts[5]
    candidates = idx.get((vendor, product), [])
    if not candidates:
        return []

    seen = set()
    matched: List[Dict] = []
    for cve in candidates:
        if cve["cve_id"] in seen:
            continue
        if any(m["vendor"] == vendor and m["product"] == product
               and _version_in_range(version, m)
               for m in cve["_matches"]):
            matched.append({k: v for k, v in cve.items() if not k.startswith("_")})
            seen.add(cve["cve_id"])

    matched.sort(key=lambda f: (f.get("cvss_score") or 0), reverse=True)
    return matched[:MAX_CVES_PER_PRODUCT]


# ─── NVD query ──────────────────────────────────────────────────────────
def _rate_limit() -> None:
    global _last_request_at
    interval = _min_interval()
    with _rate_lock:
        elapsed = time.time() - _last_request_at
        if elapsed < interval:
            time.sleep(interval - elapsed)
        _last_request_at = time.time()


def _query_nvd(cpe23: str) -> List[Dict]:
    params = {"cpeName": cpe23, "resultsPerPage": 20}
    headers = {"User-Agent": "PentexOne-Scanner/1.0"}
    api_key = os.environ.get("NVD_API_KEY")
    if api_key:
        headers["apiKey"] = api_key

    _rate_limit()
    try:
        resp = requests.get(NVD_API, params=params, headers=headers, timeout=HTTP_TIMEOUT)
    except requests.RequestException as e:
        logger.warning(f"NVD query failed for {cpe23}: {e}")
        return []

    if resp.status_code == 403:
        logger.warning("NVD rate-limited — backing off")
        time.sleep(30)
        return []
    if resp.status_code != 200:
        logger.warning(f"NVD returned {resp.status_code} for {cpe23}")
        return []

    data = resp.json()
    findings: List[Dict] = []
    for item in data.get("vulnerabilities", []):
        cve = item.get("cve", {})
        cve_id = cve.get("id")
        if not cve_id:
            continue

        descriptions = cve.get("descriptions", [])
        desc = next(
            (d["value"] for d in descriptions if d.get("lang") == "en"),
            "No description.",
        )

        metrics = cve.get("metrics", {})
        score, sev = None, "UNKNOWN"
        for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            if key in metrics and metrics[key]:
                cvss = metrics[key][0].get("cvssData", {})
                score = cvss.get("baseScore")
                sev = (
                    cvss.get("baseSeverity")
                    or metrics[key][0].get("baseSeverity")
                    or _score_to_severity(score)
                )
                break

        findings.append(
            {
                "cve_id": cve_id,
                "description": desc[:280],
                "cvss_score": score,
                "severity": (sev or "UNKNOWN").upper(),
                "published": cve.get("published"),
                "url": f"https://nvd.nist.gov/vuln/detail/{cve_id}",
            }
        )

    findings.sort(
        key=lambda f: (f.get("cvss_score") or 0),
        reverse=True,
    )
    return findings[:MAX_CVES_PER_PRODUCT]


def _score_to_severity(score: Optional[float]) -> str:
    if score is None:
        return "UNKNOWN"
    if score >= 9.0:
        return "CRITICAL"
    if score >= 7.0:
        return "HIGH"
    if score >= 4.0:
        return "MEDIUM"
    return "LOW"


# ─── Public API ─────────────────────────────────────────────────────────
def lookup_cves_for_cpe(cpe: str) -> List[Dict]:
    """Lookup CVEs for one CPE string.

    Resolution order: SQLite cache → offline NVD index → online NVD API.
    """
    cpe23 = normalise_cpe(cpe)
    if not cpe23:
        return []

    cached = _cache_get(cpe23)
    if cached is not None:
        return cached

    # Try the offline index first — zero-network, sub-millisecond lookup.
    offline = _lookup_offline(cpe23)
    if offline is not None:
        # offline == [] means index exists but no match: trust it and cache.
        _cache_put(cpe23, offline)
        return offline

    # No offline data at all. Fall back to the API unless caller forbade it.
    if _OFFLINE_ONLY:
        logger.debug(f"Offline-only mode: skipping API for {cpe23}")
        return []

    findings = _query_nvd(cpe23)
    _cache_put(cpe23, findings)
    return findings


def lookup_cves_for_ports(
    ports: List[Dict],
    progress_cb: Optional[Callable[[Dict], None]] = None,
) -> Dict[int, List[Dict]]:
    """
    Given Nmap port findings (with `cpes` from nmap_scanner), return
    {port: [cve_dict, ...]} for every port that has at least one CPE.

    progress_cb (optional): called with a dict describing progress, e.g.
        {"stage": "lookup", "current": 2, "total": 7, "cpe": "...", "port": 22}
    so the caller can stream UI updates while the cache/NVD walk runs.
    """
    out: Dict[int, List[Dict]] = {}
    seen_cpes: Dict[str, List[Dict]] = {}

    # Pre-flatten work list so we know the total upfront (for progress %).
    work: List = []  # (port, raw_cpe, key)
    for p in ports:
        for cpe in (p.get("cpes") or []):
            key = normalise_cpe(cpe) or cpe
            work.append((p["port"], cpe, key))

    cap = _lookup_cap()
    total = min(len(work), cap)
    if progress_cb:
        progress_cb({"stage": "lookup_start", "total": total})

    network_calls = 0
    for idx, (port, cpe, key) in enumerate(work):
        if network_calls >= cap and key not in seen_cpes:
            # Stop after the cap, but keep using already-seen results.
            continue
        if key in seen_cpes:
            cves = seen_cpes[key]
        else:
            cves = lookup_cves_for_cpe(cpe)
            seen_cpes[key] = cves
            network_calls += 1
            if progress_cb:
                progress_cb({
                    "stage": "lookup",
                    "current": network_calls,
                    "total": total,
                    "cpe": key,
                    "port": port,
                    "found": len(cves),
                })
        if cves:
            out.setdefault(port, []).extend(cves)

    # Dedupe per port and keep top N.
    for port, cves in list(out.items()):
        uniq: Dict[str, Dict] = {}
        for c in cves:
            uniq.setdefault(c["cve_id"], c)
        out[port] = sorted(
            uniq.values(),
            key=lambda f: (f.get("cvss_score") or 0),
            reverse=True,
        )[:MAX_CVES_PER_PRODUCT]

    if progress_cb:
        progress_cb({"stage": "lookup_done", "total": total})

    return out


if __name__ == "__main__":
    # Quick sanity check
    logging.basicConfig(level=logging.INFO)
    sample = "cpe:/a:openbsd:openssh:7.2p2"
    print(json.dumps(lookup_cves_for_cpe(sample), indent=2))
