"""
TN Election 2026 – Live Results Monitor  (Enhanced)
• Search on ALL tabs
• Charts tab: pie + bar + margin distribution (matplotlib embedded)
• Summary canvas bar chart (improved)
• Close Contests, Notable, Party-wise — all searchable
• All Participants tab with candidate photos (SQLite cache)
• PDF Export with photos and Won row highlighting
• Offline Mode: Load from saved JSON files
• Startup mode selection (asks user which mode to use)
• Photo cache: candidateswise-S22{1-234}.htm → tn_election_photos.db
Build EXE: pyinstaller --onefile --windowed tn_election_monitor.py
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import sys
import os
import math
import sqlite3
import hashlib
import io
import json
from collections import Counter

try:
    from PIL import Image as PILImage, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import ttkbootstrap as ttkb
    from ttkbootstrap.constants import *
    BOOTSTRAP = True
except ImportError:
    BOOTSTRAP = False

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.backends.backend_pdf import PdfPages
    import matplotlib.patches as mpatches
    import matplotlib.gridspec as gridspec
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors as rl_colors
    from reportlab.lib.units import cm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                     Paragraph, Spacer, HRFlowable, Image)
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.utils import ImageReader
    HAS_RL = True
except ImportError:
    HAS_RL = False

# ── Constants ────────────────────────────────────────────────────────────────
BASE_URL       = "https://results.eci.gov.in/ResultAcGenMay2026/statewiseS22{}.htm"
PARTY_WISE_URL = "https://results.eci.gov.in/ResultAcGenMay2026/partywiseresult-S22.htm"
PAGES = list(range(1, 13))
REFRESH_INTERVALS = [30, 60, 120, 300]

PARTY_COLORS = {
    "Tamilaga Vettri Kazhagam":                  "#3b82f6",
    "Dravida Munnetra Kazhagam":                  "#22c55e",
    "All India Anna Dravida Munnetra Kazhagam":   "#ef4444",
    "Bharatiya Janata Party":                      "#f97316",
    "Indian National Congress":                    "#6366f1",
    "Pattali Makkal Katchi":                       "#eab308",
    "Viduthalai Chiruthaigal Katchi":              "#10b981",
    "Communist Party of India":                    "#a855f7",
    "Communist Party of India (Marxist)":          "#9333ea",
    "Desiya Murpokku Dravida Kazhagam":            "#f59e0b",
    "Amma Makkal Munnettra Kazagam":               "#64748b",
    "Indian Union Muslim League":                  "#059669",
    "Independent":                                 "#94a3b8",
}
ABBR_COLORS = {
    "TVK":    "#3b82f6",
    "DMK":    "#22c55e",
    "AIADMK": "#ef4444",
    "ADMK":   "#ef4444",
    "BJP":    "#f97316",
    "INC":    "#6366f1",
    "PMK":    "#eab308",
    "VCK":    "#10b981",
    "CPI":    "#a855f7",
    "CPI(M)": "#9333ea",
    "CPI-M":  "#9333ea",
    "DMDK":   "#f59e0b",
    "AMMK":   "#64748b",
    "IUML":   "#059669",
    "IND":    "#94a3b8",
}

PARTY_SHORT = {
    "Tamilaga Vettri Kazhagam":                   "TVK",
    "Dravida Munnetra Kazhagam":                   "DMK",
    "All India Anna Dravida Munnetra Kazhagam":    "AIADMK",
    "Bharatiya Janata Party":                       "BJP",
    "Indian National Congress":                     "INC",
    "Pattali Makkal Katchi":                        "PMK",
    "Viduthalai Chiruthaigal Katchi":               "VCK",
    "Communist Party of India":                     "CPI",
    "Communist Party of India (Marxist)":           "CPI(M)",
    "Desiya Murpokku Dravida Kazhagam":             "DMDK",
    "Amma Makkal Munnettra Kazagam":                "AMMK",
    "Amma Makkal Munnettra Kazagam - AMMKMNKZ":    "AMMK",
    "Indian Union Muslim League":                   "IUML",
    "Independent":                                  "IND",
}

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
MAJORITY_MARK = 118  # Majority in 234-seat assembly


# ── Scraper ───────────────────────────────────────────────────────────────────

# ECI abbreviation -> our abbreviation mapping
_ECI_ABBR_MAP = {
    "ADMK":     "AIADMK",
    "TVK":      "TVK",
    "DMK":      "DMK",
    "INC":      "INC",
    "PMK":      "PMK",
    "BJP":      "BJP",
    "IUML":     "IUML",
    "VCK":      "VCK",
    "CPI":      "CPI",
    "CPI(M)":   "CPI(M)",
    "DMDK":     "DMDK",
    "AMMKMNKZ": "AMMK",
    "AMMK":     "AMMK",
}

PARTY_WISE_URL     = "https://results.eci.gov.in/ResultAcGenMay2026/partywiseresult-S22.htm"
LEAD_URL_TEMPLATE  = "https://results.eci.gov.in/ResultAcGenMay2026/partywiseleadresult-{}S22.htm"
WIN_URL_TEMPLATE   = "https://results.eci.gov.in/ResultAcGenMay2026/partywisewinresult-{}S22.htm"
CONSTWISE_TEMPLATE  = "https://results.eci.gov.in/ResultAcGenMay2026/ConstituencywiseS22{}.htm"
CANDWISE_TEMPLATE   = "https://results.eci.gov.in/ResultAcGenMay2026/candidateswise-S22{}.htm"
PHOTO_BASE_URL      = "https://results.eci.gov.in/ResultAcGenMay2026/"
DB_PATH             = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tn_election_photos.db")
CONFIG_FILE         = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_config.json")


# ── Photo Cache (SQLite) ──────────────────────────────────────────────────────

def _db_connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS photos (
            ac_no       INTEGER,
            cand_name   TEXT,
            img_url     TEXT,
            img_data    BLOB,
            fetched_at  TEXT,
            PRIMARY KEY (ac_no, cand_name)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS photo_meta (
            ac_no       INTEGER PRIMARY KEY,
            scraped_at  TEXT
        )
    """)
    conn.commit()
    return conn


_db_lock = threading.Lock()
_db_conn = None


def get_db():
    global _db_conn
    if _db_conn is None:
        _db_conn = _db_connect()
    return _db_conn


def db_get_photo(ac_no: int, cand_name: str):
    """Return (img_url, img_data_bytes) or (None, None) if not cached."""
    with _db_lock:
        try:
            row = get_db().execute(
                "SELECT img_url, img_data FROM photos WHERE ac_no=? AND cand_name=?",
                (ac_no, cand_name)
            ).fetchone()
            return (row[0], row[1]) if row else (None, None)
        except Exception:
            return (None, None)


def db_save_photo(ac_no: int, cand_name: str, img_url: str, img_data: bytes):
    with _db_lock:
        try:
            get_db().execute(
                "INSERT OR REPLACE INTO photos (ac_no, cand_name, img_url, img_data, fetched_at) "
                "VALUES (?, ?, ?, ?, datetime('now'))",
                (ac_no, cand_name, img_url, img_data)
            )
            get_db().commit()
        except Exception:
            pass


def db_ac_scraped(ac_no: int) -> bool:
    """True if this AC's photo page has already been scraped (even if no photos found)."""
    with _db_lock:
        try:
            row = get_db().execute(
                "SELECT 1 FROM photo_meta WHERE ac_no=?", (ac_no,)
            ).fetchone()
            return row is not None
        except Exception:
            return False


def db_mark_ac_scraped(ac_no: int):
    with _db_lock:
        try:
            get_db().execute(
                "INSERT OR REPLACE INTO photo_meta (ac_no, scraped_at) VALUES (?, datetime('now'))",
                (ac_no,)
            )
            get_db().commit()
        except Exception:
            pass


def db_photo_stats() -> dict:
    """Return {total_acs_scraped, total_photos, total_with_image}."""
    with _db_lock:
        try:
            db = get_db()
            acs    = db.execute("SELECT COUNT(*) FROM photo_meta").fetchone()[0]
            total  = db.execute("SELECT COUNT(*) FROM photos").fetchone()[0]
            with_img = db.execute(
                "SELECT COUNT(*) FROM photos WHERE img_data IS NOT NULL"
            ).fetchone()[0]
            return {"acs": acs, "total": total, "with_img": with_img}
        except Exception:
            return {"acs": 0, "total": 0, "with_img": 0}


def scrape_photo_page(ac_no: int) -> list:
    """Fetch candidateswise-S22{ac_no}.htm and return list of candidate photo info."""
    if db_ac_scraped(ac_no):
        return []

    url = CANDWISE_TEMPLATE.format(ac_no)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        db_mark_ac_scraped(ac_no)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []

    cand_boxes = soup.find_all("div", class_="cand-box")
    
    for box in cand_boxes:
        name_elem = box.select_one(".nme-prty h5")
        if not name_elem:
            name_elem = box.find("h5")
        
        cand_name = name_elem.get_text(strip=True) if name_elem else None
        
        if not cand_name or cand_name.upper() == "NOTA":
            continue
        
        figure = box.find("figure")
        img_url = None
        if figure:
            img = figure.find("img")
            if img and img.get("src"):
                src = img["src"].strip()
                if src.startswith("http"):
                    img_url = src
                elif src.startswith("/"):
                    img_url = "https://results.eci.gov.in" + src
                else:
                    img_url = "https://results.eci.gov.in/" + src.lstrip("/")
        
        if img_url and "nota.jpg" in img_url.lower():
            continue
        
        results.append({
            "ac_no": ac_no,
            "cand_name": cand_name,
            "img_url": img_url
        })
    
    db_mark_ac_scraped(ac_no)
    return results


def download_and_cache_photo(ac_no: int, cand_name: str, img_url: str) -> bool:
    """Download image bytes and store in DB. Returns True on success."""
    if not img_url:
        db_save_photo(ac_no, cand_name, "", None)
        return False
    _, existing = db_get_photo(ac_no, cand_name)
    if existing is not None:
        return True
    try:
        r = requests.get(img_url, headers=HEADERS, timeout=12)
        r.raise_for_status()
        img_data = r.content
        if HAS_PIL:
            PILImage.open(io.BytesIO(img_data)).verify()
        db_save_photo(ac_no, cand_name, img_url, img_data)
        return True
    except Exception:
        db_save_photo(ac_no, cand_name, img_url or "", None)
        return False


def fetch_photos_for_ac_list(ac_list: list, progress_cb=None, stop_event=None) -> dict:
    """Full pipeline: scrape photo pages then download images for all ACs."""
    import concurrent.futures

    todo_acs = [ac for ac in ac_list if not db_ac_scraped(ac)]
    total_acs = len(todo_acs)

    if progress_cb:
        progress_cb(0, max(total_acs, 1), f"Scraping photo pages… ({total_acs} ACs)")

    all_entries = []
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as ex:
        futs = {ex.submit(scrape_photo_page, ac): ac for ac in todo_acs}
        for fut in concurrent.futures.as_completed(futs):
            if stop_event and stop_event.is_set():
                break
            try:
                all_entries.extend(fut.result())
            except Exception:
                pass
            done += 1
            if progress_cb:
                progress_cb(done, max(total_acs, 1), f"Scraped {done}/{total_acs} pages…")

    to_download = [(e["ac_no"], e["cand_name"], e["img_url"]) for e in all_entries if e.get("img_url")]
    no_img = [(e["ac_no"], e["cand_name"], None) for e in all_entries if not e.get("img_url")]
    for ac_no, cand_name, _ in no_img:
        db_save_photo(ac_no, cand_name, "", None)

    total_dl = len(to_download)
    if progress_cb:
        progress_cb(0, max(total_dl, 1), f"Downloading {total_dl} photos…")

    done_dl = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
        futs2 = {ex.submit(download_and_cache_photo, ac, cn, url): (ac, cn) for ac, cn, url in to_download}
        for fut in concurrent.futures.as_completed(futs2):
            if stop_event and stop_event.is_set():
                break
            done_dl += 1
            if progress_cb and done_dl % 10 == 0:
                progress_cb(done_dl, max(total_dl, 1), f"Downloaded {done_dl}/{total_dl} photos…")

    if progress_cb:
        stats = db_photo_stats()
        progress_cb(total_dl, max(total_dl, 1), f"Done — {stats['with_img']} photos cached in DB")


def short(party_full: str) -> str:
    return PARTY_SHORT.get(party_full, party_full[:8] if party_full else "—")


def _int(text: str) -> int:
    try:
        return int(text.strip().replace(",", ""))
    except (ValueError, AttributeError):
        return -1


def _parse_constituency_link(cell_text: str):
    m = re.match(r"^(.*?)\((\d+)\)\s*$", cell_text.strip())
    if m:
        return m.group(1).strip(), int(m.group(2))
    return cell_text.strip(), 0


def scrape_party_index() -> list:
    """Fetch the ECI party-wise summary page."""
    try:
        resp = requests.get(PARTY_WISE_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    result = []

    for table in soup.find_all("table"):
        headers = [c.get_text(strip=True).lower() for c in (table.find_all("th") or table.find("tr").find_all("td"))]
        if "won" not in headers or "leading" not in headers:
            continue

        for tr in table.find_all("tr")[1:]:
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue
            party_raw = tds[0].get_text(strip=True)
            if not party_raw or party_raw.lower() == "total":
                continue

            if " - " in party_raw:
                full_name = party_raw.split(" - ")[0].strip()
                abbr_raw = party_raw.split(" - ")[-1].strip()
            else:
                full_name = party_raw
                abbr_raw = party_raw
            abbr = _ECI_ABBR_MAP.get(abbr_raw, abbr_raw)

            won_cell = tds[1]
            lead_cell = tds[2]

            won_count = _int(won_cell.get_text())
            leading_count = _int(lead_cell.get_text())
            total_count = _int(tds[3].get_text()) if len(tds) > 3 else (won_count + leading_count)

            lead_id = None
            win_id = None
            for a in lead_cell.find_all("a", href=True):
                m = re.search(r"partywiseleadresult-(\w+)S22", a["href"])
                if m:
                    lead_id = m.group(1)
            for a in won_cell.find_all("a", href=True):
                m = re.search(r"partywisewinresult-(\w+)S22", a["href"])
                if m:
                    win_id = m.group(1)

            color = PARTY_COLORS.get(full_name, ABBR_COLORS.get(abbr, "#6b7280"))
            result.append({
                "abbr": abbr, "full": full_name, "won": won_count,
                "leading": leading_count, "total": total_count, "trailing": 0,
                "color": color, "lead_id": lead_id, "win_id": win_id,
            })
        break
    return result


def _scrape_lead_or_win_page(url: str, party_full: str, status: str) -> list:
    """Scrape a partywiseleadresult or partywisewinresult page."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    last_updated = ""
    for txt in soup.stripped_strings:
        if "Last Updated" in txt:
            last_updated = txt.strip()
            break

    table = soup.find("table")
    if not table:
        return []

    rows = []
    for tr in table.find_all("tr")[1:]:
        tds = tr.find_all("td")
        if len(tds) < 5:
            continue

        const_cell = tds[1].get_text(strip=True)
        const_name, const_no = _parse_constituency_link(const_cell)
        if not const_name or const_no == 0:
            a = tds[1].find("a", href=True)
            if a:
                m = re.search(r"candidateswise-S22(\d+)", a.get("href", ""))
                if m:
                    const_no = int(m.group(1))
            if const_no == 0:
                continue

        lead_cand = tds[2].get_text(strip=True)
        total_votes = _int(tds[3].get_text())
        margin = _int(tds[4].get_text())
        round_info = tds[5].get_text(strip=True) if len(tds) > 5 else ""

        rows.append({
            "constituency": const_name, "no": const_no, "lead_cand": lead_cand,
            "lead_party": party_full, "lead_short": short(party_full),
            "trail_cand": "", "trail_party": "", "trail_short": "—",
            "total_votes": total_votes, "margin": margin, "round": round_info, "status": status,
        })
    return rows, last_updated


def _scrape_constwise(ac_no: int) -> dict:
    """Fetch ConstituencywiseS22{ac}.htm and return the 2nd-place candidate info."""
    url = CONSTWISE_TEMPLATE.format(ac_no)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except Exception:
        return {}

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if not table:
        return {}

    candidates = []
    for tr in table.find_all("tr")[1:]:
        tds = tr.find_all("td")
        if len(tds) < 6:
            continue
        name = tds[1].get_text(strip=True)
        party = tds[2].get_text(strip=True)
        votes = _int(tds[5].get_text())
        if name.lower() in ("total", "nota", "") or not name:
            continue
        if votes >= 0:
            candidates.append((votes, name, party))

    if len(candidates) < 2:
        return {}

    candidates.sort(reverse=True)
    _, trail_cand, trail_party = candidates[1]
    return {"trail_cand": trail_cand, "trail_party": trail_party, "trail_short": short(trail_party)}


def scrape_all_candidates(constituency_list: list) -> list:
    """Fetch all candidates for all constituencies."""
    winner_map = {c["no"]: c for c in constituency_list}
    all_cands = []

    def _fetch_one(ac_no):
        url = CONSTWISE_TEMPLATE.format(ac_no)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=12)
            resp.raise_for_status()
        except Exception:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table")
        if not table:
            return []

        win_info = winner_map.get(ac_no, {})
        const_name = win_info.get("constituency", f"AC #{ac_no}")
        win_status = win_info.get("status", "")

        rows = []
        for tr in table.find_all("tr")[1:]:
            tds = tr.find_all("td")
            if len(tds) < 5:
                continue
            name = tds[1].get_text(strip=True) if len(tds) > 1 else ""
            party = tds[2].get_text(strip=True) if len(tds) > 2 else ""
            evm = _int(tds[3].get_text()) if len(tds) > 3 else -1
            post = _int(tds[4].get_text()) if len(tds) > 4 else -1
            total = _int(tds[5].get_text()) if len(tds) > 5 else -1
            pct_str = tds[6].get_text(strip=True) if len(tds) > 6 else ""

            if not name:
                continue

            is_nota = name.upper() == "NOTA"
            party_short_val = "NOTA" if is_nota else short(party)

            rows.append({
                "no": ac_no, "constituency": const_name, "candidate": name,
                "party": party if not is_nota else "NOTA", "party_short": party_short_val,
                "evm_votes": evm, "postal_votes": post, "total_votes": total,
                "vote_pct": pct_str, "is_nota": is_nota,
            })

        if not rows:
            return []

        valid = [(r["total_votes"], i, r) for i, r in enumerate(rows) if r["total_votes"] >= 0]
        valid.sort(key=lambda x: x[0], reverse=True)
        nota_rows = [r for r in rows if r["is_nota"]]
        ranked_rows = [r for _, _, r in valid]

        for rank, r in enumerate(ranked_rows, start=1):
            r["rank"] = rank
            r["result"] = "Won" if (rank == 1 and win_status == "Won") else ("Leading" if rank == 1 else "Trailing")

        for r in nota_rows:
            if "rank" not in r:
                r["rank"] = len(ranked_rows) + 1
                r["result"] = "NOTA"

        return rows

    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
        futures = {ex.submit(_fetch_one, c["no"]): c["no"] for c in constituency_list}
        for f in concurrent.futures.as_completed(futures):
            all_cands.extend(f.result())

    return all_cands


def scrape_all():
    """Main scrape: fetch party index, then all lead + win pages per party."""
    party_index = scrape_party_index()
    last_updated = ""
    all_rows = {}

    eci_party = {}
    for p in party_index:
        abbr = p["abbr"]
        color = p["color"]
        full = p["full"]
        eci_party[abbr] = {
            "abbr": abbr, "full": full, "won": p["won"],
            "leading": p["leading"], "total": p["total"], "trailing": 0, "color": color,
        }

    for p in party_index:
        if p["lead_id"] and p["leading"] > 0:
            url = LEAD_URL_TEMPLATE.format(p["lead_id"])
            result = _scrape_lead_or_win_page(url, p["full"], "In Progress")
            if isinstance(result, tuple):
                rows, upd = result
                if upd and not last_updated:
                    last_updated = upd
                for r in rows:
                    if r["no"] not in all_rows:
                        all_rows[r["no"]] = r

        if p["win_id"] and p["won"] > 0:
            url = WIN_URL_TEMPLATE.format(p["win_id"])
            result = _scrape_lead_or_win_page(url, p["full"], "Won")
            if isinstance(result, tuple):
                rows, upd = result
                if upd and not last_updated:
                    last_updated = upd
                for r in rows:
                    if r["no"] not in all_rows:
                        all_rows[r["no"]] = r
                    else:
                        all_rows[r["no"]]["status"] = "Won"
                        all_rows[r["no"]]["margin"] = r["margin"]
                        all_rows[r["no"]]["round"] = r["round"]
                        all_rows[r["no"]]["total_votes"] = r["total_votes"]

    def _enrich(ac_no, row):
        trail = _scrape_constwise(ac_no)
        if trail:
            row.update(trail)

    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
        futures = {ex.submit(_enrich, ac, row): ac for ac, row in all_rows.items()}
        for f in concurrent.futures.as_completed(futures):
            pass

    trail_cnt = Counter(r.get("trail_short", "—") for r in all_rows.values())
    for abbr, cnt in trail_cnt.items():
        if abbr in eci_party:
            eci_party[abbr]["trailing"] = cnt

    return list(all_rows.values()), last_updated, eci_party


# ── Helper: search entry with clear button ────────────────────────────────────

def make_search_entry(parent, var, callback, bg="white"):
    """Returns a frame containing a search box wired to var + callback."""
    frame = tk.Frame(parent, bg=bg)
    tk.Label(frame, text="🔍 Search:", bg=bg, font=("Segoe UI", 9)).pack(side="left")
    e = tk.Entry(frame, textvariable=var, width=26, font=("Segoe UI", 9))
    e.pack(side="left", padx=4)
    clr = tk.Button(frame, text="✕", font=("Segoe UI", 7), relief="flat",
                    bg="#e2e8f0", cursor="hand2", padx=3,
                    command=lambda: (var.set(""), callback()))
    clr.pack(side="left")
    var.trace_add("write", lambda *_: callback())
    return frame


# ── Main App ──────────────────────────────────────────────────────────────────

class TNElectionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TN Election 2026 — Live Results Monitor")
        self.root.geometry("1360x860")
        self.root.minsize(960, 640)

        self.data: list = []
        self.last_updated: str = ""
        self.auto_refresh = tk.BooleanVar(value=True)
        self.refresh_interval = tk.IntVar(value=60)
        self.status_var = tk.StringVar(value="Ready. Select mode to load data.")
        self.offline_mode = tk.BooleanVar(value=False)

        self.search_var = tk.StringVar()
        self.close_search_var = tk.StringVar()
        self.notable_search_var = tk.StringVar()
        self.party_search_var = tk.StringVar()

        self.party_filter = tk.StringVar(value="All")
        self.margin_filter = tk.StringVar(value="All")

        self.participants_search_var = tk.StringVar()
        self.participants_party_var = tk.StringVar(value="All")
        self.participants_assembly_var = tk.StringVar(value="All")
        self.participants_status_var = tk.StringVar(value="All")
        self._participants_data: list = []
        self._part_sort_col = "Votes"
        self._part_sort_rev = True

        self._photo_cache: dict = {}
        self._photo_stop = threading.Event()
        self._photo_job_running = False
        self._photo_status_var = tk.StringVar(value="")
        self.sort_col = "no"
        self.sort_rev = False
        self._refresh_job = None
        self._countdown_job = None
        self._countdown_remaining = 0
        self._loading = False
        self._party_sort_col = "Total"
        self._party_sort_rev = True
        self._mpl_canvases = {}
        self._mpl_figures = {}
        self._charts_ready = False
        self._stats_ready = False
        self.eci_party = {}

        self._build_ui()
        
        # Check for existing JSON data and offer offline mode
        self.root.after(500, self._check_offline_data_on_startup)
    
    def _save_mode_preference(self):
        """Save the user's mode preference to a config file"""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump({"offline_mode": self.offline_mode.get()}, f)
        except:
            pass
    
    def _load_mode_preference(self):
        """Load saved mode preference"""
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                return config.get("offline_mode", False)
        except:
            return False
    
    def _check_offline_data_on_startup(self):
        """Check if offline data exists and ask user which mode to use"""
        # Check if JSON files exist
        script_dir = os.path.dirname(os.path.abspath(__file__))
        json_locations = [
            os.path.join(script_dir, "election_data", "election_data_compact.json"),
            os.path.join(script_dir, "election_data_compact.json"),
            "election_data_compact.json",
        ]
        
        json_exists = any(os.path.exists(loc) for loc in json_locations)
        
        # Load saved preference
        saved_preference = self._load_mode_preference()
        
        if json_exists:
            # If user previously chose offline mode, use it without asking
            if saved_preference:
                self.offline_mode.set(True)
                if hasattr(self, "offline_toggle"):
                    self.offline_toggle.select()
                self.refresh_data_offline()
            else:
                # Ask user which mode to use
                result = messagebox.askyesno(
                    "Choose Data Source",
                    "Offline data (JSON) found!\n\n"
                    "Do you want to use OFFLINE mode?\n"
                    "• YES - Load from saved JSON (faster, no internet needed)\n"
                    "• NO - Fetch live data from ECI website\n\n"
                    "You can switch modes anytime using the checkbox in toolbar.\n"
                    "Your preference will be saved for next launch."
                )
                
                if result:
                    # User wants offline mode
                    self.offline_mode.set(True)
                    if hasattr(self, "offline_toggle"):
                        self.offline_toggle.select()
                    self.refresh_data_offline()
                else:
                    # User wants live mode
                    self.offline_mode.set(False)
                    if hasattr(self, "offline_toggle"):
                        self.offline_toggle.deselect()
                    self.refresh_data()
                
                # Save preference
                self._save_mode_preference()
        else:
            # No JSON found, use live mode
            self.status_var.set("No offline data found. Fetching live data from ECI...")
            self.refresh_data()

    def _build_ui(self):
        hdr = tk.Frame(self.root, bg="#1e3a5f", pady=8)
        hdr.pack(fill="x")
        tk.Label(hdr, text="🗳  Tamil Nadu Assembly Election 2026 — Live Results Monitor",
                 bg="#1e3a5f", fg="white", font=("Segoe UI", 14, "bold")).pack(side="left", padx=16)
        self.status_lbl = tk.Label(hdr, textvariable=self.status_var,
                                   bg="#1e3a5f", fg="#93c5fd", font=("Segoe UI", 9))
        self.status_lbl.pack(side="right", padx=16)

        self.toolbar = tk.Frame(self.root, bg="#f1f5f9", pady=6, padx=10, relief="flat", bd=0)
        self.toolbar.pack(fill="x")

        tk.Button(self.toolbar, text="⟳  Refresh Now", command=self.refresh_data,
                  bg="#2563eb", fg="white", relief="flat", padx=12, pady=4,
                  font=("Segoe UI", 9, "bold"), cursor="hand2",
                  activebackground="#1d4ed8").pack(side="left", padx=(0, 8))

        tk.Label(self.toolbar, text="Auto-refresh:", bg="#f1f5f9", font=("Segoe UI", 9)).pack(side="left")
        tk.Checkbutton(self.toolbar, variable=self.auto_refresh, bg="#f1f5f9",
                       command=self._schedule_refresh).pack(side="left")

        tk.Label(self.toolbar, text="Every:", bg="#f1f5f9", font=("Segoe UI", 9)).pack(side="left", padx=(4, 2))
        iv_cb = ttk.Combobox(self.toolbar, textvariable=self.refresh_interval,
                             values=REFRESH_INTERVALS, width=5, state="readonly")
        iv_cb.pack(side="left")
        tk.Label(self.toolbar, text="sec", bg="#f1f5f9", font=("Segoe UI", 9)).pack(side="left", padx=(2, 16))

        # Offline mode toggle
        self.offline_toggle = tk.Checkbutton(
            self.toolbar, 
            text="📁 Offline Mode (Use JSON)", 
            variable=self.offline_mode,
            bg="#f1f5f9",
            font=("Segoe UI", 9),
            command=self.toggle_offline_mode
        )
        self.offline_toggle.pack(side="left", padx=(16, 8))
        
        # Status indicator for current mode
        self.offline_status_lbl = tk.Label(
            self.toolbar, 
            text="", 
            bg="#f1f5f9", 
            font=("Segoe UI", 8, "bold"),
            width=12
        )
        self.offline_status_lbl.pack(side="left", padx=(5, 0))

        self.progress = ttk.Progressbar(self.root, mode="indeterminate", length=200)

        tk.Button(self.toolbar, text="📄  Export PDF", command=self._export_pdf_current_tab,
                  bg="#059669", fg="white", relief="flat", padx=12, pady=4,
                  font=("Segoe UI", 9, "bold"), cursor="hand2",
                  activebackground="#047857").pack(side="right", padx=(8, 4))

        self._photo_btn = tk.Button(
            self.toolbar, text="📷  Fetch Photos", command=self._start_photo_fetch,
            bg="#7c3aed", fg="white", relief="flat", padx=12, pady=4,
            font=("Segoe UI", 9, "bold"), cursor="hand2",
            activebackground="#6d28d9")
        self._photo_btn.pack(side="right", padx=(0, 4))

        self._photo_status_lbl = tk.Label(
            self.toolbar, textvariable=self._photo_status_var,
            bg="#f1f5f9", fg="#7c3aed", font=("Segoe UI", 8))
        self._photo_status_lbl.pack(side="right", padx=(0, 8))

        self.root.after(800, self._refresh_photo_status)

        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self._nb = nb

        self.tab_summary = tk.Frame(nb, bg="white")
        self.tab_charts = tk.Frame(nb, bg="white")
        self.tab_stats = tk.Frame(nb, bg="white")
        self.tab_party = tk.Frame(nb, bg="white")
        self.tab_table = tk.Frame(nb, bg="white")
        self.tab_close = tk.Frame(nb, bg="white")
        self.tab_notable = tk.Frame(nb, bg="white")
        self.tab_participants = tk.Frame(nb, bg="white")

        nb.add(self.tab_summary, text="  📊 Summary  ")
        nb.add(self.tab_charts, text="  📈 Charts  ")
        nb.add(self.tab_stats, text="  🔬 Stats  ")
        nb.add(self.tab_party, text="  🏛 Party-wise  ")
        nb.add(self.tab_table, text="  📋 All Constituencies  ")
        nb.add(self.tab_close, text="  ⚔ Close Contests  ")
        nb.add(self.tab_notable, text="  ⭐ Notable  ")
        nb.add(self.tab_participants, text="  👥 All Participants  ")

        self._build_summary_tab()
        self._build_charts_tab()
        self._build_stats_tab()
        self._build_party_tab()
        self._build_table_tab()
        self._build_close_tab()
        self._build_notable_tab()
        self._build_participants_tab()

    def toggle_offline_mode(self):
        """Toggle between live and offline mode."""
        if self._loading:
            return
        
        if self.offline_mode.get():
            self.refresh_data_offline()
        else:
            self.refresh_data()
        
        # Save preference
        self._save_mode_preference()

    def load_from_json(self, json_file_path=None):
        """Load election data from JSON file instead of live scraping."""
        if json_file_path is None:
            # Look for JSON files in default location
            script_dir = os.path.dirname(os.path.abspath(__file__))
            json_locations = [
                os.path.join(script_dir, "election_data", "election_data_compact.json"),
                os.path.join(script_dir, "election_data_compact.json"),
                os.path.join(script_dir, "election_data", "complete_election_data.json"),
                "election_data_compact.json",
                "election_data/complete_election_data.json",
            ]
            
            json_file = None
            for loc in json_locations:
                if os.path.exists(loc):
                    json_file = loc
                    break
            
            if json_file is None:
                return False
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Convert JSON data to the format expected by the application
            constituencies = []
            
            for const in data.get("constituencies", []):
                # Find trailing candidate (2nd place)
                candidates = const.get("candidates", [])
                sorted_candidates = sorted(candidates, key=lambda x: x.get("total_votes", 0), reverse=True)
                
                trail_cand = sorted_candidates[1] if len(sorted_candidates) > 1 else None
                
                constituency_data = {
                    "no": const.get("no"),
                    "constituency": const.get("constituency"),
                    "lead_cand": const.get("lead_cand"),
                    "lead_party": const.get("lead_party"),
                    "lead_short": const.get("lead_short"),
                    "trail_cand": trail_cand.get("name") if trail_cand else "",
                    "trail_party": trail_cand.get("party") if trail_cand else "",
                    "trail_short": trail_cand.get("party_short") if trail_cand else "—",
                    "total_votes": const.get("total_votes", 0),
                    "margin": const.get("margin", 0),
                    "round": const.get("round", ""),
                    "status": const.get("status", ""),
                }
                constituencies.append(constituency_data)
            
            # Get party totals
            eci_party = {}
            for abbr, info in data.get("party_totals", {}).items():
                eci_party[abbr] = {
                    "abbr": abbr,
                    "full": info.get("full", abbr),
                    "won": info.get("won", 0),
                    "leading": info.get("leading", 0),
                    "total": info.get("total", 0),
                    "trailing": 0,
                    "color": info.get("color", "#6b7280")
                }
            
            # Calculate trailing counts
            trail_cnt = Counter(c.get("trail_short", "—") for c in constituencies)
            for abbr, cnt in trail_cnt.items():
                if abbr in eci_party:
                    eci_party[abbr]["trailing"] = cnt
            
            # Store participants data if available
            participants_data = []
            for const in data.get("constituencies", []):
                for candidate in const.get("candidates", []):
                    participants_data.append({
                        "no": const.get("no"),
                        "constituency": const.get("constituency"),
                        "candidate": candidate.get("name"),
                        "party": candidate.get("party"),
                        "party_short": candidate.get("party_short"),
                        "evm_votes": candidate.get("evm_votes", 0),
                        "postal_votes": candidate.get("postal_votes", 0),
                        "total_votes": candidate.get("total_votes", 0),
                        "vote_pct": candidate.get("vote_percentage", ""),
                        "rank": 0,
                        "result": "",
                    })
            
            # Calculate ranks and results for participants
            for const_no in set(p["no"] for p in participants_data):
                const_candidates = [p for p in participants_data if p["no"] == const_no]
                sorted_cands = sorted(const_candidates, key=lambda x: x["total_votes"], reverse=True)
                for rank, cand in enumerate(sorted_cands, 1):
                    cand["rank"] = rank
                    if rank == 1:
                        const_data = next((c for c in constituencies if c["no"] == const_no), {})
                        cand["result"] = "Won" if const_data.get("status") == "Won" else "Leading"
                    else:
                        cand["result"] = "Trailing"
            
            self.data = constituencies
            self.eci_party = eci_party
            self._participants_data = participants_data
            self.last_updated = data.get("metadata", {}).get("last_updated", "From saved data")
            
            return True
            
        except Exception as e:
            print(f"Error loading JSON: {e}")
            return False

    def refresh_data_offline(self):
        """Load data from JSON file instead of live scraping."""
        if self._loading:
            return
        
        # Cancel any scheduled refresh jobs
        if self._refresh_job:
            self.root.after_cancel(self._refresh_job)
            self._refresh_job = None
        
        self._loading = True
        self.status_var.set("📁 Loading data from saved JSON file...")
        self.progress.pack(fill="x", padx=8, pady=2)
        self.progress.start(10)
        
        def _load_thread():
            success = self.load_from_json()
            self.root.after(0, self._on_offline_data_ready, success)
        
        threading.Thread(target=_load_thread, daemon=True).start()

    def _on_offline_data_ready(self, success):
        """Handle offline data loading completion."""
        self._loading = False
        self.progress.stop()
        self.progress.pack_forget()
        
        if success:
            now = datetime.now().strftime("%H:%M:%S")
            self.status_var.set(f"✓ {len(self.data)} constituencies loaded from JSON  |  Loaded at: {now}")
            
            self._refresh_summary()
            self._refresh_charts_tab()
            self._refresh_stats_tab()
            self._refresh_party_tab()
            self.apply_filters()
            self._refresh_close_tab()
            self._refresh_notable_tab()
            self._refresh_participants_tab()
            
            self._refresh_photo_status()
            
            # Disable auto-refresh in offline mode
            self.auto_refresh.set(False)
            
            # Update offline status indicator
            self.offline_status_lbl.config(text="📁 OFFLINE", fg="#059669")
        else:
            self.status_var.set("⚠ Could not load JSON data. Switching to live mode...")
            self.offline_mode.set(False)
            self.offline_toggle.deselect()
            # Fall back to live mode
            self.refresh_data()
        
        self._schedule_refresh()

    def _build_summary_tab(self):
        f = self.tab_summary
        sc = tk.Canvas(f, bg="white", highlightthickness=0)
        vsb = ttk.Scrollbar(f, orient="vertical", command=sc.yview)
        hsb = ttk.Scrollbar(f, orient="horizontal", command=sc.xview)
        sc.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        hsb.pack(side="bottom", fill="x")
        vsb.pack(side="right", fill="y")
        sc.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(sc, bg="white")
        win_id = sc.create_window((0, 0), window=inner, anchor="nw")

        def _cfg(e): sc.configure(scrollregion=sc.bbox("all"))
        def _resize(e): sc.itemconfig(win_id, width=e.width)
        inner.bind("<Configure>", _cfg)
        sc.bind("<Configure>", _resize)

        def _mw(e): sc.yview_scroll(int(-1*(e.delta/120)), "units")
        sc.bind_all("<MouseWheel>", _mw)

        tk.Label(inner, text="Overall Snapshot", font=("Segoe UI", 12, "bold"),
                 bg="white", fg="#1e3a5f").pack(pady=(16, 8))

        self.metric_frame = tk.Frame(inner, bg="white")
        self.metric_frame.pack(pady=4, padx=20, fill="x")

        tk.Label(inner, text="Party-wise Seat Tally (Leading + Won)",
                 font=("Segoe UI", 10, "bold"), bg="white", fg="#334155").pack(pady=(16, 4))
        self.summary_canvas = tk.Canvas(inner, bg="white", highlightthickness=0, height=420)
        self.summary_canvas.pack(fill="x", padx=20, pady=(0, 12))

    def _build_metric_card(self, parent, row, col, title, value, color="#2563eb"):
        card = tk.Frame(parent, bg=color, padx=16, pady=10, relief="flat")
        card.grid(row=row, column=col, padx=6, pady=4, sticky="ew")
        parent.columnconfigure(col, weight=1)
        tk.Label(card, text=title, bg=color, fg="white", font=("Segoe UI", 8)).pack()
        tk.Label(card, text=value, bg=color, fg="white", font=("Segoe UI", 20, "bold")).pack()

    def _refresh_summary(self):
        for w in self.metric_frame.winfo_children():
            w.destroy()

        total = 234
        with_data = len(self.data)
        pt = self._get_party_totals()
        tvk = pt.get("TVK", {})
        dmk = pt.get("DMK", {})
        aiadmk = pt.get("AIADMK", {})
        declared = sum(1 for d in self.data if d["status"] == "Won")

        metrics = [
            ("Total Seats", str(total), "#1e3a5f"), ("With Data", str(with_data), "#0f766e"),
            ("Majority Mark", str(MAJORITY_MARK), "#374151"), ("TVK Lead+Won", str(tvk.get("total", 0)), "#2563eb"),
            ("DMK Lead+Won", str(dmk.get("total", 0)), "#16a34a"), ("AIADMK Lead+Won", str(aiadmk.get("total", 0)), "#dc2626"),
            ("Results Declared", str(declared), "#7c3aed"), ("In Progress", str(with_data - declared), "#d97706"),
        ]
        for i, (title, val, col) in enumerate(metrics):
            self._build_metric_card(self.metric_frame, 0, i, title, val, col)

        def _draw_summary_bars():
            c = self.summary_canvas
            c.delete("all")
            if not pt:
                c.create_text(300, 100, text="No data loaded yet", fill="#94a3b8", font=("Segoe UI", 11))
                return

            sorted_parties = sorted(pt.items(), key=lambda x: x[1]["total"], reverse=True)
            sorted_parties = [(a, v) for a, v in sorted_parties if v["total"] > 0]
            if not sorted_parties:
                return

            max_seats = max(v["total"] for _, v in sorted_parties)
            max_seats = max(max_seats, 1)

            BAR_H = 28
            GAP = 8
            LEFT = 90
            RIGHT_PAD = 160
            TOP = 30

            c.update_idletasks()
            canvas_w = c.winfo_width()
            if canvas_w < 200:
                canvas_w = 900

            needed_h = TOP + len(sorted_parties) * (BAR_H + GAP) + 50
            c.config(height=max(needed_h, 300))

            bar_max_w = canvas_w - LEFT - RIGHT_PAD
            mid_x = LEFT + bar_max_w // 2
            c.create_text(LEFT, TOP - 16, text="0", anchor="center", fill="#64748b", font=("Segoe UI", 8))
            c.create_text(mid_x, TOP - 16, text=str(max_seats // 2), anchor="center",
                          fill="#64748b", font=("Segoe UI", 8))
            c.create_text(LEFT + bar_max_w, TOP - 16, text=str(max_seats), anchor="center",
                          fill="#64748b", font=("Segoe UI", 8))

            for i, (abbr, info) in enumerate(sorted_parties):
                y = TOP + i * (BAR_H + GAP)
                bar_w = int(info["total"] / max_seats * bar_max_w)
                won_bar_w = int(info["won"] / max_seats * bar_max_w)
                color = ABBR_COLORS.get(abbr, "#6b7280")

                c.create_text(LEFT - 6, y + BAR_H // 2, text=abbr,
                              anchor="e", font=("Segoe UI", 9, "bold"), fill="#1e293b")
                c.create_rectangle(LEFT, y, LEFT + bar_max_w, y + BAR_H, fill="#e2e8f0", outline="")

                if bar_w > 0:
                    c.create_rectangle(LEFT, y, LEFT + bar_w, y + BAR_H, fill=color, outline="")
                if won_bar_w > 0:
                    c.create_rectangle(LEFT, y, LEFT + won_bar_w, y + BAR_H, fill="#065f46", outline="", stipple="")
                    c.create_rectangle(LEFT, y + 2, LEFT + won_bar_w, y + BAR_H - 2, fill="#059669", outline="")

                lbl = f"{info['total']}  Won:{info['won']}  Lead:{info['leading']}"
                c.create_text(LEFT + bar_w + 10, y + BAR_H // 2, text=lbl, anchor="w",
                              font=("Segoe UI", 8), fill="#1e293b")

            maj_x = LEFT + int(MAJORITY_MARK / max_seats * bar_max_w)
            max_y = TOP + len(sorted_parties) * (BAR_H + GAP)
            c.create_line(maj_x, TOP - 20, maj_x, max_y + 4, fill="#dc2626", dash=(5, 3), width=2)
            c.create_text(maj_x + 4, TOP - 22, text=f"Majority ({MAJORITY_MARK})",
                          anchor="w", fill="#dc2626", font=("Segoe UI", 8, "bold"))

            leg_y = max_y + 14
            c.create_rectangle(LEFT, leg_y, LEFT + 14, leg_y + 12, fill="#059669", outline="")
            c.create_text(LEFT + 18, leg_y + 6, anchor="w", fill="#374151",
                          font=("Segoe UI", 8),
                          text="= Won (declared)    Lighter = Still Leading (in progress)")

        self.summary_canvas.after(100, _draw_summary_bars)

    def _build_charts_tab(self):
        f = self.tab_charts
        if not HAS_MPL:
            tk.Label(f, text="Install matplotlib to see charts:\n\npip install matplotlib",
                     font=("Segoe UI", 12), bg="white", fg="#64748b").pack(expand=True)
            self._charts_ready = False
            return
        self._charts_ready = True

        scroll_canvas = tk.Canvas(f, bg="white", highlightthickness=0)
        vsb = ttk.Scrollbar(f, orient="vertical", command=scroll_canvas.yview)
        hsb = ttk.Scrollbar(f, orient="horizontal", command=scroll_canvas.xview)
        scroll_canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        hsb.pack(side="bottom", fill="x")
        vsb.pack(side="right", fill="y")
        scroll_canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(scroll_canvas, bg="white")
        scroll_win = scroll_canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_configure(event):
            scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all"))
        def _on_canvas_resize(event):
            scroll_canvas.itemconfig(scroll_win, width=event.width)

        inner.bind("<Configure>", _on_configure)
        scroll_canvas.bind("<Configure>", _on_canvas_resize)

        def _on_mousewheel(event):
            scroll_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        scroll_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        top_row = tk.Frame(inner, bg="white")
        top_row.pack(side="top", fill="x")
        bot_row = tk.Frame(inner, bg="white")
        bot_row.pack(side="top", fill="x")

        self._pie_frame = tk.Frame(top_row, bg="white", relief="flat", bd=1)
        self._pie_frame.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        self._bar_frame = tk.Frame(top_row, bg="white", relief="flat", bd=1)
        self._bar_frame.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        self._margin_frame = tk.Frame(bot_row, bg="white", relief="flat", bd=1)
        self._margin_frame.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        self._status_frame = tk.Frame(bot_row, bg="white", relief="flat", bd=1)
        self._status_frame.pack(side="left", fill="both", expand=True, padx=2, pady=2)

        tk.Label(inner, text="Charts auto-refresh with data  |  matplotlib powered",
                 bg="white", fg="#94a3b8", font=("Segoe UI", 8)).pack(side="top", pady=4)

    def _refresh_charts_tab(self):
        if not HAS_MPL or not self._charts_ready:
            return
        pt = self._get_party_totals()
        sorted_pt = sorted(pt.items(), key=lambda x: x[1]["total"], reverse=True)
        sorted_pt = [(k, v) for k, v in sorted_pt if v["total"] > 0]
        labels = [p[0] for p in sorted_pt]
        totals = [p[1]["total"] for p in sorted_pt]
        wons = [p[1]["won"] for p in sorted_pt]
        colors = [ABBR_COLORS.get(p[0], "#9ca3af") for p in sorted_pt]
        self._draw_pie(labels, totals, colors)
        self._draw_bar(labels, totals, wons, colors)
        self._draw_margin_hist()
        self._draw_status_donut()

    def _embed_figure(self, key, parent, fig):
        old_canvas = self._mpl_canvases.get(key)
        if old_canvas:
            try:
                old_canvas.get_tk_widget().destroy()
            except Exception:
                pass
        old_fig = self._mpl_figures.get(key)
        if old_fig:
            try:
                old_fig.clf()
            except Exception:
                pass
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        widget = canvas.get_tk_widget()
        widget.pack(fill="both", expand=True)
        self._mpl_canvases[key] = canvas
        self._mpl_figures[key] = fig

    def _draw_pie(self, labels, totals, colors):
        combined = [(l, t, c) for l, t, c in zip(labels, totals, colors) if t > 0]
        if not combined:
            return
        labels, totals, colors = zip(*combined)
        labels, totals, colors = list(labels), list(totals), list(colors)
        fig = Figure(figsize=(4.5, 3.4), dpi=88, facecolor="white")
        ax = fig.add_subplot(111)
        _, _, autotexts = ax.pie(totals, labels=None, colors=colors,
            autopct=lambda p: f"{p:.1f}%" if p > 2 else "",
            startangle=140, pctdistance=0.8, wedgeprops=dict(linewidth=0.5, edgecolor="white"))
        for at in autotexts:
            at.set_fontsize(7)
        ax.set_title("Seat Share (Leading + Won)", fontsize=10, fontweight="bold", pad=8)
        patches = [mpatches.Patch(color=colors[i], label=f"{labels[i]} ({totals[i]})") for i in range(len(labels))]
        ax.legend(handles=patches, loc="lower center", bbox_to_anchor=(0.5, -0.22), ncol=3, fontsize=7, frameon=False)
        fig.tight_layout()
        self._embed_figure("pie", self._pie_frame, fig)

    def _draw_bar(self, labels, totals, wons, colors):
        if not totals:
            return
        fig = Figure(figsize=(4.5, 3.4), dpi=88, facecolor="white")
        ax = fig.add_subplot(111)
        y = list(range(len(labels)))
        leading_only = [t - w for t, w in zip(totals, wons)]
        ax.barh(y, leading_only, color=colors, alpha=0.55, label="Leading")
        ax.barh(y, wons, left=leading_only, color=colors, alpha=1.0, label="Won")
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=8)
        ax.axvline(MAJORITY_MARK, color="#dc2626", linewidth=1.2, linestyle="--", label=f"Majority ({MAJORITY_MARK})")
        ax.set_xlabel("Seats", fontsize=8)
        ax.set_title("Leading vs Won by Party", fontsize=10, fontweight="bold")
        ax.legend(fontsize=7, loc="lower right")
        ax.invert_yaxis()
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
        fig.tight_layout()
        self._embed_figure("bar", self._bar_frame, fig)

    def _draw_margin_hist(self):
        margins = [d["margin"] for d in self.data if d["margin"] >= 0]
        if not margins:
            return
        fig = Figure(figsize=(4.5, 3.0), dpi=88, facecolor="white")
        ax = fig.add_subplot(111)
        top = max(margins) + 1
        bins = [0, 500, 2000, 5000, 10000, 20000, top]
        bin_labels = ["<500", "500-2k", "2k-5k", "5k-10k", "10k-20k", ">20k"]
        counts = [sum(1 for m in margins if bins[i] <= m < bins[i + 1]) for i in range(len(bins) - 1)]
        bar_colors = ["#dc2626", "#f97316", "#eab308", "#22c55e", "#3b82f6", "#6366f1"]
        bars = ax.bar(bin_labels, counts, color=bar_colors, edgecolor="white", linewidth=0.7)
        for bar, count in zip(bars, counts):
            if count:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                        str(count), ha="center", va="bottom", fontsize=8, fontweight="bold")
        ax.set_title("Margin Distribution", fontsize=10, fontweight="bold")
        ax.set_xlabel("Victory Margin", fontsize=8)
        ax.set_ylabel("No. of Constituencies", fontsize=8)
        ax.tick_params(axis="both", labelsize=8)
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
        fig.tight_layout()
        self._embed_figure("margin", self._margin_frame, fig)

    def _draw_status_donut(self):
        won = sum(1 for d in self.data if d["status"] == "Won")
        prog = len(self.data) - won
        no_data = max(0, 234 - len(self.data))
        raw_values = [won, prog, no_data]
        raw_lbls = [f"Declared ({won})", f"In Progress ({prog})", f"No Data ({no_data})"]
        raw_clrs = ["#065f46", "#f97316", "#e2e8f0"]
        combined = [(v, l, c) for v, l, c in zip(raw_values, raw_lbls, raw_clrs) if v > 0]
        if not combined:
            return
        values, lbls, clrs = zip(*combined)
        fig = Figure(figsize=(4.5, 3.0), dpi=88, facecolor="white")
        ax = fig.add_subplot(111)
        ax.pie(list(values), labels=None, colors=list(clrs), startangle=90, wedgeprops=dict(width=0.5, edgecolor="white"))
        ax.text(0, 0, f"{won}\nDeclared", ha="center", va="center", fontsize=11, fontweight="bold", color="#065f46")
        patches = [mpatches.Patch(color=c, label=l) for l, c in zip(lbls, clrs)]
        ax.legend(handles=patches, loc="lower center", bbox_to_anchor=(0.5, -0.15), ncol=3, fontsize=7, frameon=False)
        ax.set_title("Result Status (of 234 seats)", fontsize=10, fontweight="bold")
        fig.tight_layout()
        self._embed_figure("donut", self._status_frame, fig)

    def _build_party_tab(self):
        f = self.tab_party
        srow = tk.Frame(f, bg="white", pady=6, padx=8)
        srow.pack(fill="x")
        sf = make_search_entry(srow, self.party_search_var, self._refresh_party_tab)
        sf.pack(side="left")
        self.party_row_lbl = tk.Label(srow, text="", bg="white", fg="#64748b", font=("Segoe UI", 8))
        self.party_row_lbl.pack(side="right")

        cols = ("Party", "Short", "Leading", "Won", "Total", "Trailing")
        self.party_tree = ttk.Treeview(f, columns=cols, show="headings", height=22)
        col_widths = {"Party": 320, "Short": 80, "Leading": 100, "Won": 80, "Total": 80, "Trailing": 100}
        col_anchors = {"Party": "w", "Short": "center", "Leading": "center",
                       "Won": "center", "Total": "center", "Trailing": "center"}
        for c in cols:
            self.party_tree.heading(c, text=c if c != "Leading" else "Leading\n(In Progress)",
                                    command=lambda _c=c: self._sort_party(_c))
            self.party_tree.column(c, width=col_widths.get(c, 80), anchor=col_anchors.get(c, "center"))
        vsb = ttk.Scrollbar(f, orient="vertical", command=self.party_tree.yview)
        self.party_tree.configure(yscrollcommand=vsb.set)
        self.party_tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=(0, 8))
        vsb.pack(side="left", fill="y", pady=(0, 8))

    def _sort_party(self, col):
        self._party_sort_rev = (col == self._party_sort_col) and not self._party_sort_rev
        self._party_sort_col = col
        self._refresh_party_tab()

    def _refresh_party_tab(self, *_):
        q = self.party_search_var.get().lower()
        pt = self._get_party_totals()
        tree = self.party_tree
        tree.delete(*tree.get_children())
        col_map = {"Party": "full", "Short": "abbr", "Leading": "leading",
                   "Won": "won", "Total": "total", "Trailing": "trailing"}
        key = col_map.get(self._party_sort_col, "total")
        sorted_items = sorted(pt.items(), key=lambda x: x[1].get(key, 0) if key in ("leading","won","total","trailing") else str(x[1].get(key,"")),
                              reverse=self._party_sort_rev)
        TAG_BG = {"TVK": "#dbeafe", "DMK": "#dcfce7", "AIADMK": "#fee2e2",
                  "BJP": "#ffedd5", "INC": "#e0e7ff", "PMK": "#fef9c3",
                  "VCK": "#d1fae5", "CPI": "#f3e8ff", "IUML": "#d1fae5"}
        shown = 0
        for abbr, info in sorted_items:
            if q and q not in info["full"].lower() and q not in abbr.lower():
                continue
            tag = abbr if abbr in TAG_BG else "other"
            tree.insert("", "end", values=(info["full"], abbr, info["leading"], info["won"], info["total"], info["trailing"]), tags=(tag,))
            shown += 1
        for tag, bg in TAG_BG.items():
            tree.tag_configure(tag, background=bg)
        self.party_row_lbl.config(text=f"{shown} parties")

    def _build_table_tab(self):
        f = self.tab_table
        frow = tk.Frame(f, bg="white", pady=6)
        frow.pack(fill="x", padx=8)
        sf = make_search_entry(frow, self.search_var, self.apply_filters)
        sf.pack(side="left")

        tk.Label(frow, text="Party:", bg="white", font=("Segoe UI", 9)).pack(side="left", padx=(12, 2))
        party_cb = ttk.Combobox(frow, textvariable=self.party_filter, width=10, state="readonly",
                                values=["All", "TVK", "DMK", "AIADMK", "BJP", "INC",
                                        "PMK", "VCK", "CPI", "CPI(M)", "DMDK", "AMMK", "IUML", "IND"])
        party_cb.pack(side="left")
        party_cb.bind("<<ComboboxSelected>>", lambda _: self.apply_filters())

        tk.Label(frow, text="Margin:", bg="white", font=("Segoe UI", 9)).pack(side="left", padx=(12, 2))
        margin_cb = ttk.Combobox(frow, textvariable=self.margin_filter, width=14, state="readonly",
                                 values=["All", "Close (<500)", "Tight (<2000)", "Comfortable (>5000)", "Big (>15000)"])
        margin_cb.pack(side="left")
        margin_cb.bind("<<ComboboxSelected>>", lambda _: self.apply_filters())

        self.row_count_lbl = tk.Label(frow, text="", bg="white", fg="#64748b", font=("Segoe UI", 8))
        self.row_count_lbl.pack(side="right", padx=8)

        tree_container = tk.Frame(f, bg="white")
        tree_container.pack(fill="both", expand=True, padx=(8, 8), pady=(0, 4))

        cols = ("No", "Constituency", "Leading Candidate", "Lead Party",
                "Trailing Candidate", "Trail Party", "Total Votes", "Margin", "Round", "Status")
        self.main_tree = ttk.Treeview(tree_container, columns=cols, show="headings", height=24)
        col_widths = {"No": 45, "Constituency": 150, "Leading Candidate": 180, "Lead Party": 70,
                      "Trailing Candidate": 180, "Trail Party": 70, "Total Votes": 90, "Margin": 80, "Round": 65, "Status": 90}
        for c in cols:
            w = col_widths.get(c, 100)
            anc = "center" if c in ("No", "Total Votes", "Margin", "Round", "Status", "Lead Party", "Trail Party") else "w"
            self.main_tree.heading(c, text=c, command=lambda _c=c: self._sort_main(_c))
            self.main_tree.column(c, width=w, anchor=anc)

        vsb = ttk.Scrollbar(tree_container, orient="vertical", command=self.main_tree.yview)
        vsb.pack(side="right", fill="y")
        hsb = ttk.Scrollbar(tree_container, orient="horizontal", command=self.main_tree.xview)
        hsb.pack(side="bottom", fill="x")
        self.main_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.main_tree.pack(side="left", fill="both", expand=True)

        self.main_tree.tag_configure("close", background="#fef2f2")
        self.main_tree.tag_configure("very_close", background="#fee2e2")
        self.main_tree.tag_configure("big", background="#f0fdf4")
        self.main_tree.tag_configure("won", background="#bbf7d0", foreground="#065f46")

    def _sort_main(self, col):
        self.sort_col = col
        self.sort_rev = not self.sort_rev
        self.apply_filters()

    def apply_filters(self, *_):
        q = self.search_var.get().lower()
        pf = self.party_filter.get()
        mf = self.margin_filter.get()

        rows = []
        for d in self.data:
            if q and not (q in d["constituency"].lower() or q in d["lead_cand"].lower() or
                          q in d["trail_cand"].lower() or q in d["lead_short"].lower() or
                          q in d["trail_short"].lower() or q in d["lead_party"].lower()):
                continue
            if pf != "All" and d["lead_short"] != pf:
                continue
            if mf == "Close (<500)" and d["margin"] >= 500: continue
            if mf == "Tight (<2000)" and d["margin"] >= 2000: continue
            if mf == "Comfortable (>5000)" and d["margin"] <= 5000: continue
            if mf == "Big (>15000)" and d["margin"] <= 15000: continue
            rows.append(d)

        col_key = {"No": "no", "Constituency": "constituency", "Lead Party": "lead_short",
                   "Trail Party": "trail_short", "Total Votes": "total_votes", "Margin": "margin",
                   "Round": "round", "Status": "status", "Leading Candidate": "lead_cand",
                   "Trailing Candidate": "trail_cand"}.get(self.sort_col, "no")
        rows.sort(key=lambda r: r.get(col_key, 0) if col_key in ("no", "margin", "total_votes") else str(r.get(col_key, "")),
                  reverse=self.sort_rev)

        tree = self.main_tree
        tree.delete(*tree.get_children())
        for d in rows:
            m = d["margin"]
            tv = d.get("total_votes", -1)
            tag = "won" if d["status"] == "Won" else "very_close" if 0 <= m < 500 else "close" if 0 <= m < 2000 else "big" if m > 15000 else ""
            m_str = f"{m:,}" if m >= 0 else "—"
            tv_str = f"{tv:,}" if tv >= 0 else "—"
            tree.insert("", "end", values=(d["no"], d["constituency"], d["lead_cand"], d["lead_short"],
                      d.get("trail_cand", ""), d.get("trail_short", "—"), tv_str, m_str, d["round"], d["status"]), tags=(tag,))
        self.row_count_lbl.config(text=f"{len(rows)} of {len(self.data)} constituencies")

    def _build_close_tab(self):
        f = self.tab_close
        tk.Label(f, text="⚔  Close Contests (margin < 2000)",
                 font=("Segoe UI", 11, "bold"), bg="white", fg="#991b1b").pack(pady=(12, 4))
        srow = tk.Frame(f, bg="white", padx=8, pady=4)
        srow.pack(fill="x")
        sf = make_search_entry(srow, self.close_search_var, self._refresh_close_tab)
        sf.pack(side="left")
        self.close_row_lbl = tk.Label(srow, text="", bg="white", fg="#64748b", font=("Segoe UI", 8))
        self.close_row_lbl.pack(side="right")

        cols = ("No", "Constituency", "Leading", "Lead Party", "Trailing", "Trail Party", "Margin", "Round")
        self.close_tree = ttk.Treeview(f, columns=cols, show="headings", height=22)
        widths = {"No": 40, "Constituency": 160, "Leading": 190, "Lead Party": 70,
                  "Trailing": 190, "Trail Party": 70, "Margin": 70, "Round": 65}
        for c in cols:
            anc = "center" if c in ("No", "Margin", "Round", "Lead Party", "Trail Party") else "w"
            self.close_tree.heading(c, text=c)
            self.close_tree.column(c, width=widths.get(c, 100), anchor=anc)
        vsb = ttk.Scrollbar(f, orient="vertical", command=self.close_tree.yview)
        self.close_tree.configure(yscrollcommand=vsb.set)
        self.close_tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=(0, 8))
        vsb.pack(side="left", fill="y", pady=(0, 8))
        self.close_tree.tag_configure("very_close", background="#fee2e2")
        self.close_tree.tag_configure("close", background="#fef2f2")

    def _refresh_close_tab(self, *_):
        q = self.close_search_var.get().lower()
        tree = self.close_tree
        tree.delete(*tree.get_children())
        close = sorted([d for d in self.data if 0 <= d["margin"] < 2000], key=lambda x: x["margin"])
        shown = 0
        for d in close:
            if q and not (q in d["constituency"].lower() or q in d["lead_cand"].lower() or
                          q in d["trail_cand"].lower() or q in d["lead_short"].lower() or
                          q in d["trail_short"].lower()):
                continue
            tag = "very_close" if d["margin"] < 500 else "close"
            tree.insert("", "end", values=(d["no"], d["constituency"], d["lead_cand"], d["lead_short"],
                      d["trail_cand"], d["trail_short"], f"{d['margin']:,}", d["round"]), tags=(tag,))
            shown += 1
        total_close = sum(1 for d in self.data if 0 <= d["margin"] < 2000)
        self.close_row_lbl.config(text=f"{shown} of {total_close} close contests")

    def _build_stats_tab(self):
        f = self.tab_stats
        tk.Label(f, text="🔬  Statistical Analysis", font=("Segoe UI", 12, "bold"), bg="white", fg="#1e3a5f").pack(pady=(10, 2))
        tk.Label(f, text="Deep-dive metrics  •  Vote distributions  •  Alliance breakdown  •  Top margins",
                 font=("Segoe UI", 8), bg="white", fg="#64748b").pack(pady=(0, 4))
        if not HAS_MPL:
            tk.Label(f, text="Install matplotlib:\n\npip install matplotlib", font=("Segoe UI", 12), bg="white", fg="#64748b").pack(expand=True)
            self._stats_ready = False
            return
        self._stats_ready = True

        sc = tk.Canvas(f, bg="white", highlightthickness=0)
        vsb = ttk.Scrollbar(f, orient="vertical", command=sc.yview)
        hsb = ttk.Scrollbar(f, orient="horizontal", command=sc.xview)
        sc.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        hsb.pack(side="bottom", fill="x")
        vsb.pack(side="right", fill="y")
        sc.pack(side="left", fill="both", expand=True)

        self._stats_inner = tk.Frame(sc, bg="white")
        win_id = sc.create_window((0, 0), window=self._stats_inner, anchor="nw")

        def _cfg(e): sc.configure(scrollregion=sc.bbox("all"))
        def _resize(e): sc.itemconfig(win_id, width=e.width)
        self._stats_inner.bind("<Configure>", _cfg)
        sc.bind("<Configure>", _resize)

        def _mw(e): sc.yview_scroll(int(-1*(e.delta/120)), "units")
        sc.bind_all("<MouseWheel>", _mw)

        self._stat_cards_frame = tk.Frame(self._stats_inner, bg="white")
        self._stat_cards_frame.pack(fill="x", padx=12, pady=(4, 8))

        row1 = tk.Frame(self._stats_inner, bg="white")
        row1.pack(fill="x", padx=4)
        self._topmargin_frame = tk.Frame(row1, bg="white", relief="groove", bd=1)
        self._topmargin_frame.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        self._alliance_frame = tk.Frame(row1, bg="white", relief="groove", bd=1)
        self._alliance_frame.pack(side="left", fill="both", expand=True, padx=4, pady=4)

        row2 = tk.Frame(self._stats_inner, bg="white")
        row2.pack(fill="x", padx=4)
        self._box_frame = tk.Frame(row2, bg="white", relief="groove", bd=1)
        self._box_frame.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        self._conc_frame = tk.Frame(row2, bg="white", relief="groove", bd=1)
        self._conc_frame.pack(side="left", fill="both", expand=True, padx=4, pady=4)

        row3 = tk.Frame(self._stats_inner, bg="white")
        row3.pack(fill="x", padx=4)
        self._heat_frame = tk.Frame(row3, bg="white", relief="groove", bd=1)
        self._heat_frame.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        self._cumvote_frame = tk.Frame(row3, bg="white", relief="groove", bd=1)
        self._cumvote_frame.pack(side="left", fill="both", expand=True, padx=4, pady=4)

    def _refresh_stats_tab(self):
        if not HAS_MPL or not getattr(self, "_stats_ready", False):
            return
        if not self.data:
            return
        pt = self._get_party_totals()
        self._draw_stat_cards(pt)
        self._draw_top_margins()
        self._draw_alliance_pie(pt)
        self._draw_margin_boxplot()
        self._draw_vote_concentration(pt)
        self._draw_margin_heatmap()
        self._draw_cumulative_votes()

    def _draw_stat_cards(self, pt):
        f = self._stat_cards_frame
        for w in f.winfo_children():
            w.destroy()
        margins = [d["margin"] for d in self.data if d["margin"] >= 0]
        declared = sum(1 for d in self.data if d["status"] == "Won")
        close_cnt = sum(1 for m in margins if m < 2000)
        avg_m = int(sum(margins) / len(margins)) if margins else 0
        med_m = sorted(margins)[len(margins)//2] if margins else 0
        top_p = max(pt.items(), key=lambda x: x[1]["total"], default=("—", {}))[0]
        pct_dec = int(declared / 234 * 100)
        stats = [("Avg Margin", f"{avg_m:,}", "#1e3a5f"), ("Median Margin", f"{med_m:,}", "#0f766e"),
                 ("% Declared", f"{pct_dec}%", "#7c3aed"), ("Close Seats", f"{close_cnt}", "#dc2626"),
                 ("Leading Party", top_p, "#d97706"), ("Data Coverage", f"{len(self.data)}/234", "#374151")]
        for i, (title, val, color) in enumerate(stats):
            card = tk.Frame(f, bg=color, padx=14, pady=8, relief="flat")
            card.grid(row=0, column=i, padx=5, pady=3, sticky="ew")
            f.columnconfigure(i, weight=1)
            tk.Label(card, text=title, bg=color, fg="#e0f2fe", font=("Segoe UI", 7, "bold")).pack()
            tk.Label(card, text=val, bg=color, fg="white", font=("Segoe UI", 16, "bold")).pack()

    def _draw_top_margins(self):
        winners = sorted([d for d in self.data if d["margin"] > 0], key=lambda x: x["margin"], reverse=True)[:15]
        if not winners:
            return
        fig = Figure(figsize=(5.5, 4.0), dpi=88, facecolor="white")
        ax = fig.add_subplot(111)
        labels = [f"{d['constituency'][:16]} ({d['lead_short']})" for d in winners]
        values = [d["margin"] for d in winners]
        colors_list = [ABBR_COLORS.get(d["lead_short"], "#6b7280") for d in winners]
        y = list(range(len(labels)))
        bars = ax.barh(y, values, color=colors_list, edgecolor="white", linewidth=0.5)
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=7)
        ax.invert_yaxis()
        for bar, val in zip(bars, values):
            ax.text(bar.get_width() + max(values)*0.01, bar.get_y() + bar.get_height()/2, f"{val:,}", va="center", fontsize=6.5, color="#374151")
        ax.set_title("Top 15 Winning Margins", fontsize=10, fontweight="bold")
        ax.set_xlabel("Margin (votes)", fontsize=8)
        for sp in ["top", "right"]:
            ax.spines[sp].set_visible(False)
        ax.tick_params(axis="x", labelsize=7)
        fig.tight_layout()
        self._embed_figure("topmargin", self._topmargin_frame, fig)

    ALLIANCES = {"INDIA / DMK Front": ["DMK","TVK","INC","VCK","CPI","CPI(M)","IUML","DMDK"],
                 "NDA / BJP Front": ["BJP","PMK","AMMK"], "AIADMK": ["AIADMK"], "Others / IND": []}

    def _draw_alliance_pie(self, pt):
        totals_by_alliance = {}
        assigned = set()
        for name, parties in self.ALLIANCES.items():
            if parties:
                totals_by_alliance[name] = sum(pt.get(p, {}).get("total", 0) for p in parties)
                assigned.update(parties)
        totals_by_alliance["Others / IND"] = sum(info["total"] for abbr, info in pt.items() if abbr not in assigned and info["total"] > 0)
        colors_ali = ["#22c55e", "#f97316", "#ef4444", "#94a3b8"]
        labels_ali = list(totals_by_alliance.keys())
        values_ali = list(totals_by_alliance.values())
        combined = [(l,v,c) for l,v,c in zip(labels_ali,values_ali,colors_ali) if v > 0]
        if not combined:
            return
        labels_ali, values_ali, colors_ali = zip(*combined)
        fig = Figure(figsize=(4.5, 4.0), dpi=88, facecolor="white")
        ax = fig.add_subplot(111)
        wedges, texts, autotexts = ax.pie(values_ali, labels=None, colors=colors_ali,
            autopct=lambda p: f"{p:.1f}%" if p > 3 else "", startangle=120, pctdistance=0.75,
            wedgeprops=dict(width=0.55, edgecolor="white", linewidth=1.5))
        for at in autotexts:
            at.set_fontsize(8)
        ax.set_title("Alliance-wise Seat Share", fontsize=10, fontweight="bold")
        patches = [mpatches.Patch(color=c, label=f"{l} ({v})") for l,v,c in zip(labels_ali, values_ali, colors_ali)]
        ax.legend(handles=patches, loc="lower center", bbox_to_anchor=(0.5, -0.18), ncol=2, fontsize=7.5, frameon=False)
        fig.tight_layout()
        self._embed_figure("alliance", self._alliance_frame, fig)

    def _draw_margin_boxplot(self):
        import numpy as np
        parties_data = {}
        for d in self.data:
            if d["margin"] < 0:
                continue
            abbr = d["lead_short"]
            parties_data.setdefault(abbr, []).append(d["margin"])
        parties_data = {k: v for k, v in parties_data.items() if len(v) >= 3}
        if not parties_data:
            return
        sorted_p = sorted(parties_data.items(), key=lambda x: len(x[1]), reverse=True)[:8]
        fig = Figure(figsize=(5.5, 4.0), dpi=88, facecolor="white")
        ax = fig.add_subplot(111)
        data_vals = [item[1] for item in sorted_p]
        tick_lbls = [item[0] for item in sorted_p]
        bp = ax.boxplot(data_vals, vert=True, patch_artist=True,
                        medianprops=dict(color="#1e3a5f", linewidth=2),
                        whiskerprops=dict(linewidth=1), capprops=dict(linewidth=1.5),
                        flierprops=dict(marker="o", markersize=3, alpha=0.5))
        for patch, (abbr, _) in zip(bp["boxes"], sorted_p):
            patch.set_facecolor(ABBR_COLORS.get(abbr, "#9ca3af"))
            patch.set_alpha(0.75)
        ax.set_xticks(range(1, len(sorted_p)+1))
        ax.set_xticklabels(tick_lbls, fontsize=8)
        ax.set_title("Winning Margin Distribution by Party", fontsize=10, fontweight="bold")
        ax.set_ylabel("Victory Margin (votes)", fontsize=8)
        ax.tick_params(labelsize=8)
        for sp in ["top", "right"]:
            ax.spines[sp].set_visible(False)
        ax.yaxis.grid(True, linestyle="--", alpha=0.5)
        fig.tight_layout()
        self._embed_figure("boxplot", self._box_frame, fig)

    def _draw_vote_concentration(self, pt):
        sorted_pt = sorted([(k, v) for k, v in pt.items() if v["total"] > 0], key=lambda x: x[1]["total"], reverse=True)[:10]
        if not sorted_pt:
            return
        fig = Figure(figsize=(4.5, 4.0), dpi=88, facecolor="white")
        ax = fig.add_subplot(111)
        labels = [p[0] for p in sorted_pt]
        wons = [p[1]["won"] for p in sorted_pt]
        leads = [p[1]["leading"] for p in sorted_pt]
        colors_list = [ABBR_COLORS.get(p[0], "#6b7280") for p in sorted_pt]
        x = list(range(len(labels)))
        bars1 = ax.bar(x, wons, color=colors_list, label="Won (declared)", alpha=1.0, edgecolor="white", linewidth=0.8)
        bars2 = ax.bar(x, leads, bottom=wons, color=colors_list, label="Leading", alpha=0.45, edgecolor="white", linewidth=0.8)
        ax.axhline(MAJORITY_MARK, color="#dc2626", linewidth=1.2, linestyle="--", label=f"Majority ({MAJORITY_MARK})")
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=8, rotation=25, ha="right")
        ax.set_title("Won vs Leading — Top 10 Parties", fontsize=10, fontweight="bold")
        ax.set_ylabel("Seats", fontsize=8)
        ax.legend(fontsize=7, loc="upper right")
        for sp in ["top", "right"]:
            ax.spines[sp].set_visible(False)
        ax.yaxis.grid(True, linestyle="--", alpha=0.4)
        for i, (bar1, bar2) in enumerate(zip(bars1, bars2)):
            total = wons[i] + leads[i]
            ax.text(i, total + 0.5, str(total), ha="center", fontsize=7.5, fontweight="bold")
        fig.tight_layout()
        self._embed_figure("concentration", self._conc_frame, fig)

    def _draw_margin_heatmap(self):
        margins = [(d["no"], d["margin"], d["lead_short"]) for d in self.data if d["margin"] >= 0]
        if not margins:
            return
        fig = Figure(figsize=(5.5, 3.5), dpi=88, facecolor="white")
        ax = fig.add_subplot(111)
        xs = [m[0] for m in margins]
        ys = [m[1] for m in margins]
        cs = [ABBR_COLORS.get(m[2], "#6b7280") for m in margins]
        ax.scatter(xs, ys, c=cs, s=18, alpha=0.75, linewidths=0)
        ax.axhline(2000, color="#f97316", linewidth=1, linestyle="--", alpha=0.8, label="2k margin")
        ax.axhline(500, color="#dc2626", linewidth=1, linestyle=":", alpha=0.9, label="500 margin")
        ax.axhline(10000, color="#22c55e", linewidth=1, linestyle="--", alpha=0.6, label="10k margin")
        ax.set_title("Margin vs Constituency No.", fontsize=10, fontweight="bold")
        ax.set_xlabel("Constituency Number", fontsize=8)
        ax.set_ylabel("Victory Margin", fontsize=8)
        ax.legend(fontsize=6.5, loc="upper right")
        ax.tick_params(labelsize=7)
        for sp in ["top", "right"]:
            ax.spines[sp].set_visible(False)
        fig.tight_layout()
        self._embed_figure("heatmap", self._heat_frame, fig)

    def _draw_cumulative_votes(self):
        margins = sorted([d["margin"] for d in self.data if d["margin"] >= 0])
        if not margins:
            return
        n = len(margins)
        cum_pct = [(i+1)/n*100 for i in range(n)]
        fig = Figure(figsize=(4.5, 3.5), dpi=88, facecolor="white")
        ax = fig.add_subplot(111)
        ax.plot(margins, cum_pct, color="#3b82f6", linewidth=2)
        ax.fill_between(margins, cum_pct, alpha=0.12, color="#3b82f6")
        ax.axvline(500, color="#dc2626", linewidth=1, linestyle=":", label="500")
        ax.axvline(2000, color="#f97316", linewidth=1, linestyle="--", label="2000")
        ax.axhline(50, color="#64748b", linewidth=0.8, linestyle="--", alpha=0.6)
        pct_500 = sum(1 for m in margins if m < 500) / n * 100
        pct_2000 = sum(1 for m in margins if m < 2000) / n * 100
        ax.text(500+200, 12, f"{pct_500:.0f}% < 500", fontsize=7, color="#dc2626")
        ax.text(2000+200, 30, f"{pct_2000:.0f}% < 2k", fontsize=7, color="#f97316")
        ax.set_title("Cumulative % of Seats by Margin", fontsize=10, fontweight="bold")
        ax.set_xlabel("Victory Margin", fontsize=8)
        ax.set_ylabel("Cumulative % of seats", fontsize=8)
        ax.legend(fontsize=7, loc="lower right")
        ax.tick_params(labelsize=7)
        for sp in ["top", "right"]:
            ax.spines[sp].set_visible(False)
        ax.yaxis.grid(True, linestyle="--", alpha=0.4)
        fig.tight_layout()
        self._embed_figure("cumvote", self._cumvote_frame, fig)

    def _build_participants_tab(self):
        f = self.tab_participants
        tk.Label(f, text="👥  All Participants — Every Candidate, Party & NOTA",
                 font=("Segoe UI", 11, "bold"), bg="white", fg="#1e3a5f").pack(pady=(10, 2))
        tk.Label(f, text="Shows all contestants loaded from ECI constituency-wise pages  •  Click a row to see candidate photo",
                 font=("Segoe UI", 8), bg="white", fg="#64748b").pack()

        frow = tk.Frame(f, bg="white", pady=6, padx=8)
        frow.pack(fill="x")
        sf = make_search_entry(frow, self.participants_search_var, self._refresh_participants_tab)
        sf.pack(side="left")

        tk.Label(frow, text="Party:", bg="white", font=("Segoe UI", 9)).pack(side="left", padx=(12, 2))
        self._part_party_cb = ttk.Combobox(frow, textvariable=self.participants_party_var, width=10, state="readonly",
                                values=["All", "TVK", "DMK", "AIADMK", "BJP", "INC", "PMK", "VCK", "CPI", "CPI(M)", "DMDK", "AMMK", "IUML", "IND", "NOTA"])
        self._part_party_cb.pack(side="left")
        self._part_party_cb.bind("<<ComboboxSelected>>", lambda _: self._refresh_participants_tab())

        tk.Label(frow, text="Assembly:", bg="white", font=("Segoe UI", 9)).pack(side="left", padx=(10, 2))
        self._part_assembly_cb = ttk.Combobox(frow, textvariable=self.participants_assembly_var, width=18, state="readonly", values=["All"])
        self._part_assembly_cb.pack(side="left")
        self._part_assembly_cb.bind("<<ComboboxSelected>>", lambda _: self._refresh_participants_tab())

        tk.Label(frow, text="Result:", bg="white", font=("Segoe UI", 9)).pack(side="left", padx=(10, 2))
        result_cb = ttk.Combobox(frow, textvariable=self.participants_status_var, width=10, state="readonly",
                                 values=["All", "Won", "Leading", "Trailing", "NOTA"])
        result_cb.pack(side="left")
        result_cb.bind("<<ComboboxSelected>>", lambda _: self._refresh_participants_tab())

        self.part_row_lbl = tk.Label(frow, text="", bg="white", fg="#64748b", font=("Segoe UI", 8))
        self.part_row_lbl.pack(side="right", padx=8)

        body = tk.Frame(f, bg="white")
        body.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        self._photo_panel = tk.Frame(body, bg="#f8fafc", width=160, relief="flat", bd=0)
        self._photo_panel.pack(side="right", fill="y", padx=(4, 0))
        self._photo_panel.pack_propagate(False)

        tk.Label(self._photo_panel, text="📷 Candidate Photo", bg="#f8fafc", fg="#64748b", font=("Segoe UI", 8, "bold")).pack(pady=(8, 4))
        self._photo_img_lbl = tk.Label(self._photo_panel, bg="#f8fafc", text="Click a row\nto view photo",
                                        fg="#94a3b8", font=("Segoe UI", 8), justify="center")
        self._photo_img_lbl.pack(pady=4)
        self._photo_name_lbl = tk.Label(self._photo_panel, bg="#f8fafc", text="", fg="#1e3a5f", font=("Segoe UI", 8, "bold"), wraplength=148, justify="center")
        self._photo_name_lbl.pack(pady=2)
        self._photo_party_lbl = tk.Label(self._photo_panel, bg="#f8fafc", text="", fg="#64748b", font=("Segoe UI", 8), wraplength=148, justify="center")
        self._photo_party_lbl.pack(pady=1)
        self._photo_result_lbl = tk.Label(self._photo_panel, bg="#f8fafc", text="", fg="#065f46", font=("Segoe UI", 9, "bold"), wraplength=148, justify="center")
        self._photo_result_lbl.pack(pady=1)
        self._photo_votes_lbl = tk.Label(self._photo_panel, bg="#f8fafc", text="", fg="#374151", font=("Segoe UI", 8), wraplength=148, justify="center")
        self._photo_votes_lbl.pack(pady=1)

        if not HAS_PIL:
            tk.Label(self._photo_panel, text="Install Pillow for\nphoto display:\npip install Pillow", bg="#f8fafc", fg="#f97316", font=("Segoe UI", 7), justify="center").pack(pady=8)

        self._photo_cache_lbl = tk.Label(self._photo_panel, text="", bg="#f8fafc", fg="#94a3b8", font=("Segoe UI", 7), wraplength=148, justify="center")
        self._photo_cache_lbl.pack(side="bottom", pady=6)

        part_container = tk.Frame(body, bg="white")
        part_container.pack(side="left", fill="both", expand=True)

        cols = ("No", "Assembly", "Candidate", "Party", "Short", "EVM Votes", "Postal", "Total Votes", "Vote %", "Rank", "Result")
        self.part_tree = ttk.Treeview(part_container, columns=cols, show="headings", height=24)
        col_widths = {"No": 40, "Assembly": 155, "Candidate": 195, "Party": 230, "Short": 70,
                      "EVM Votes": 90, "Postal": 65, "Total Votes": 90, "Vote %": 60, "Rank": 50, "Result": 80}
        col_anchors = {"No": "center", "Assembly": "w", "Candidate": "w", "Party": "w", "Short": "center",
                       "EVM Votes": "center", "Postal": "center", "Total Votes": "center",
                       "Vote %": "center", "Rank": "center", "Result": "center"}
        for c in cols:
            self.part_tree.heading(c, text=c, command=lambda _c=c: self._sort_participants(_c))
            self.part_tree.column(c, width=col_widths.get(c, 90), anchor=col_anchors.get(c, "center"))

        vsb = ttk.Scrollbar(part_container, orient="vertical", command=self.part_tree.yview)
        vsb.pack(side="right", fill="y")
        hsb = ttk.Scrollbar(part_container, orient="horizontal", command=self.part_tree.xview)
        hsb.pack(side="bottom", fill="x")
        self.part_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.part_tree.pack(side="left", fill="both", expand=True)
        self.part_tree.bind("<<TreeviewSelect>>", self._on_participant_select)

        self.part_tree.tag_configure("won", background="#bbf7d0", foreground="#065f46")
        self.part_tree.tag_configure("leading", background="#dbeafe", foreground="#1e3a5f")
        self.part_tree.tag_configure("trailing", background="#f8fafc")
        self.part_tree.tag_configure("nota", background="#f1f5f9", foreground="#64748b")

        tk.Label(f, text="ℹ  Click 📷 Fetch Photos in toolbar to download & cache all candidate photos locally", bg="white", fg="#94a3b8", font=("Segoe UI", 8)).pack(side="bottom", pady=2)

    def _sort_participants(self, col):
        self._part_sort_rev = (col == self._part_sort_col) and not self._part_sort_rev
        self._part_sort_col = col
        self._refresh_participants_tab()

    def _refresh_participants_tab(self, *_):
        if not self._participants_data:
            self.part_tree.delete(*self.part_tree.get_children())
            self.part_row_lbl.config(text="No data — click Refresh Now")
            return

        q = self.participants_search_var.get().lower()
        pf = self.participants_party_var.get()
        af = self.participants_assembly_var.get()
        rf = self.participants_status_var.get()

        rows = []
        for d in self._participants_data:
            if q and not (q in d["candidate"].lower() or q in d["party"].lower() or q in d["party_short"].lower() or q in d["constituency"].lower()):
                continue
            if pf != "All" and d["party_short"] != pf:
                continue
            if af != "All" and d["constituency"] != af:
                continue
            if rf != "All" and d.get("result", "") != rf:
                continue
            rows.append(d)

        col_key = {"No": "no", "Assembly": "constituency", "Candidate": "candidate", "Party": "party",
                   "Short": "party_short", "EVM Votes": "evm_votes", "Postal": "postal_votes",
                   "Total Votes": "total_votes", "Vote %": "vote_pct", "Rank": "rank", "Result": "result"}.get(self._part_sort_col, "total_votes")
        numeric_cols = {"no", "evm_votes", "postal_votes", "total_votes", "rank"}
        rows.sort(key=lambda r: r.get(col_key, 0) if col_key in numeric_cols else str(r.get(col_key, "")), reverse=self._part_sort_rev)

        tree = self.part_tree
        tree.delete(*tree.get_children())
        for d in rows:
            result = d.get("result", "")
            tag = {"Won": "won", "Leading": "leading", "Trailing": "trailing", "NOTA": "nota"}.get(result, "trailing")
            evm_s = f"{d['evm_votes']:,}" if d["evm_votes"] >= 0 else "—"
            post_s = f"{d['postal_votes']:,}" if d["postal_votes"] >= 0 else "—"
            tot_s = f"{d['total_votes']:,}" if d["total_votes"] >= 0 else "—"
            tree.insert("", "end", values=(d["no"], d["constituency"], d["candidate"], d["party"], d["party_short"],
                      evm_s, post_s, tot_s, d.get("vote_pct", ""), d.get("rank", ""), result), tags=(tag,))
        total = len(self._participants_data)
        self.part_row_lbl.config(text=f"{len(rows):,} of {total:,} participants")

    def _load_participants(self):
        if not self.data:
            return
        import threading
        def _bg():
            cands = scrape_all_candidates(self.data)
            self.root.after(0, self._on_participants_ready, cands)
        threading.Thread(target=_bg, daemon=True).start()
        self.status_var.set(self.status_var.get() + "  |  Loading participants…")

    def _on_participants_ready(self, cands):
        self._participants_data = cands
        assemblies = sorted({d["constituency"] for d in cands})
        self._part_assembly_cb["values"] = ["All"] + assemblies
        self._refresh_participants_tab()
        sv = self.status_var.get()
        self.status_var.set(sv.replace("  |  Loading participants…", "") + f"  |  {len(cands):,} candidates loaded")
        self._refresh_photo_status()

    def _on_participant_select(self, event=None):
        sel = self.part_tree.selection()
        if not sel:
            return
        vals = self.part_tree.item(sel[0], "values")
        if not vals or len(vals) < 11:
            return
        ac_no = int(vals[0])
        cand_name = vals[2]
        party = vals[3]
        result = vals[10]
        votes = vals[7]
        self._show_photo_panel(ac_no, cand_name, party, result, votes)

    def _show_photo_panel(self, ac_no: int, cand_name: str, party: str, result: str, votes: str):
        self._photo_name_lbl.config(text=cand_name)
        self._photo_party_lbl.config(text=party)
        result_colors = {"Won": "#065f46", "Leading": "#1e3a5f", "Trailing": "#92400e", "NOTA": "#64748b"}
        self._photo_result_lbl.config(text=result, fg=result_colors.get(result, "#374151"))
        self._photo_votes_lbl.config(text=f"Votes: {votes}" if votes != "—" else "")

        if not HAS_PIL:
            self._photo_img_lbl.config(image="", text="Install Pillow:\npip install Pillow", fg="#f97316", compound="top")
            return

        cache_key = (ac_no, cand_name)
        if cache_key in self._photo_cache:
            photo = self._photo_cache[cache_key]
            if photo is None:
                self._photo_img_lbl.config(image="", text="No photo\navailable", fg="#94a3b8", compound="top")
            else:
                self._photo_img_lbl.config(image=photo, text="", compound="top")
                self._photo_img_lbl.image = photo
            return

        def _load_from_db():
            _, img_data = db_get_photo(ac_no, cand_name)
            self.root.after(0, self._apply_photo, cache_key, cand_name, img_data)
        threading.Thread(target=_load_from_db, daemon=True).start()
        self._photo_img_lbl.config(image="", text="Loading…", fg="#64748b", compound="top")

    def _apply_photo(self, cache_key, cand_name: str, img_data):
        if img_data:
            try:
                pil_img = PILImage.open(io.BytesIO(img_data))
                pil_img.thumbnail((148, 180), PILImage.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(pil_img)
                self._photo_cache[cache_key] = photo
                self._photo_img_lbl.config(image=photo, text="", compound="top")
                self._photo_img_lbl.image = photo
                return
            except Exception:
                pass
        self._photo_cache[cache_key] = None
        self._photo_img_lbl.config(image="", text="No photo\navailable", fg="#94a3b8", compound="top")

    def _refresh_photo_status(self):
        try:
            stats = db_photo_stats()
            if stats["total"] == 0:
                self._photo_status_var.set("No photos cached")
            else:
                self._photo_status_var.set(f"📷 {stats['with_img']:,}/{stats['total']:,} photos  ({stats['acs']}/234 ACs)")
            if hasattr(self, "_photo_cache_lbl"):
                self._photo_cache_lbl.config(text=f"DB: {stats['with_img']} photos\n{stats['acs']}/234 ACs scraped")
        except Exception:
            pass

    def _start_photo_fetch(self):
        if self._photo_job_running:
            self._photo_stop.set()
            self._photo_btn.config(text="📷  Fetch Photos", bg="#7c3aed", activebackground="#6d28d9")
            self._photo_status_var.set("Cancelling…")
            return

        self._photo_stop.clear()
        self._photo_job_running = True
        self._photo_btn.config(text="⏹  Stop Fetch", bg="#dc2626", activebackground="#b91c1c")

        if self.data:
            ac_list = [d["no"] for d in self.data]
            known = set(ac_list)
            ac_list += [i for i in range(1, 235) if i not in known]
        else:
            ac_list = list(range(1, 235))

        def _bg():
            fetch_photos_for_ac_list(ac_list, progress_cb=self._photo_progress_cb, stop_event=self._photo_stop)
            self.root.after(0, self._photo_fetch_done)
        threading.Thread(target=_bg, daemon=True).start()

    def _photo_progress_cb(self, done: int, total: int, msg: str):
        self.root.after(0, self._photo_status_var.set, msg)
        if done > 0 and done % 20 == 0:
            self.root.after(0, self._refresh_photo_status)
            self._photo_cache.clear()

    def _photo_fetch_done(self):
        self._photo_job_running = False
        self._photo_btn.config(text="📷  Fetch Photos", bg="#7c3aed", activebackground="#6d28d9")
        self._refresh_photo_status()
        self._photo_cache.clear()

    def _build_notable_tab(self):
        f = self.tab_notable
        tk.Label(f, text="⭐  Notable Contests to Watch", font=("Segoe UI", 11, "bold"), bg="white", fg="#1e3a5f").pack(pady=(12, 2))
        tk.Label(f, text="(Key candidates, high-profile constituencies — live from ECI)", font=("Segoe UI", 9), bg="white", fg="#64748b").pack()

        srow = tk.Frame(f, bg="white", padx=8, pady=4)
        srow.pack(fill="x")
        sf = make_search_entry(srow, self.notable_search_var, self._refresh_notable_tab)
        sf.pack(side="left")
        self.notable_row_lbl = tk.Label(srow, text="", bg="white", fg="#64748b", font=("Segoe UI", 8))
        self.notable_row_lbl.pack(side="right")

        cols = ("No", "Constituency", "Why Notable", "Leading", "Lead Party", "Trailing", "Trail Party", "Margin")
        self.notable_tree = ttk.Treeview(f, columns=cols, show="headings", height=20)
        widths = {"No": 40, "Constituency": 150, "Why Notable": 220, "Leading": 160,
                  "Lead Party": 70, "Trailing": 160, "Trail Party": 70, "Margin": 80}
        for c in cols:
            anc = "center" if c in ("No", "Margin", "Lead Party", "Trail Party") else "w"
            self.notable_tree.heading(c, text=c)
            self.notable_tree.column(c, width=widths.get(c, 100), anchor=anc)
        vsb = ttk.Scrollbar(f, orient="vertical", command=self.notable_tree.yview)
        self.notable_tree.configure(yscrollcommand=vsb.set)
        self.notable_tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=(4, 8))
        vsb.pack(side="left", fill="y", pady=(4, 8))

    NOTABLE_RULES = [
        (13, "Kolathur — CM M.K. Stalin's seat"), (200, "Bodinayakanur — OPS (Panneerselvam) contest"),
        (59, "Dharmapuri — Sowmiya Anbumani (PMK)"), (211, "Ramanathapuram — BJP vs DMK"),
        (98, "Erode East — INC vs TVK"), (152, "Vriddhachalam — Premallatha Vijayakant (DMDK)"),
        (8, "Ambattur — Watch for big TVK lead"), (6, "Avadi — TVK stronghold watch"),
        (166, "Thiruthuraipoondi — CPI contest"), (21, "Anna Nagar — Urban Chennai seat"),
        (25, "Mylapore — Chennai key seat"), (19, "Chepauk-Thiruvallikeni — Chennai coastal"),
    ]

    def _refresh_notable_tab(self, *_):
        q = self.notable_search_var.get().lower()
        tree = self.notable_tree
        tree.delete(*tree.get_children())
        lookup = {d["no"]: d for d in self.data}
        shown = 0
        for (no, note) in self.NOTABLE_RULES:
            d = lookup.get(no)
            constituency = d["constituency"] if d else f"AC #{no}"
            m_str = f"{d['margin']:,}" if d and d["margin"] >= 0 else "—"
            lead = d["lead_cand"] if d else "—"
            lead_s = d["lead_short"] if d else "—"
            trail = d["trail_cand"] if d else "—"
            trail_s = d["trail_short"] if d else "—"
            if q and not (q in constituency.lower() or q in note.lower() or q in lead.lower() or q in lead_s.lower() or q in trail.lower() or q in trail_s.lower()):
                continue
            tree.insert("", "end", values=(no, constituency, note, lead, lead_s, trail, trail_s, m_str))
            shown += 1
        self.notable_row_lbl.config(text=f"{shown} of {len(self.NOTABLE_RULES)} notable seats")

    def _get_party_totals(self) -> dict:
        from collections import Counter
        trail_count = Counter(d["trail_short"] for d in self.data)
        if self.eci_party:
            result = {}
            for abbr, info in self.eci_party.items():
                result[abbr] = dict(info)
                result[abbr]["trailing"] = trail_count.get(abbr, 0)
            for abbr, cnt in trail_count.items():
                if abbr not in result and abbr != "—":
                    party_map = {v: k for k, v in PARTY_SHORT.items()}
                    full = party_map.get(abbr, abbr)
                    color = PARTY_COLORS.get(full, ABBR_COLORS.get(abbr, "#6b7280"))
                    result[abbr] = {"abbr": abbr, "full": full, "won": 0, "leading": 0, "total": 0, "trailing": cnt, "color": color}
            return result

        won_count = Counter(d["lead_short"] for d in self.data if d["status"] == "Won")
        leading_only_count = Counter(d["lead_short"] for d in self.data if d["status"] != "Won")
        party_map = {v: k for k, v in PARTY_SHORT.items()}
        totals = {}
        all_abbrs = set(won_count) | set(leading_only_count) | set(trail_count)
        for abbr in all_abbrs:
            if abbr == "—":
                continue
            full = party_map.get(abbr, abbr)
            color = PARTY_COLORS.get(full, ABBR_COLORS.get(abbr, "#6b7280"))
            won = won_count.get(abbr, 0)
            leading = leading_only_count.get(abbr, 0)
            totals[abbr] = {"abbr": abbr, "full": full, "leading": leading, "won": won, "total": won + leading, "trailing": trail_count.get(abbr, 0), "color": color}
        return totals

    def refresh_data(self):
        if self._loading:
            return
        self._loading = True
        self.status_var.set("⏳ Fetching data from ECI…")
        self.progress.pack(fill="x", padx=8, pady=2)
        self.progress.start(10)
        threading.Thread(target=self._fetch_thread, daemon=True).start()

    def _fetch_thread(self):
        try:
            data, last_upd, eci_party = scrape_all()
            self.root.after(0, self._on_data_ready, data, last_upd, eci_party)
        except Exception as e:
            self.root.after(0, self._on_fetch_error, str(e))

    def _on_data_ready(self, data, last_upd, eci_party=None):
        self.data = data
        self.last_updated = last_upd
        self.eci_party = eci_party or {}
        self._loading = False
        self.progress.stop()
        self.progress.pack_forget()
        now = datetime.now().strftime("%H:%M:%S")
        self.status_var.set(f"✓ {len(data)} constituencies loaded  |  Last fetch: {now}")
        
        self._refresh_summary()
        self._refresh_charts_tab()
        self._refresh_stats_tab()
        self._refresh_party_tab()
        self.apply_filters()
        self._refresh_close_tab()
        self._refresh_notable_tab()
        self._load_participants()
        
        # Update offline status indicator
        self.offline_status_lbl.config(text="🌐 LIVE", fg="#2563eb")
        
        self._schedule_refresh()

    def _on_fetch_error(self, err):
        self._loading = False
        self.progress.stop()
        self.progress.pack_forget()
        self.status_var.set(f"⚠ Error fetching data: {err[:80]}")
        self._schedule_refresh()

    def _schedule_refresh(self):
        if self._refresh_job:
            self.root.after_cancel(self._refresh_job)
            self._refresh_job = None
        if self._countdown_job:
            self.root.after_cancel(self._countdown_job)
            self._countdown_job = None
        if self.auto_refresh.get() and not self.offline_mode.get():
            secs = self.refresh_interval.get()
            self._refresh_job = self.root.after(secs * 1000, self.refresh_data)
            self._countdown_remaining = secs
            self._tick_countdown()

    def _tick_countdown(self):
        if not self.auto_refresh.get() or self._loading or self.offline_mode.get():
            return
        remaining = self._countdown_remaining
        base = self.status_var.get().split("  |  Next")[0]
        self.status_var.set(f"{base}  |  Next refresh in {remaining}s")
        if remaining > 0:
            self._countdown_remaining -= 1
            self._countdown_job = self.root.after(1000, self._tick_countdown)

    def _export_pdf_current_tab(self):
        if not HAS_RL and not HAS_MPL:
            messagebox.showerror("Missing libraries", "PDF export requires reportlab (for tables) or matplotlib (for charts).\nInstall with:\n  pip install reportlab matplotlib")
            return

        tab_index = self._nb.index(self._nb.select())
        tab_names = ["summary", "charts", "stats", "party", "table", "close", "notable", "participants"]
        tab = tab_names[tab_index] if tab_index < len(tab_names) else "unknown"

        from tkinter import filedialog
        default_name = f"TN_Election_2026_{tab}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")],
                                            initialfile=default_name, title=f"Export '{tab}' tab as PDF")
        if not path:
            return

        try:
            if tab == "summary":
                self._pdf_summary(path)
            elif tab == "charts":
                self._pdf_charts(path)
            elif tab == "stats":
                self._pdf_stats(path)
            elif tab == "party":
                self._pdf_treeview(path, self.party_tree, title="Party-wise Results",
                    subtitle=f"Search: '{self.party_search_var.get()}'" if self.party_search_var.get() else "All parties",
                    col_widths=[6.5, 1.8, 2, 1.8, 1.8, 2])
            elif tab == "table":
                filters = []
                if self.search_var.get(): filters.append(f"Search: '{self.search_var.get()}'")
                if self.party_filter.get() != "All": filters.append(f"Party: {self.party_filter.get()}")
                if self.margin_filter.get() != "All": filters.append(f"Margin: {self.margin_filter.get()}")
                self._pdf_treeview(path, self.main_tree, title="All Constituencies",
                    subtitle="  |  ".join(filters) if filters else "No filters applied — all constituencies",
                    col_widths=[0.9, 2.8, 3.2, 1.4, 3.2, 1.4, 1.6, 1.4, 1.2, 1.6], landscape_mode=True)
            elif tab == "close":
                self._pdf_treeview(path, self.close_tree, title="Close Contests (margin < 2000)",
                    subtitle=f"Search: '{self.close_search_var.get()}'" if self.close_search_var.get() else "All close contests",
                    col_widths=[0.9, 2.8, 3.2, 1.4, 3.2, 1.4, 1.4, 1.2], landscape_mode=True)
            elif tab == "notable":
                self._pdf_treeview(path, self.notable_tree, title="Notable Contests",
                    subtitle=f"Search: '{self.notable_search_var.get()}'" if self.notable_search_var.get() else "All notable seats",
                    col_widths=[0.8, 2.4, 4.0, 2.8, 1.3, 2.8, 1.3, 1.4], landscape_mode=True)
            elif tab == "participants":
                filters = []
                if self.participants_search_var.get(): filters.append(f"Search: '{self.participants_search_var.get()}'")
                if self.participants_party_var.get() != "All": filters.append(f"Party: {self.participants_party_var.get()}")
                if self.participants_assembly_var.get() != "All": filters.append(f"Assembly: {self.participants_assembly_var.get()}")
                if self.participants_status_var.get() != "All": filters.append(f"Result: {self.participants_status_var.get()}")
                self._pdf_participants_with_photos(path, self.part_tree, title="All Participants",
                    subtitle="  |  ".join(filters) if filters else "All candidates, parties & NOTA",
                    col_widths=[0.7, 2.6, 3.2, 3.8, 1.2, 1.5, 1.1, 1.5, 1.0, 0.8, 1.3], landscape_mode=True)
            messagebox.showinfo("Export complete", f"PDF saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))

    def _pdf_participants_with_photos(self, path, tree, title, subtitle="", col_widths=None, landscape_mode=False):
        """Export All Participants tab with photos and colored Won rows."""
        if not HAS_RL:
            messagebox.showerror("Missing library", "reportlab is required for table export.\n  pip install reportlab")
            return
        if not HAS_PIL:
            messagebox.showerror("Missing library", "Pillow is required for photo export.\n  pip install Pillow")
            return

        cols = tree["columns"]
        headers = [tree.heading(c)["text"] for c in cols]
        
        rows_data = []
        for iid in tree.get_children():
            vals = list(tree.item(iid, "values"))
            result_status = vals[-1] if vals else ""
            cand_name = vals[2] if len(vals) > 2 else ""
            assembly = vals[1] if len(vals) > 1 else ""
            
            ac_no = None
            for d in self._participants_data:
                if d["candidate"] == cand_name and d["constituency"] == assembly:
                    ac_no = d["no"]
                    break
            
            photo_data = None
            if ac_no and cand_name:
                _, img_data = db_get_photo(ac_no, cand_name)
                if img_data:
                    try:
                        pil_img = PILImage.open(io.BytesIO(img_data))
                        pil_img.thumbnail((100, 100), PILImage.Resampling.LANCZOS)
                        if pil_img.mode in ('RGBA', 'LA', 'P'):
                            pil_img = pil_img.convert('RGB')
                        photo_data = pil_img
                    except Exception as e:
                        print(f"Error processing photo for {cand_name}: {e}")
            
            rows_data.append({"values": vals, "result": result_status, "photo": photo_data})
        
        if not rows_data:
            messagebox.showwarning("Nothing to export", "No rows visible — nothing to export.")
            return
        
        doc = self._rl_doc(path, landscape_mode)
        page_w = (landscape(A4)[0] if landscape_mode else A4[0]) - 3*cm
        n_cols = len(cols) + 1
        
        if col_widths and len(col_widths) == n_cols - 1:
            total = sum(col_widths)
            photo_width_cm = 2.8
            photo_width_pt = photo_width_cm * 28.35
            remaining_width = page_w - photo_width_pt
            widths_pt = [photo_width_pt] + [w / total * remaining_width for w in col_widths]
        else:
            photo_width_pt = 2.8 * 28.35
            other_width = (page_w - photo_width_pt) / (n_cols - 1)
            widths_pt = [photo_width_pt] + [other_width] * (n_cols - 1)
        
        styles = getSampleStyleSheet()
        hdr_style = ParagraphStyle("th", parent=styles["Normal"], fontSize=8, fontName="Helvetica-Bold",
                                   textColor=rl_colors.white, alignment=TA_CENTER)
        cell_style = ParagraphStyle("td", parent=styles["Normal"], fontSize=7, fontName="Helvetica",
                                    textColor=rl_colors.HexColor("#1e293b"), alignment=TA_LEFT)
        cell_center = ParagraphStyle("tdc", parent=cell_style, alignment=TA_CENTER)
        cell_photo = ParagraphStyle("td_photo", parent=cell_style, alignment=TA_CENTER)
        
        CENTER_COLS = {"No", "Short", "EVM Votes", "Postal", "Total Votes", "Vote %", "Rank", "Result"}
        
        def cell(text, col_name="", is_header=False):
            if is_header:
                return Paragraph(str(text), hdr_style)
            s = cell_center if col_name in CENTER_COLS else cell_style
            return Paragraph(str(text), s)
        
        photo_header = Paragraph("Photo", hdr_style)
        header_row = [photo_header] + [Paragraph(h, hdr_style) for h in headers]
        table_data = [header_row]
        
        from reportlab.platypus import Image as RLImage
        
        for row in rows_data:
            row_cells = []
            if row["photo"]:
                try:
                    img_buffer = io.BytesIO()
                    row["photo"].save(img_buffer, format="PNG", quality=95, optimize=False)
                    img_buffer.seek(0)
                    img = RLImage(img_buffer, width=90, height=90, kind='proportional')
                    row_cells.append(img)
                except Exception as e:
                    print(f"Error creating image for PDF: {e}")
                    row_cells.append(Paragraph("Photo error", cell_photo))
            else:
                row_cells.append(Paragraph("No photo", cell_photo))
            
            for i, val in enumerate(row["values"]):
                col_name = headers[i] if i < len(headers) else ""
                para = cell(val, col_name)
                row_cells.append(para)
            table_data.append(row_cells)
        
        tbl = Table(table_data, colWidths=widths_pt, repeatRows=1)
        
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor("#1e3a5f")),
            ("GRID", (0, 0), (-1, -1), 0.3, rl_colors.HexColor("#cbd5e1")),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ROWHIGH", (0, 0), (-1, -1), 110),
        ]
        
        for i, row in enumerate(rows_data, start=1):
            if row["result"] == "Won":
                style_cmds.append(("BACKGROUND", (0, i), (-1, i), rl_colors.HexColor("#90EE90")))
            else:
                bg_color = rl_colors.HexColor("#f8fafc") if i % 2 == 1 else rl_colors.HexColor("#e8f0fe")
                style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg_color))
        
        tbl.setStyle(TableStyle(style_cmds))
        
        elems = self._rl_header_elements(title, subtitle)
        elems.append(Paragraph(f"{len(rows_data)} candidates", ParagraphStyle("rc", parent=styles["Normal"], fontSize=8,
                              textColor=rl_colors.HexColor("#64748b"), alignment=TA_RIGHT, spaceAfter=4)))
        elems.append(Spacer(1, 0.2*cm))
        elems.append(tbl)
        doc.build(elems)

    def _pdf_treeview(self, path, tree, title, subtitle="", col_widths=None, landscape_mode=False):
        """Export whatever rows are currently visible in a Treeview to a PDF table."""
        if not HAS_RL:
            messagebox.showerror("Missing library", "reportlab is required for table export.\n  pip install reportlab")
            return

        if title == "All Participants":
            self._pdf_participants_with_photos(path, tree, title, subtitle, col_widths, landscape_mode)
            return

        cols = tree["columns"]
        headers = [tree.heading(c)["text"] for c in cols]

        rows = []
        result_colors = {}
        for iid in tree.get_children():
            vals = list(tree.item(iid, "values"))
            rows.append(vals)
            if "Result" in headers:
                result_idx = headers.index("Result") if "Result" in headers else -1
                if result_idx >= 0 and len(vals) > result_idx:
                    result_colors[len(rows)-1] = vals[result_idx]

        if not rows:
            messagebox.showwarning("Nothing to export", "No rows visible — nothing to export.")
            return

        doc = self._rl_doc(path, landscape_mode)
        page_w = (landscape(A4)[0] if landscape_mode else A4[0]) - 3*cm
        n_cols = len(cols)

        if col_widths and len(col_widths) == n_cols:
            total = sum(col_widths)
            widths_pt = [w / total * page_w for w in col_widths]
        else:
            widths_pt = [page_w / n_cols] * n_cols

        styles = getSampleStyleSheet()
        hdr_style = ParagraphStyle("th", parent=styles["Normal"], fontSize=7, fontName="Helvetica-Bold",
                                   textColor=rl_colors.white, alignment=TA_CENTER)
        cell_style = ParagraphStyle("td", parent=styles["Normal"], fontSize=6.5, fontName="Helvetica",
                                    textColor=rl_colors.HexColor("#1e293b"), alignment=TA_LEFT)
        cell_center = ParagraphStyle("tdc", parent=cell_style, alignment=TA_CENTER)

        CENTER_COLS = {"No", "Short", "Leading\n(In Progress)", "Leading", "Won", "Total", "Trailing",
                       "Margin", "Round", "Status", "Lead Party", "Trail Party", "Total Votes",
                       "EVM Votes", "Postal", "Vote %", "Rank", "Result"}

        def cell(text, col_name="", is_header=False):
            if is_header:
                return Paragraph(str(text), hdr_style)
            s = cell_center if col_name in CENTER_COLS else cell_style
            return Paragraph(str(text), s)

        table_data = [[cell(h, "", True) for h in headers]]
        for r in rows:
            table_data.append([cell(v, headers[i]) for i, v in enumerate(r)])

        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor("#1e3a5f")),
            ("GRID", (0, 0), (-1, -1), 0.3, rl_colors.HexColor("#cbd5e1")),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
        
        for i in range(1, len(rows) + 1):
            if i-1 in result_colors and result_colors[i-1] == "Won":
                style_cmds.append(("BACKGROUND", (0, i), (-1, i), rl_colors.HexColor("#90EE90")))
            else:
                bg_color = rl_colors.HexColor("#f8fafc") if i % 2 == 1 else rl_colors.HexColor("#e8f0fe")
                style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg_color))

        tbl = Table(table_data, colWidths=widths_pt, repeatRows=1)
        tbl.setStyle(TableStyle(style_cmds))

        elems = self._rl_header_elements(title, subtitle)
        elems.append(Paragraph(f"{len(rows)} rows", ParagraphStyle("rc", parent=styles["Normal"], fontSize=7,
                              textColor=rl_colors.HexColor("#64748b"), alignment=TA_RIGHT, spaceAfter=4)))
        elems.append(tbl)
        doc.build(elems)

    def _rl_doc(self, path, landscape_mode=False):
        page = landscape(A4) if landscape_mode else A4
        return SimpleDocTemplate(path, pagesize=page, leftMargin=1.5*cm, rightMargin=1.5*cm,
                                 topMargin=1.8*cm, bottomMargin=1.8*cm)

    def _rl_header_elements(self, title, subtitle="", filter_info=""):
        styles = getSampleStyleSheet()
        h1 = ParagraphStyle("h1", parent=styles["Normal"], fontSize=14, fontName="Helvetica-Bold",
                            textColor=rl_colors.HexColor("#1e3a5f"), spaceAfter=2, alignment=TA_CENTER)
        h2 = ParagraphStyle("h2", parent=styles["Normal"], fontSize=9, fontName="Helvetica",
                            textColor=rl_colors.HexColor("#64748b"), spaceAfter=2, alignment=TA_CENTER)
        h3 = ParagraphStyle("h3", parent=styles["Normal"], fontSize=8, fontName="Helvetica-Oblique",
                            textColor=rl_colors.HexColor("#dc2626"), spaceAfter=4, alignment=TA_CENTER)
        ts = ParagraphStyle("ts", parent=styles["Normal"], fontSize=7, fontName="Helvetica",
                            textColor=rl_colors.HexColor("#94a3b8"), spaceAfter=6, alignment=TA_RIGHT)
        elems = [Paragraph("🗳  Tamil Nadu Assembly Election 2026", h1), Paragraph(title, h2)]
        if subtitle:
            elems.append(Paragraph(f"Filter: {subtitle}", h3))
        elems.append(Paragraph(f"Generated: {datetime.now().strftime('%d %b %Y  %H:%M:%S')}  |  "
                              f"ECI last update: {self.last_updated or 'N/A'}", ts))
        elems.append(HRFlowable(width="100%", thickness=1, color=rl_colors.HexColor("#1e3a5f"), spaceAfter=8))
        return elems

    def _pdf_summary(self, path):
        if not HAS_MPL:
            messagebox.showerror("Missing library", "matplotlib is required for chart export.\n  pip install matplotlib")
            return
        import io
        pt = self._get_party_totals()
        sorted_parties = sorted(pt.items(), key=lambda x: x[1]["total"], reverse=True)
        sorted_parties = [(a, v) for a, v in sorted_parties if v["total"] > 0]
        fig = Figure(figsize=(10, max(4, len(sorted_parties)*0.55 + 2)), dpi=110, facecolor="white")
        ax = fig.add_subplot(111)
        max_seats = max((v["total"] for _, v in sorted_parties), default=1)
        labels = [a for a, _ in sorted_parties]
        totals = [v["total"] for _, v in sorted_parties]
        wons = [v["won"] for _, v in sorted_parties]
        leads = [t - w for t, w in zip(totals, wons)]
        colors_l = [ABBR_COLORS.get(a, "#6b7280") for a, _ in sorted_parties]
        y = list(range(len(labels)))
        ax.barh(y, leads, color=colors_l, alpha=0.45, label="Leading")
        ax.barh(y, wons, left=leads, color=colors_l, alpha=1.0, label="Won")
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=9)
        ax.invert_yaxis()
        ax.axvline(MAJORITY_MARK, color="#dc2626", linewidth=1.5, linestyle="--", label=f"Majority ({MAJORITY_MARK})")
        for i, (t, w, l) in enumerate(zip(totals, wons, leads)):
            ax.text(t + 0.5, i, f"{t}  (W:{w} L:{l})", va="center", fontsize=8)
        ax.set_xlabel("Seats", fontsize=9)
        ax.set_title("Party-wise Seat Tally — Leading + Won", fontsize=11, fontweight="bold")
        ax.legend(fontsize=8, loc="lower right")
        for sp in ["top", "right"]:
            ax.spines[sp].set_visible(False)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
        buf.seek(0)
        if HAS_RL:
            doc = self._rl_doc(path)
            page_w = A4[0] - 3*cm
            declared = sum(1 for d in self.data if d["status"] == "Won")
            with_data = len(self.data)
            tvk = pt.get("TVK", {}).get("total", 0)
            dmk = pt.get("DMK", {}).get("total", 0)
            aiadmk = pt.get("AIADMK", {}).get("total", 0)
            styles = getSampleStyleSheet()
            card_style = ParagraphStyle("card", parent=styles["Normal"], fontSize=8, fontName="Helvetica-Bold",
                                        textColor=rl_colors.HexColor("#1e3a5f"), alignment=TA_CENTER)
            metrics = [("Total Seats", "234"), ("With Data", str(with_data)), ("Majority Mark", str(MAJORITY_MARK)),
                       ("TVK Lead+Won", str(tvk)), ("DMK Lead+Won", str(dmk)), ("AIADMK Lead+Won", str(aiadmk)),
                       ("Results Declared", str(declared)), ("In Progress", str(with_data-declared))]
            card_data = [[Paragraph(f"{t}\n{v}", card_style) for t, v in metrics]]
            card_colors = ["#1e3a5f","#0f766e","#374151","#2563eb","#16a34a","#dc2626","#7c3aed","#d97706"]
            bg_cmds = [("BACKGROUND",(i,0),(i,0), rl_colors.HexColor(c)) for i, c in enumerate(card_colors)]
            card_tbl = Table(card_data, colWidths=[page_w/8]*8)
            card_tbl.setStyle(TableStyle([("TEXTCOLOR", (0,0),(-1,-1), rl_colors.white), ("FONTNAME", (0,0),(-1,-1), "Helvetica-Bold"),
                ("FONTSIZE", (0,0),(-1,-1), 8), ("ALIGN", (0,0),(-1,-1), "CENTER"), ("VALIGN", (0,0),(-1,-1), "MIDDLE"),
                ("TOPPADDING",(0,0),(-1,-1), 8), ("BOTTOMPADDING",(0,0),(-1,-1), 8), ("GRID", (0,0),(-1,-1), 0.5, rl_colors.white)] + bg_cmds))
            img_w = page_w
            img_h = img_w * fig.get_figheight() / fig.get_figwidth()
            from reportlab.platypus import Image as RLImage
            img = RLImage(buf, width=img_w, height=img_h)
            elems = self._rl_header_elements("Summary — Overall Snapshot")
            elems += [card_tbl, Spacer(1, 0.4*cm), img]
            doc.build(elems)
        else:
            with PdfPages(path) as pp:
                fig.savefig(pp, format="pdf", bbox_inches="tight")

    def _pdf_charts(self, path):
        if not HAS_MPL:
            messagebox.showerror("Missing library", "matplotlib required.\n  pip install matplotlib")
            return
        pt = self._get_party_totals()
        sorted_pt = sorted(pt.items(), key=lambda x: x[1]["total"], reverse=True)
        sorted_pt = [(k, v) for k, v in sorted_pt if v["total"] > 0]
        labels = [p[0] for p in sorted_pt]
        totals = [p[1]["total"] for p in sorted_pt]
        wons = [p[1]["won"] for p in sorted_pt]
        colors_list = [ABBR_COLORS.get(p[0], "#9ca3af") for p in sorted_pt]
        with PdfPages(path) as pp:
            fig = Figure(figsize=(14, 6), facecolor="white")
            ax1 = fig.add_subplot(1, 2, 1)
            ax2 = fig.add_subplot(1, 2, 2)
            combined = [(l,t,c) for l,t,c in zip(labels,totals,colors_list) if t>0]
            if combined:
                ll, tt, cc = zip(*combined)
                ax1.pie(tt, labels=None, colors=cc, autopct=lambda p: f"{p:.1f}%" if p > 2 else "",
                        startangle=140, pctdistance=0.8, wedgeprops=dict(linewidth=0.5, edgecolor="white"))
                patches = [mpatches.Patch(color=cc[i], label=f"{ll[i]} ({tt[i]})") for i in range(len(ll))]
                ax1.legend(handles=patches, loc="lower center", bbox_to_anchor=(0.5,-0.22), ncol=3, fontsize=7, frameon=False)
                ax1.set_title("Seat Share (Leading + Won)", fontsize=11, fontweight="bold")
            if totals:
                y = list(range(len(labels)))
                leading_only = [t - w for t, w in zip(totals, wons)]
                ax2.barh(y, leading_only, color=colors_list, alpha=0.55, label="Leading")
                ax2.barh(y, wons, left=leading_only, color=colors_list, alpha=1.0, label="Won")
                ax2.set_yticks(y); ax2.set_yticklabels(labels, fontsize=9)
                ax2.axvline(MAJORITY_MARK, color="#dc2626", linewidth=1.2, linestyle="--", label=f"Majority ({MAJORITY_MARK})")
                ax2.set_xlabel("Seats", fontsize=9)
                ax2.set_title("Leading vs Won by Party", fontsize=11, fontweight="bold")
                ax2.legend(fontsize=8, loc="lower right")
                ax2.invert_yaxis()
                for sp in ["top","right"]: ax2.spines[sp].set_visible(False)
            fig.suptitle("TN Election 2026 — Charts", fontsize=13, fontweight="bold", y=1.01)
            fig.tight_layout()
            pp.savefig(fig, bbox_inches="tight")
            fig2 = Figure(figsize=(14, 6), facecolor="white")
            ax3 = fig2.add_subplot(1, 2, 1)
            ax4 = fig2.add_subplot(1, 2, 2)
            margins = [d["margin"] for d in self.data if d["margin"] >= 0]
            if margins:
                top = max(margins)+1
                bins = [0,500,2000,5000,10000,20000,top]
                bin_labels = ["<500","500-2k","2k-5k","5k-10k","10k-20k",">20k"]
                counts = [sum(1 for m in margins if bins[i]<=m<bins[i+1]) for i in range(len(bins)-1)]
                bar_colors = ["#dc2626","#f97316","#eab308","#22c55e","#3b82f6","#6366f1"]
                bars = ax3.bar(bin_labels, counts, color=bar_colors, edgecolor="white", linewidth=0.7)
                for bar, count in zip(bars, counts):
                    if count:
                        ax3.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.3, str(count), ha="center", va="bottom", fontsize=9, fontweight="bold")
                ax3.set_title("Margin Distribution", fontsize=11, fontweight="bold")
                ax3.set_xlabel("Victory Margin", fontsize=9)
                ax3.set_ylabel("No. of Constituencies", fontsize=9)
                for sp in ["top","right"]: ax3.spines[sp].set_visible(False)
            won = sum(1 for d in self.data if d["status"]=="Won")
            prog = len(self.data)-won; no_data = max(0,234-len(self.data))
            raw_values = [v for v in [won,prog,no_data] if v>0]
            raw_lbls = [l for l,v in zip([f"Declared ({won})",f"In Progress ({prog})",f"No Data ({no_data})"], [won,prog,no_data]) if v>0]
            raw_clrs_all = ["#065f46","#f97316","#e2e8f0"]
            raw_clrs = [c for c,v in zip(raw_clrs_all,[won,prog,no_data]) if v>0]
            if raw_values:
                ax4.pie(raw_values, labels=None, colors=raw_clrs, startangle=90, wedgeprops=dict(width=0.5, edgecolor="white"))
                ax4.text(0,0,f"{won}\nDeclared",ha="center",va="center", fontsize=12,fontweight="bold",color="#065f46")
                patches4=[mpatches.Patch(color=c,label=l) for l,c in zip(raw_lbls,raw_clrs)]
                ax4.legend(handles=patches4,loc="lower center", bbox_to_anchor=(0.5,-0.15), ncol=3, fontsize=8, frameon=False)
                ax4.set_title("Result Status (of 234 seats)",fontsize=11,fontweight="bold")
            fig2.tight_layout()
            pp.savefig(fig2, bbox_inches="tight")

    def _pdf_stats(self, path):
        if not HAS_MPL:
            messagebox.showerror("Missing library", "matplotlib required.\n  pip install matplotlib")
            return
        pt = self._get_party_totals()
        sorted_pt = sorted([(k,v) for k,v in pt.items() if v["total"]>0], key=lambda x: x[1]["total"], reverse=True)
        figs = []
        winners = sorted([d for d in self.data if d["margin"]>0], key=lambda x: x["margin"], reverse=True)[:15]
        if winners:
            fig = Figure(figsize=(10,5), dpi=100, facecolor="white")
            ax = fig.add_subplot(111)
            labels_w = [f"{d['constituency'][:18]} ({d['lead_short']})" for d in winners]
            vals_w = [d["margin"] for d in winners]
            clrs_w = [ABBR_COLORS.get(d["lead_short"],"#6b7280") for d in winners]
            y_w = list(range(len(labels_w)))
            bars_w = ax.barh(y_w, vals_w, color=clrs_w, edgecolor="white")
            ax.set_yticks(y_w); ax.set_yticklabels(labels_w, fontsize=8); ax.invert_yaxis()
            for bar, val in zip(bars_w, vals_w):
                ax.text(bar.get_width()+max(vals_w)*0.01, bar.get_y()+bar.get_height()/2, f"{val:,}", va="center", fontsize=7)
            ax.set_title("Top 15 Winning Margins", fontsize=11, fontweight="bold")
            ax.set_xlabel("Margin (votes)", fontsize=9)
            for sp in ["top","right"]: ax.spines[sp].set_visible(False)
            fig.tight_layout(); figs.append(("Top 15 Winning Margins", fig))
        totals_by_alliance = {}
        assigned = set()
        for name, parties in self.ALLIANCES.items():
            if parties:
                totals_by_alliance[name] = sum(pt.get(p,{}).get("total",0) for p in parties)
                assigned.update(parties)
        totals_by_alliance["Others / IND"] = sum(info["total"] for abbr, info in pt.items() if abbr not in assigned and info["total"] > 0)
        colors_ali = ["#22c55e","#f97316","#ef4444","#94a3b8"]
        combined_ali = [(l,v,c) for l,v,c in zip(totals_by_alliance.keys(), totals_by_alliance.values(), colors_ali) if v>0]
        if combined_ali:
            ll,vv,cc = zip(*combined_ali)
            fig = Figure(figsize=(7,5), dpi=100, facecolor="white")
            ax = fig.add_subplot(111)
            ax.pie(vv, labels=None, colors=cc, autopct=lambda p: f"{p:.1f}%" if p>3 else "",
                   startangle=120, pctdistance=0.75, wedgeprops=dict(width=0.55, edgecolor="white"))
            ax.set_title("Alliance-wise Seat Share", fontsize=11, fontweight="bold")
            patches_a = [mpatches.Patch(color=c, label=f"{l} ({v})") for l,v,c in zip(ll,vv,cc)]
            ax.legend(handles=patches_a, loc="lower center", bbox_to_anchor=(0.5,-0.15), ncol=2, fontsize=9, frameon=False)
            fig.tight_layout(); figs.append(("Alliance-wise Seat Share", fig))
        parties_data = {}
        for d in self.data:
            if d["margin"] < 0: continue
            parties_data.setdefault(d["lead_short"], []).append(d["margin"])
        parties_data = {k:v for k,v in parties_data.items() if len(v)>=3}
        if parties_data:
            sorted_pd = sorted(parties_data.items(), key=lambda x: len(x[1]), reverse=True)[:8]
            fig = Figure(figsize=(10,5), dpi=100, facecolor="white")
            ax = fig.add_subplot(111)
            bp = ax.boxplot([item[1] for item in sorted_pd], vert=True, patch_artist=True,
                            medianprops=dict(color="#1e3a5f",linewidth=2))
            for patch,(abbr,_) in zip(bp["boxes"], sorted_pd):
                patch.set_facecolor(ABBR_COLORS.get(abbr,"#9ca3af")); patch.set_alpha(0.75)
            ax.set_xticks(range(1,len(sorted_pd)+1))
            ax.set_xticklabels([item[0] for item in sorted_pd], fontsize=9)
            ax.set_title("Winning Margin Distribution by Party", fontsize=11, fontweight="bold")
            ax.set_ylabel("Victory Margin (votes)", fontsize=9)
            for sp in ["top","right"]: ax.spines[sp].set_visible(False)
            ax.yaxis.grid(True, linestyle="--", alpha=0.5)
            fig.tight_layout(); figs.append(("Margin Distribution by Party", fig))
        top10 = sorted_pt[:10]
        if top10:
            fig = Figure(figsize=(10,5), dpi=100, facecolor="white")
            ax = fig.add_subplot(111)
            lbls = [p[0] for p in top10]
            ww = [p[1]["won"] for p in top10]
            ll2 = [p[1]["leading"] for p in top10]
            clrs = [ABBR_COLORS.get(p[0],"#6b7280") for p in top10]
            x = list(range(len(lbls)))
            ax.bar(x, ww, color=clrs, alpha=1.0, label="Won", edgecolor="white")
            ax.bar(x, ll2, bottom=ww, color=clrs, alpha=0.45, label="Leading", edgecolor="white")
            ax.axhline(MAJORITY_MARK, color="#dc2626", linewidth=1.2, linestyle="--", label=f"Majority ({MAJORITY_MARK})")
            ax.set_xticks(x); ax.set_xticklabels(lbls, fontsize=9, rotation=25, ha="right")
            ax.set_title("Won vs Leading — Top 10 Parties", fontsize=11, fontweight="bold")
            ax.set_ylabel("Seats", fontsize=9)
            ax.legend(fontsize=8, loc="upper right")
            for sp in ["top","right"]: ax.spines[sp].set_visible(False)
            for i in range(len(lbls)):
                ax.text(i, ww[i]+ll2[i]+0.5, str(ww[i]+ll2[i]), ha="center", fontsize=8, fontweight="bold")
            fig.tight_layout(); figs.append(("Won vs Leading — Top 10 Parties", fig))
        scatter_data = [(d["no"],d["margin"],d["lead_short"]) for d in self.data if d["margin"]>=0]
        if scatter_data:
            fig = Figure(figsize=(10,5), dpi=100, facecolor="white")
            ax = fig.add_subplot(111)
            ax.scatter([m[0] for m in scatter_data],[m[1] for m in scatter_data],
                       c=[ABBR_COLORS.get(m[2],"#6b7280") for m in scatter_data], s=20, alpha=0.75, linewidths=0)
            ax.axhline(2000, color="#f97316", linewidth=1, linestyle="--", label="2k margin")
            ax.axhline(500, color="#dc2626", linewidth=1, linestyle=":", label="500 margin")
            ax.axhline(10000,color="#22c55e", linewidth=1, linestyle="--", label="10k margin")
            ax.set_title("Margin vs Constituency No.", fontsize=11, fontweight="bold")
            ax.set_xlabel("Constituency Number", fontsize=9)
            ax.set_ylabel("Victory Margin", fontsize=9)
            ax.legend(fontsize=7, loc="upper right")
            for sp in ["top","right"]: ax.spines[sp].set_visible(False)
            fig.tight_layout(); figs.append(("Margin vs Constituency No.", fig))
        margins_sorted = sorted([d["margin"] for d in self.data if d["margin"]>=0])
        if margins_sorted:
            n = len(margins_sorted)
            cum = [(i+1)/n*100 for i in range(n)]
            fig = Figure(figsize=(10,5), dpi=100, facecolor="white")
            ax = fig.add_subplot(111)
            ax.plot(margins_sorted, cum, color="#3b82f6", linewidth=2)
            ax.fill_between(margins_sorted, cum, alpha=0.12, color="#3b82f6")
            ax.axvline(500, color="#dc2626", linewidth=1, linestyle=":", label="500")
            ax.axvline(2000, color="#f97316", linewidth=1, linestyle="--", label="2000")
            ax.axhline(50, color="#64748b", linewidth=0.8, linestyle="--", alpha=0.6)
            ax.set_title("Cumulative % of Seats by Margin", fontsize=11, fontweight="bold")
            ax.set_xlabel("Victory Margin", fontsize=9)
            ax.set_ylabel("Cumulative % of seats", fontsize=9)
            ax.legend(fontsize=8, loc="lower right")
            for sp in ["top","right"]: ax.spines[sp].set_visible(False)
            ax.yaxis.grid(True, linestyle="--", alpha=0.4)
            fig.tight_layout(); figs.append(("Cumulative % of Seats by Margin", fig))
        if not figs:
            messagebox.showwarning("No data", "No statistics data available to export.")
            return
        with PdfPages(path) as pp:
            for _title_c, fig_c in figs:
                pp.savefig(fig_c, bbox_inches="tight")


def main():
    if BOOTSTRAP:
        root = ttkb.Window(themename="litera")
    else:
        root = tk.Tk()
        ttk.Style().theme_use("clam")
    app = TNElectionApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()