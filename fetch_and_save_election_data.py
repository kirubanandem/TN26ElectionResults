#!/usr/bin/env python3
"""
Election Data Scraper & JSON Exporter
Fetches all Tamil Nadu Election 2026 data from ECI and saves to JSON files
Run this script to create a permanent local copy of all election data

Usage:
    python fetch_and_save_election_data.py
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import sys
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
from collections import Counter

# Constants
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
PARTY_WISE_URL = "https://results.eci.gov.in/ResultAcGenMay2026/partywiseresult-S22.htm"
LEAD_URL_TEMPLATE = "https://results.eci.gov.in/ResultAcGenMay2026/partywiseleadresult-{}S22.htm"
WIN_URL_TEMPLATE = "https://results.eci.gov.in/ResultAcGenMay2026/partywisewinresult-{}S22.htm"
CONSTWISE_TEMPLATE = "https://results.eci.gov.in/ResultAcGenMay2026/ConstituencywiseS22{}.htm"
CANDWISE_TEMPLATE = "https://results.eci.gov.in/ResultAcGenMay2026/candidateswise-S22{}.htm"

# Party name mappings
PARTY_SHORT = {
    "Tamilaga Vettri Kazhagam": "TVK",
    "Dravida Munnetra Kazhagam": "DMK",
    "All India Anna Dravida Munnetra Kazhagam": "AIADMK",
    "Bharatiya Janata Party": "BJP",
    "Indian National Congress": "INC",
    "Pattali Makkal Katchi": "PMK",
    "Viduthalai Chiruthaigal Katchi": "VCK",
    "Communist Party of India": "CPI",
    "Communist Party of India (Marxist)": "CPI(M)",
    "Desiya Murpokku Dravida Kazhagam": "DMDK",
    "Amma Makkal Munnettra Kazagam": "AMMK",
    "Indian Union Muslim League": "IUML",
    "Independent": "IND",
}

PARTY_COLORS = {
    "TVK": "#3b82f6", "DMK": "#22c55e", "AIADMK": "#ef4444", "BJP": "#f97316",
    "INC": "#6366f1", "PMK": "#eab308", "VCK": "#10b981", "CPI": "#a855f7",
    "CPI(M)": "#9333ea", "DMDK": "#f59e0b", "AMMK": "#64748b", "IUML": "#059669", "IND": "#94a3b8",
}

_ECI_ABBR_MAP = {
    "ADMK": "AIADMK", "TVK": "TVK", "DMK": "DMK", "INC": "INC", "PMK": "PMK",
    "BJP": "BJP", "IUML": "IUML", "VCK": "VCK", "CPI": "CPI", "CPI(M)": "CPI(M)",
    "DMDK": "DMDK", "AMMKMNKZ": "AMMK", "AMMK": "AMMK",
}


def short(party_full):
    return PARTY_SHORT.get(party_full, party_full[:8] if party_full else "—")


def _int(text):
    try:
        return int(text.strip().replace(",", ""))
    except (ValueError, AttributeError):
        return -1


def _parse_constituency_link(cell_text):
    m = re.match(r"^(.*?)\((\d+)\)\s*$", cell_text.strip())
    if m:
        return m.group(1).strip(), int(m.group(2))
    return cell_text.strip(), 0


def scrape_party_index():
    """Fetch the ECI party-wise summary page."""
    try:
        resp = requests.get(PARTY_WISE_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch party index: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    result = []

    for table in soup.find_all("table"):
        headers = [c.get_text(strip=True).lower() 
                   for c in (table.find_all("th") or table.find("tr").find_all("td"))]
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

            result.append({
                "abbr": abbr, "full": full_name, "won": won_count,
                "leading": leading_count, "total": total_count,
                "lead_id": lead_id, "win_id": win_id,
            })
        break
    return result


def scrape_lead_or_win_page(url, party_full, status):
    """Scrape a partywiseleadresult or partywisewinresult page."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
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
            "total_votes": total_votes, "margin": margin, "round": round_info, "status": status,
        })
    return rows, last_updated


def scrape_constwise(ac_no):
    """Fetch ConstituencywiseS22{ac}.htm and return candidate data."""
    url = CONSTWISE_TEMPLATE.format(ac_no)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception:
        return None, None

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if not table:
        return None, None

    # Get last updated time
    last_updated = ""
    for txt in soup.stripped_strings:
        if "Last Updated" in txt:
            last_updated = txt.strip()
            break

    candidates = []
    for tr in table.find_all("tr")[1:]:
        tds = tr.find_all("td")
        if len(tds) < 6:
            continue
        name = tds[1].get_text(strip=True)
        party = tds[2].get_text(strip=True)
        evm = _int(tds[3].get_text()) if len(tds) > 3 else -1
        postal = _int(tds[4].get_text()) if len(tds) > 4 else -1
        total = _int(tds[5].get_text()) if len(tds) > 5 else -1
        pct = tds[6].get_text(strip=True) if len(tds) > 6 else ""

        if name and name.upper() != "TOTAL":
            candidates.append({
                "name": name, "party": party, "party_short": short(party),
                "evm_votes": evm, "postal_votes": postal, "total_votes": total,
                "vote_percentage": pct
            })

    return candidates, last_updated


def scrape_candidate_photos(ac_no):
    """Fetch candidateswise page for photo URLs."""
    url = CANDWISE_TEMPLATE.format(ac_no)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception:
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
        
        results.append({"candidate_name": cand_name, "photo_url": img_url})
    
    return results


def fetch_all_data():
    """Main function to fetch all election data."""
    print("=" * 70)
    print("  TN Election 2026 - Data Scraper & JSON Exporter")
    print("=" * 70)
    print("\nFetching live data from ECI...\n")
    
    # Step 1: Get party index
    print("1. Fetching party index...")
    party_index = scrape_party_index()
    print(f"   Found {len(party_index)} parties")
    
    # Step 2: Get constituency results from lead/win pages
    print("2. Fetching constituency results...")
    all_constituencies = {}
    last_updated = ""
    
    for p in party_index:
        if p["lead_id"] and p["leading"] > 0:
            url = LEAD_URL_TEMPLATE.format(p["lead_id"])
            result = scrape_lead_or_win_page(url, p["full"], "In Progress")
            if result:
                rows, upd = result
                if upd and not last_updated:
                    last_updated = upd
                for r in rows:
                    if r["no"] not in all_constituencies:
                        all_constituencies[r["no"]] = r
        
        if p["win_id"] and p["won"] > 0:
            url = WIN_URL_TEMPLATE.format(p["win_id"])
            result = scrape_lead_or_win_page(url, p["full"], "Won")
            if result:
                rows, upd = result
                if upd and not last_updated:
                    last_updated = upd
                for r in rows:
                    if r["no"] not in all_constituencies:
                        all_constituencies[r["no"]] = r
                    else:
                        all_constituencies[r["no"]]["status"] = "Won"
                        all_constituencies[r["no"]]["margin"] = r["margin"]
                        all_constituencies[r["no"]]["round"] = r["round"]
        
        print(f"   Progress: {len(all_constituencies)} constituencies", end="\r")
    
    print(f"\n   Total constituencies: {len(all_constituencies)}")
    
    # Step 3: Fetch detailed candidate data for each constituency
    print("3. Fetching detailed candidate data...")
    constituency_list = list(all_constituencies.values())
    
    for i, const in enumerate(constituency_list):
        const_no = const["no"]
        candidates, upd = scrape_constwise(const_no)
        if candidates:
            # Find winner and runner-up
            sorted_candidates = sorted(candidates, key=lambda x: x["total_votes"], reverse=True)
            winner = sorted_candidates[0] if sorted_candidates else None
            runner_up = sorted_candidates[1] if len(sorted_candidates) > 1 else None
            
            const["candidates"] = candidates
            const["winner"] = winner
            const["runner_up"] = runner_up
            
            if winner:
                const["winner_party"] = winner["party_short"]
                const["winner_votes"] = winner["total_votes"]
            if upd and not const.get("last_updated"):
                const["last_updated"] = upd
        
        if (i + 1) % 50 == 0:
            print(f"   Progress: {i + 1}/{len(constituency_list)}", end="\r")
    
    print(f"\n   Completed: {len(constituency_list)} constituencies")
    
    # Step 4: Fetch photo URLs (optional - can be done later)
    print("4. Fetching candidate photo URLs...")
    for i, const in enumerate(constituency_list):
        const_no = const["no"]
        photos = scrape_candidate_photos(const_no)
        if photos:
            # Match photos with candidates
            for candidate in const.get("candidates", []):
                for photo in photos:
                    if photo["candidate_name"] == candidate["name"]:
                        candidate["photo_url"] = photo["photo_url"]
                        break
        
        if (i + 1) % 50 == 0:
            print(f"   Progress: {i + 1}/{len(constituency_list)}", end="\r")
    
    print(f"\n   Completed photo URL fetching")
    
    # Step 5: Calculate party totals
    print("5. Calculating party totals...")
    party_totals = {}
    for const in constituency_list:
        abbr = const.get("lead_short", "Unknown")
        if abbr not in party_totals:
            party_totals[abbr] = {
                "abbr": abbr, "full": const.get("lead_party", abbr),
                "won": 0, "leading": 0, "total": 0, "color": PARTY_COLORS.get(abbr, "#6b7280")
            }
        if const["status"] == "Won":
            party_totals[abbr]["won"] += 1
        else:
            party_totals[abbr]["leading"] += 1
        party_totals[abbr]["total"] = party_totals[abbr]["won"] + party_totals[abbr]["leading"]
    
    # Prepare final data package
    final_data = {
        "metadata": {
            "export_date": datetime.now().isoformat(),
            "last_updated": last_updated,
            "total_constituencies": len(constituency_list),
            "source": "Election Commission of India",
            "election": "Tamil Nadu Assembly Election 2026",
            "total_seats": 234
        },
        "party_totals": party_totals,
        "constituencies": constituency_list,
        "party_index": party_index
    }
    
    return final_data


def save_data(data, output_dir="election_data"):
    """Save data to JSON files."""
    os.makedirs(output_dir, exist_ok=True)
    
    # Save complete dataset
    complete_file = os.path.join(output_dir, "complete_election_data.json")
    with open(complete_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n✓ Saved complete data to: {complete_file}")
    
    # Save constituencies separately
    const_file = os.path.join(output_dir, "constituencies.json")
    with open(const_file, "w", encoding="utf-8") as f:
        json.dump(data["constituencies"], f, indent=2, ensure_ascii=False)
    print(f"✓ Saved constituencies to: {const_file}")
    
    # Save party totals separately
    party_file = os.path.join(output_dir, "party_totals.json")
    with open(party_file, "w", encoding="utf-8") as f:
        json.dump(data["party_totals"], f, indent=2, ensure_ascii=False)
    print(f"✓ Saved party totals to: {party_file}")
    
    # Save metadata separately
    meta_file = os.path.join(output_dir, "metadata.json")
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(data["metadata"], f, indent=2, ensure_ascii=False)
    print(f"✓ Saved metadata to: {meta_file}")
    
    # Also save as a single-line JSON (for programmatic loading)
    compact_file = os.path.join(output_dir, "election_data_compact.json")
    with open(compact_file, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(',', ':'), ensure_ascii=False)
    print(f"✓ Saved compact data to: {compact_file}")


def main():
    try:
        # Fetch all data
        data = fetch_all_data()
        
        # Save to JSON files
        save_data(data)
        
        # Print summary
        print("\n" + "=" * 70)
        print("  DATA EXPORT COMPLETE!")
        print("=" * 70)
        print(f"\n  Total Constituencies: {len(data['constituencies'])}")
        print(f"  Total Parties: {len(data['party_totals'])}")
        print(f"  Export Date: {data['metadata']['export_date']}")
        print(f"  ECI Last Update: {data['metadata']['last_updated']}")
        print("\n  Data saved in 'election_data' folder")
        print("  You can now use the offline mode in the main application")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()