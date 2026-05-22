#!/usr/bin/env bash
# Download NVD JSON feeds for offline CVE lookup.
#
# Usage:
#   ./download_nvd_feeds.sh             # download last 6 years (default)
#   ./download_nvd_feeds.sh 2018 2026   # explicit year range
#
# Output goes to backend/nvd_offline/. After running, the scanner will
# use the offline index automatically (no env vars needed). To force
# offline-only mode and skip any API fallback:
#   export PENTEX_NVD_OFFLINE_ONLY=1

set -euo pipefail

# Resolve the offline dir relative to this script.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${SCRIPT_DIR}/../nvd_offline"
mkdir -p "$OUT_DIR"

START_YEAR="${1:-$(($(date +%Y) - 5))}"
END_YEAR="${2:-$(date +%Y)}"

# Primary source: official NIST 1.1 JSON feeds (legacy but still served).
# These URLs do go through Cloudflare. If they fail with 403 / challenge,
# try the alternative mirrors listed below.
NIST_BASE="https://nvd.nist.gov/feeds/json/cve/1.1"

# Alternative mirror, hosted on GitHub Pages — no Cloudflare in the way.
# Each release has yearly JSON files attached.
MIRROR_BASE="https://github.com/fkie-cad/nvd-json-data-feeds/releases/latest/download"

download_with_fallback() {
    local year="$1"
    local fname="nvdcve-1.1-${year}.json.gz"
    local dest="${OUT_DIR}/${fname}"

    echo "[*] ${year}: trying NIST direct..."
    if curl -sSf --max-time 60 -o "${dest}.tmp" "${NIST_BASE}/${fname}"; then
        mv "${dest}.tmp" "$dest"
        echo "    ✓ saved ${fname}"
        return 0
    fi
    rm -f "${dest}.tmp"

    echo "    ✗ NIST blocked, trying GitHub mirror..."
    # Mirror uses *.json (uncompressed) per-year files
    local mfname="CVE-${year}.json"
    local mdest="${OUT_DIR}/${mfname}"
    if curl -sSfL --max-time 120 -o "${mdest}.tmp" "${MIRROR_BASE}/${mfname}"; then
        mv "${mdest}.tmp" "$mdest"
        echo "    ✓ saved ${mfname} (from mirror)"
        return 0
    fi
    rm -f "${mdest}.tmp"

    echo "    ✗ both sources failed for ${year}"
    return 1
}

echo "Downloading NVD feeds → ${OUT_DIR}"
echo "Year range: ${START_YEAR}..${END_YEAR}"
echo

FAIL=0
for year in $(seq "$START_YEAR" "$END_YEAR"); do
    download_with_fallback "$year" || FAIL=$((FAIL + 1))
done

echo
echo "Done. Files in ${OUT_DIR}:"
ls -lh "$OUT_DIR" | tail -n +2

if [[ $FAIL -gt 0 ]]; then
    echo
    echo "⚠ ${FAIL} year(s) failed. Options:"
    echo "  • Try later (Cloudflare challenges are transient)"
    echo "  • Run behind a VPN (Cloudflare WARP works well)"
    echo "  • Manually download from a mirror and place files in ${OUT_DIR}/"
    exit 1
fi

echo
echo "Restart the backend so the offline index loads:"
echo "  systemctl restart pentexone   # or however you run it"
