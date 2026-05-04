# 🗳️ Tamil Nadu Election 2026 Live Results Monitor

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)]()

A comprehensive real-time election results monitoring application for the Tamil Nadu Assembly Election 2026. Fetches live data from the Election Commission of India (ECI) website and provides detailed analytics, visualizations, and candidate information with photo caching.

## 📋 Table of Contents

- [✨ Features](#-features)
- [🚀 Quick Start](#-quick-start)
- [📦 Dependencies](#-dependencies)
- [🎯 Usage Guide](#-usage-guide)
- [📁 File Structure](#-file-structure)
- [🔧 Configuration](#-configuration)
- [📊 Data Source](#-data-source)
- [📈 Reporting Methods](#-reporting-methods)
- [🛠️ Building Standalone EXE](#️-building-standalone-exe)
- [🐛 Troubleshooting](#-troubleshooting)
- [📊 Statistical Analysis Features](#-statistical-analysis-features)
- [🖼️ Photo Caching System](#️-photo-caching-system)
- [📄 PDF Export Details](#-pdf-export-details)
- [⚙️ Technical Architecture](#️-technical-architecture)
- [🤝 Contributing](#-contributing)
- [⚠️ Disclaimer](#️-disclaimer)
- [📧 Contact & Support](#-contact--support)
- [🎯 Roadmap](#-roadmap)

## ✨ Features

### 📊 **Real-time Results Monitoring**
- Live fetching of constituency-wise results from ECI (234 constituencies)
- Auto-refresh with configurable intervals (30s, 60s, 120s, 300s)
- Last updated timestamp from ECI with countdown timer
- Parallel fetching for faster data retrieval (20+ concurrent threads)

### 🏛️ **Comprehensive Analysis**
- **Summary Dashboard**: Overall seat tally (234 total), majority mark tracking (118 seats), party-wise standings with visual bar charts
- **Interactive Charts**: Pie charts, bar charts, margin distribution histogram, status donut (matplotlib powered)
- **Statistical Deep-Dive**: Average margins, median margins, alliance-wise breakdown, top 15 winning margins
- **Party-wise Analysis**: Won vs Leading vs Trailing seats with color-coded display
- **Alliance Tracking**: INDIA/DMK Front, NDA/BJP Front, AIADMK, Others

### 👥 **Candidate Information System**
- **All Participants View**: Complete list of all 2000+ candidates across all constituencies
- **Candidate Photo Cache**: Automatic scraping and local storage of candidate photos in SQLite database
- Click on any candidate row to instantly view their photo
- Photo status indicator showing download progress and cache statistics
- Supports NOTA entries and independent candidates

### 🔍 **Advanced Filtering & Search**
- **Global Search**: Search across all tabs (constituencies, candidates, parties)
- **Party Filter**: Filter by any political party (TVK, DMK, AIADMK, BJP, INC, PMK, VCK, CPI, CPI(M), DMDK, AMMK, IUML, IND)
- **Margin Range Filters**: Close (<500), Tight (<2000), Comfortable (>5000), Big (>15000)
- **Result Status Filter**: Won, Leading, Trailing, NOTA
- **Assembly Filter**: Filter participants by specific constituency
- **Close Contests Tab**: Automatically shows all margins under 2000 votes
- **Notable Constituencies Tab**: Pre-defined key seats with context (CM seat, OPS contest, etc.)

### 📈 **Statistical Insights (8+ Charts)**
1. **Margin Distribution Histogram**: Binned margins (<500, 500-2k, 2k-5k, 5k-10k, 10k-20k, >20k)
2. **Cumulative Percentage Chart**: Shows what percentage of seats fall under each margin threshold
3. **Alliance-wise Pie Chart**: Seat share by political alliance
4. **Margin Box Plots**: Distribution by party (requires minimum 3 seats)
5. **Won vs Leading Stacked Bar**: Top 10 parties comparison
6. **Margin vs Constituency Scatter**: Identify patterns across constituency numbers
7. **Top 15 Margins**: Horizontal bar chart of largest victory margins
8. **Result Status Donut**: Declared vs In Progress vs No Data

### 📄 **PDF Export System**
- **Tab-specific Export**: Export any active tab as professional PDF
- **Summary Export**: Includes metric cards + party tally bar chart
- **Charts Export**: All 4 charts (pie, bar, margin hist, donut) in 2 pages
- **Stats Export**: All 6 statistical charts (2 per page, 3 pages total)
- **Treeview Export**: Any table tab (Party-wise, Constituencies, Close Contests, Notable, Participants)
- **ReportLab Formatting**: Professional headers, alternating row colors, metadata (timestamp, filters applied)

### 🖼️ **Automatic Photo Caching**
- Scrapes all 234 candidateswise pages
- Extracts images from `<div class='cand-box'>` structure
- Downloads high-quality candidate photos
- Stores in SQLite database with metadata
- Progress tracking with status updates
- Cancellable download process
- Persistent cache between sessions
- 20 concurrent download threads for speed

### 🔄 **Data Fetching Architecture**
- **Multi-stage Scraping**:
  1. Party index page parsing (partywiseleadresult-S22.htm)
  2. Lead pages for in-progress results
  3. Win pages for declared results
  4. Constituency pages for trailing candidates
  5. Candidate pages for all participants and photos
- **Concurrent Processing**: 20+ threads for parallel page fetching
- **Smart Caching**: Only fetches new/changed data
- **Error Resilience**: Graceful handling of missing pages or timeouts

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- Internet connection (for fetching live data)
- 500MB free disk space (for dependencies and photo cache)

### Method 1: One-Click Launcher (Recommended for End Users)

```bash
# Download these two files in the same folder:
# - launch_app.py
# - tn_election_monitor.py

# Run the launcher (auto-installs all dependencies)
python launch_app.py

https://github.com/kirubanandem/TN26ElectionResults
