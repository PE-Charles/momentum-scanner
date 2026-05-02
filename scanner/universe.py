"""
Hardcoded starter universe of Canadian small-cap tickers.
Covers TSXV, CSE, NEO, and TSX small-caps across multiple sectors.
Excludes pure mining explorers.

yfinance suffix conventions:
  .TO  = TSX
  .V   = TSXV
  .CN  = CSE (also used for some NEO listings)
  .NE  = NEO Exchange

Last cleaned: 2026-04-18 — removed 20 delisted/invalid tickers.
"""

UNIVERSE = [
    # --- Security / Defense ---
    {"ticker": "ZDC.V", "yf_ticker": "ZDC.V", "name": "Zedcor Inc.", "exchange": "TSXV", "sector": "Security"},
    {"ticker": "PNG.V", "yf_ticker": "PNG.V", "name": "Kraken Robotics Inc.", "exchange": "TSXV", "sector": "Defense"},

    # --- Advanced Materials / Clean Tech ---
    {"ticker": "HG.CN", "yf_ticker": "HG.CN", "name": "HydroGraph Clean Power Inc.", "exchange": "CSE", "sector": "Clean Energy"},

    # --- Retail / Consumer ---
    {"ticker": "GRGD.TO", "yf_ticker": "GRGD.TO", "name": "Groupe Dynamite Inc.", "exchange": "TSX", "sector": "Retail"},

    # --- Industrials ---
    {"ticker": "HPS-A.TO", "yf_ticker": "HPS-A.TO", "name": "Hammond Power Solutions Inc.", "exchange": "TSX", "sector": "Industrials"},

    # --- Fintech ---
    {"ticker": "PRL.TO", "yf_ticker": "PRL.TO", "name": "Propel Holdings Inc.", "exchange": "TSX", "sector": "Fintech"},
    {"ticker": "EQB.TO", "yf_ticker": "EQB.TO", "name": "EQB Inc.", "exchange": "TSX", "sector": "Fintech"},

    # --- Tech / SaaS ---
    {"ticker": "WELL.TO", "yf_ticker": "WELL.TO", "name": "WELL Health Technologies Corp.", "exchange": "TSX", "sector": "Healthcare Tech"},
    {"ticker": "MDA.TO", "yf_ticker": "MDA.TO", "name": "MDA Space Ltd.", "exchange": "TSX", "sector": "Aerospace"},
    {"ticker": "STC.TO", "yf_ticker": "STC.TO", "name": "Sangoma Technologies Corp.", "exchange": "TSX", "sector": "Tech"},
    {"ticker": "DCBO.TO", "yf_ticker": "DCBO.TO", "name": "Docebo Inc.", "exchange": "TSX", "sector": "Tech"},
    {"ticker": "KXS.TO", "yf_ticker": "KXS.TO", "name": "Kinaxis Inc.", "exchange": "TSX", "sector": "Tech"},
    {"ticker": "DND.TO", "yf_ticker": "DND.TO", "name": "Dye & Durham Ltd.", "exchange": "TSX", "sector": "Tech"},
    {"ticker": "ENGH.TO", "yf_ticker": "ENGH.TO", "name": "Enghouse Systems Ltd.", "exchange": "TSX", "sector": "Tech"},
    {"ticker": "LSPD.TO", "yf_ticker": "LSPD.TO", "name": "Lightspeed Commerce Inc.", "exchange": "TSX", "sector": "Tech"},

    # --- Crypto / Digital Assets ---
    {"ticker": "HUT.TO", "yf_ticker": "HUT.TO", "name": "Hut 8 Corp.", "exchange": "TSX", "sector": "Crypto"},
    {"ticker": "BITF.TO", "yf_ticker": "BITF.TO", "name": "Bitfarms Ltd.", "exchange": "TSX", "sector": "Crypto"},
    {"ticker": "GLXY.TO", "yf_ticker": "GLXY.TO", "name": "Galaxy Digital Holdings Ltd.", "exchange": "TSX", "sector": "Crypto"},

    # --- Cannabis ---
    {"ticker": "TLRY.TO", "yf_ticker": "TLRY.TO", "name": "Tilray Brands Inc.", "exchange": "TSX", "sector": "Cannabis"},
    {"ticker": "OGI.TO", "yf_ticker": "OGI.TO", "name": "Organigram Holdings Inc.", "exchange": "TSX", "sector": "Cannabis"},
    {"ticker": "WEED.TO", "yf_ticker": "WEED.TO", "name": "Canopy Growth Corp.", "exchange": "TSX", "sector": "Cannabis"},
    {"ticker": "CRON.TO", "yf_ticker": "CRON.TO", "name": "Cronos Group Inc.", "exchange": "TSX", "sector": "Cannabis"},

    # --- Clean Energy ---
    {"ticker": "PEAK.V", "yf_ticker": "PEAK.V", "name": "Sun Peak Metals Corp.", "exchange": "TSXV", "sector": "Clean Energy"},
    {"ticker": "HURA.TO", "yf_ticker": "HURA.TO", "name": "Global X Uranium ETF", "exchange": "TSX", "sector": "Energy"},

    # --- Fintech / Financial Services ---
    {"ticker": "GDI.TO", "yf_ticker": "GDI.TO", "name": "GDI Integrated Facility Services Inc.", "exchange": "TSX", "sector": "Industrials"},
    {"ticker": "AIF.TO", "yf_ticker": "AIF.TO", "name": "Altus Group Ltd.", "exchange": "TSX", "sector": "Real Estate Tech"},
    {"ticker": "REAL.TO", "yf_ticker": "REAL.TO", "name": "Real Matters Inc.", "exchange": "TSX", "sector": "Real Estate Tech"},

    # --- TSXV/CSE small-caps ---
    {"ticker": "FOBI.V", "yf_ticker": "FOBI.V", "name": "Fobi AI Inc.", "exchange": "TSXV", "sector": "Tech"},
    {"ticker": "CSTR.V", "yf_ticker": "CSTR.V", "name": "CarbonStream Inc.", "exchange": "TSXV", "sector": "Clean Tech"},
    {"ticker": "CBIT.V", "yf_ticker": "CBIT.V", "name": "Cathedra Bitcoin Inc.", "exchange": "TSXV", "sector": "Crypto"},
]
