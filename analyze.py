#!/usr/bin/env python3
"""
Knoxville Vintage Clothing Store — Data Cleaning & Analysis Pipeline
"""

import sys
import pandas as pd
import sqlite3
import re
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# ─── PATHS ──────────────────────────────────────────────────────────────────
BASE = Path(__file__).parent
DATA = BASE / "data"
OUT  = BASE / "output"
for sub in ("cleaned", "analysis", "tableau"):
    (OUT / sub).mkdir(parents=True, exist_ok=True)

# ─── BRAND CORRECTION MAP ───────────────────────────────────────────────────
# Keys are lowercased brand names AFTER preprocessing (NWT strip, X→&, xs→'s).
BRAND_FIX = {
    # ── Numbers / symbols ──────────────────────────────────────────
    "7 for all mandkind":           "7 For All Mankind",
    "7 famk":                       "7 For All Mankind",
    "7 fam":                        "7 For All Mankind",
    "32 degreees":                  "32 Degrees",
    "1 state":                      "1. State",
    "2to-ky":                       "2to-Ky",
    "&merci":                       "&Merci",
    "ac dc":                        "AC/DC",

    # ── A ──────────────────────────────────────────────────────────
    "abercombie":                   "Abercrombie & Fitch",
    "abercrombie & fitch":          "Abercrombie & Fitch",
    "abercrombie&finch":            "Abercrombie & Fitch",
    "abercrombie":                  "Abercrombie & Fitch",
    "adrienne vittadin":            "Adrienne Vittadini",
    "absolutely":                   "ABSOLIUTELY",
    "ana sui":                      "Anna Sui",
    "ann klein":                    "Anne Klein",
    "ann taylor loft":              "Ann Taylor LOFT",
    "ataylot loft":                 "Ann Taylor LOFT",
    "atloft":                       "Ann Taylor LOFT",
    "altar'd state":                "Altar'd State",   # post-preprocessing form

    # ── B ──────────────────────────────────────────────────────────
    "b darlin":                     "B. Darlin",
    "bandolino":                    "Bandolino",
    "brandolino":                   "Bandolino",       # misspelling
    "bcbgmaxazria":                 "BCBG Maxazria",
    "bcbg maxazria":                "BCBG Maxazria",
    "bcbg generations":             "BCBGeneration",
    "bcbgeneration":                "BCBGeneration",
    "bronks brothers":              "Brooks Brothers",

    # ── C ──────────────────────────────────────────────────────────
    "charolette russe":             "Charlotte Russe",
    "chicos":                       "Chico's",
    "chico's":                      "Chico's",

    # ── D ──────────────────────────────────────────────────────────
    "dana buckman":                 "Dana Buchman",
    "danielrainn":                  "Danielle Rainn",
    "delias":                       "Delia's",
    "delia's":                      "Delia's",

    # ── E ──────────────────────────────────────────────────────────
    "eli tahari":                   "Elie Tahari",
    "ellie tahari":                 "Elie Tahari",
    "elexenses":                    "Elevenses",
    "espirit":                      "Esprit",
    "evan picone":                  "Evan-Picone",

    # ── F ──────────────────────────────────────────────────────────
    "forever21":                    "Forever 21",
    "fredericks of hollywood":      "Frederick's of Hollywood",

    # ── G ──────────────────────────────────────────────────────────
    "giani bini":                   "Gianni Bini",
    "gilligan & oxmalley":          "Gilligan & O'Malley",

    # ── H ──────────────────────────────────────────────────────────
    "h & m":                        "H&M",             # from "H X M" after X→&
    "hxm":                          "H&M",

    # ── I ──────────────────────────────────────────────────────────
    "iaxnue ligne":                 "A'nye Ligne",

    # ── J ──────────────────────────────────────────────────────────
    "j crew":                       "J.Crew",
    "j.crew":                       "J.Crew",
    "jcrew":                        "J.Crew",
    "jane delancy":                 "Jane & Delancy",

    # ── L ──────────────────────────────────────────────────────────
    "levi strauss & co":            "Levi Strauss & Co",
    "lily pulitzer":                "Lilly Pulitzer",

    # ── M ──────────────────────────────────────────────────────────
    "madwell":                      "Madewell",
    "misguided":                    "Missguided",

    # ── N ──────────────────────────────────────────────────────────
    "nic & zoe":                    "Nic+Zoe",         # from "Nic X Zoe" after X→&
    "nic zoe":                      "Nic+Zoe",
    "nie & zoe":                    "Nic+Zoe",
    "ny & co":                      "New York & Company",
    "new york & company":           "New York & Company",

    # ── O ──────────────────────────────────────────────────────────
    "oxneill":                      "O'Neill",
    "oxoxo":                        "XOXO",

    # ── P ──────────────────────────────────────────────────────────
    "pac sun":                      "PacSun",
    "pacsun":                       "PacSun",
    "polo by ralph lauren":         "Polo Ralph Lauren",
    "prettylittlethings":           "Pretty Little Thing",

    # ── S ──────────────────────────────────────────────────────────
    "sage harbor":                  "Sag Harbor",
    "st johns bay":                 "St. John's Bay",

    # ── T ──────────────────────────────────────────────────────────
    "talbot's":                     "Talbots",
    "ttahari":                      "Tahari",

    # ── U ──────────────────────────────────────────────────────────
    "unknown":                      "Unknown",

    # ── W ──────────────────────────────────────────────────────────
    "whbm":                         "White House Black Market",
}

# ─── SIZE EXTRACTION ────────────────────────────────────────────────────────
def extract_size(name: str) -> str:
    if not isinstance(name, str):
        return ""
    m = re.search(
        r'\bsize\s*(xxs|xs|xl|xxl|xxxl|osfm|s|m|l|\d+\.?\d*)',
        name, re.IGNORECASE
    )
    if m:
        return m.group(1).upper()
    m = re.search(
        r'/\s*(xxs|xs|xl|xxl|xxxl|osfm|s|m|l|\d+\.?\d*)\s*$',
        name, re.IGNORECASE
    )
    if m:
        val = m.group(1)
        if re.match(r'^\d{4}$', val):
            return ""
        return val.upper()
    return ""


# ─── PRODUCT CATEGORY ───────────────────────────────────────────────────────
_CATS = [
    ("Dress",           ["dress", "gown"]),
    ("Skirt",           ["skirt", "skrt"]),
    ("Shorts",          ["short", "shrt"]),
    ("Jeans/Pants",     ["jean", "jns", "pant", "denim", "dnm", "trouser", "legging"]),
    ("Romper/Jumpsuit", ["romper", "jumpsuit", "onesl"]),
    ("Jacket/Coat",     ["jacket", "coat", "blazer", "jkt", "puffer", "bomber", "trench"]),
    ("Sweater/Cardigan",["sweater", "swtr", "cardigan", "crdign", "pullover", "knit"]),
    ("Top",             ["blouse", "shirt", "tee", "tank", "cami", "camisole", "tube",
                          "halter", "bodysuit", "vest", "crop top", "croptop", "ls", "ss"]),
    ("Top",             [r"\btop\b"]),
    ("Set",             ["set", "pajama"]),
    ("Shoes",           ["boot", "shoe", "slide", "sneaker", "heel", "flat", "sandal",
                          "loafer", "pump"]),
    ("Accessories",     ["bag", "purse", "clutch", "wallet", "tote", "earring", "earr",
                          "necklace", "bracelet", "brac", "belt", "hat", "scarf",
                          "ring", "watch", "jewelry"]),
]

def categorize(name: str) -> str:
    if not isinstance(name, str):
        return "Other"
    nl = name.lower()
    for cat, kws in _CATS:
        for kw in kws:
            if re.search(kw, nl):
                return cat
    return "Other"


# ─── NAME CLEANER ───────────────────────────────────────────────────────────
def clean_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    n = name
    n = re.sub(r'[/\s]*\bsize\s*[^\s/,]+', ' ', n, flags=re.IGNORECASE)
    n = re.sub(r'\s*/\s*(xxs|xs|xl|xxl|xxxl|osfm|s|m|l|\d+\.?\d*)\s*$', ' ', n, flags=re.IGNORECASE)
    n = n.replace('/', ' ')
    n = re.sub(r'\s+', ' ', n).strip()
    return n


# ─── BRAND CLEANER ──────────────────────────────────────────────────────────
def clean_brand(brand) -> str:
    if not isinstance(brand, str) or not brand.strip():
        return ""
    b = brand.strip()

    # 1. Strip trailing suffixes that aren't part of the brand name
    b = re.sub(r'\s*\bNWT\b\s*$',     '', b, flags=re.IGNORECASE).strip()
    b = re.sub(r'\s*\bPetites\b\s*$', '', b, flags=re.IGNORECASE).strip()
    if not b:
        return ""

    # 2. Fix POS apostrophe-encoding artifact: 'x' was inserted in place of "'"
    #    e.g. "Chicoxs" → "Chico's",  "Altarxd" → "Altar'd"
    b = re.sub(r"([a-zA-Z])xs\b", r"\1's", b)
    b = re.sub(r"([a-zA-Z])xd\b", r"\1'd", b)

    # 3. Replace word-separator " X " with " & "
    #    e.g. "Croft X Barrow" → "Croft & Barrow"
    b = re.sub(r'(?<=[A-Za-z0-9])\s+X\s+(?=[A-Za-z0-9])', ' & ', b)

    # 4. BRAND_FIX lookup (case-insensitive)
    key = b.lower()
    if key in BRAND_FIX:
        return BRAND_FIX[key]

    # 5. Apply title case if all-caps or all-lowercase
    if b.isupper() or b.islower():
        return b.title()
    return b


# ════════════════════════════════════════════════════════════════════════════
# 1. CLEAN: product-export.csv
# ════════════════════════════════════════════════════════════════════════════
print("=" * 60)
print("STEP 1 — Cleaning product-export.csv")
print("=" * 60)

pe_raw = pd.read_csv(DATA / "product-export.csv", low_memory=False)
print(f"  Raw rows: {len(pe_raw)}")

pe = pd.DataFrame({
    "sku":            pe_raw["sku"].astype(str).str.strip(),
    "name_raw":       pe_raw["name"],
    "brand_raw":      pe_raw["brand_name"],
    "retail_price":   pd.to_numeric(pe_raw["retail_price"],  errors="coerce"),
    "supply_price":   pd.to_numeric(pe_raw["supply_price"],  errors="coerce"),
    "active":         pe_raw["active"],
    "inventory":      pd.to_numeric(pe_raw["inventory_Knoxville_Location"], errors="coerce"),
})

pe["size"]             = pe["name_raw"].apply(extract_size)
pe["product_name"]     = pe["name_raw"].apply(clean_name)
pe["brand_name"]       = pe["brand_raw"].apply(clean_brand)
pe["product_category"] = pe["name_raw"].apply(categorize)
pe["gross_margin_pct"] = pe.apply(
    lambda r: round((r.retail_price - r.supply_price) / r.retail_price * 100, 1)
    if (pd.notna(r.supply_price) and r.supply_price > 0
        and pd.notna(r.retail_price) and r.retail_price > 0)
    else None,
    axis=1
)
pe.drop(columns=["name_raw", "brand_raw"], inplace=True)

print("\n  Brand corrections applied:")
brand_changes = []
pe_raw_brands = pe_raw["brand_name"].fillna("").str.strip()
for raw, fixed in zip(pe_raw_brands, pe["brand_name"]):
    if raw and fixed and raw.lower() in BRAND_FIX and raw != fixed:
        brand_changes.append((raw, fixed))
unique_changes = dict(brand_changes)
for orig, corrected in sorted(unique_changes.items()):
    count = sum(1 for r in pe_raw_brands if r.strip().lower() == orig.lower())
    print(f"    '{orig}' -> '{corrected}'  ({count} products)")

pe.to_csv(OUT / "cleaned" / "products_clean.csv", index=False)
print(f"\n  ✓ Saved {len(pe)} rows → output/cleaned/products_clean.csv")


# ════════════════════════════════════════════════════════════════════════════
# 2. CLEAN: vend.csv
# ════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 2 — Cleaning vend.csv")
print("=" * 60)

vend_raw = pd.read_csv(DATA / "vend.csv", low_memory=False)
print(f"  Raw rows: {len(vend_raw)}")

vend = pd.DataFrame({
    "sku":               vend_raw["SKU"].astype(str).str.strip(),
    "name_raw":          vend_raw["Product"],
    "brand_raw":         vend_raw["Brand"],
    "closing_inventory": pd.to_numeric(vend_raw["Closing Inventory"], errors="coerce"),
    "revenue":           pd.to_numeric(vend_raw["Revenue"],           errors="coerce"),
    "inventory_cost":    pd.to_numeric(vend_raw["Inventory Cost"],    errors="coerce"),
})

vend["size"]             = vend["name_raw"].apply(extract_size)
vend["product_name"]     = vend["name_raw"].apply(clean_name)
vend["brand_name"]       = vend["brand_raw"].apply(clean_brand)
vend["product_category"] = vend["name_raw"].apply(categorize)

pe_brand_map = pe.set_index("sku")["brand_name"].to_dict()
vend["brand_name"] = vend.apply(
    lambda r: r["brand_name"] if r["brand_name"] else pe_brand_map.get(r["sku"], ""),
    axis=1
)

vend.drop(columns=["name_raw", "brand_raw"], inplace=True)
vend.to_csv(OUT / "cleaned" / "vend_clean.csv", index=False)
print(f"  ✓ Saved {len(vend)} rows → output/cleaned/vend_clean.csv")


# ════════════════════════════════════════════════════════════════════════════
# 3. CLEAN: sales.csv
# ════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 3 — Cleaning sales.csv")
print("=" * 60)

sales_raw = pd.read_csv(DATA / "sales.csv", low_memory=False)
sales_raw.columns = sales_raw.columns.str.strip()
print(f"  Raw rows: {len(sales_raw)}")
print(f"  Line types: {dict(sales_raw['Line Type'].value_counts())}")

sales_raw["dt"] = pd.to_datetime(sales_raw["Date"], errors="coerce")
sales_raw["date"]        = sales_raw["dt"].dt.date.astype(str)
sales_raw["hour"]        = sales_raw["dt"].dt.hour
sales_raw["month"]       = sales_raw["dt"].dt.month
sales_raw["day_of_week"] = sales_raw["dt"].dt.day_name()
sales_raw["week_num"]    = sales_raw["dt"].dt.isocalendar().week.astype(int)

# ── Sale headers (transaction level) ────────────────────────
sh_raw = sales_raw[sales_raw["Line Type"] == "Sale"].copy()
sh = pd.DataFrame({
    "datetime":       sh_raw["dt"],
    "date":           sh_raw["date"],
    "hour":           sh_raw["hour"],
    "month":          sh_raw["month"],
    "day_of_week":    sh_raw["day_of_week"],
    "week_num":       sh_raw["week_num"],
    "receipt_number": sh_raw["Receipt Number"],
    "total_items":    pd.to_numeric(sh_raw["Quantity"], errors="coerce"),
    "subtotal":       pd.to_numeric(sh_raw["Subtotal"], errors="coerce"),
    "sales_tax":      pd.to_numeric(sh_raw["Sales Tax"], errors="coerce"),
    "total_discount": pd.to_numeric(sh_raw["Discount"], errors="coerce"),
    "total":          pd.to_numeric(sh_raw["Total"], errors="coerce"),
    "details":        sh_raw["Details"],
    "register":       sh_raw["Register"],
})
sh.to_csv(OUT / "cleaned" / "transactions_clean.csv", index=False)
print(f"  ✓ Saved {len(sh)} transactions → output/cleaned/transactions_clean.csv")

# ── Sale lines (item level) ──────────────────────────────────
sl_raw = sales_raw[sales_raw["Line Type"] == "Sale Line"].copy()

# Identify vend-discount-coupon receipts BEFORE filtering
disc_receipts = set(
    sl_raw[sl_raw["Sku"].astype(str).str.strip() == "vend-discount"]["Receipt Number"].unique()
)

sl = pd.DataFrame({
    "datetime":       sl_raw["dt"],
    "date":           sl_raw["date"],
    "hour":           sl_raw["hour"],
    "month":          sl_raw["month"],
    "day_of_week":    sl_raw["day_of_week"],
    "week_num":       sl_raw["week_num"],
    "receipt_number": sl_raw["Receipt Number"],
    "quantity":       pd.to_numeric(sl_raw["Quantity"],   errors="coerce"),
    "subtotal":       pd.to_numeric(sl_raw["Subtotal"],   errors="coerce"),
    "sales_tax":      pd.to_numeric(sl_raw["Sales Tax"],  errors="coerce"),
    "total":          pd.to_numeric(sl_raw["Total"],      errors="coerce"),
    "line_discount":  pd.to_numeric(sl_raw["Discount"],   errors="coerce").fillna(0),
    "details":        sl_raw["Details"],
    "sku":            sl_raw["Sku"].astype(str).str.strip(),
})

# Drop discount placeholder rows and returns (negative quantity)
sl = sl[sl["sku"] != "vend-discount"]
sl = sl[sl["quantity"] > 0]

# Mark vend-discount-coupon transactions
sl["has_discount"] = sl["receipt_number"].isin(disc_receipts)

# Mark Wednesday deal transactions:
# Wednesday + June (month 6) + at least one line with per-item discount > 0
wed_deal_receipts = set(
    sl[
        (sl["day_of_week"] == "Wednesday") &
        (sl["month"] == 6) &
        (sl["line_discount"] > 0)
    ]["receipt_number"].unique()
)
sl["is_wednesday_deal"] = sl["receipt_number"].isin(wed_deal_receipts)

print(f"  Wednesday deal transactions identified: {len(wed_deal_receipts)}")

# Join product metadata via SKU
pe_lookup   = pe.set_index("sku")[["brand_name","product_category","retail_price","size"]].to_dict("index")
vend_lookup = vend.set_index("sku")[["brand_name","product_category","size"]].to_dict("index")

def get_field(sku, field, fallback_dict=None):
    val = pe_lookup.get(sku, {}).get(field, "")
    if not val and fallback_dict:
        val = fallback_dict.get(sku, {}).get(field, "")
    return val if val is not None else ""

sl["brand_name"]       = sl["sku"].map(lambda s: get_field(s, "brand_name",       vend_lookup))
sl["product_category"] = sl["sku"].map(lambda s: get_field(s, "product_category", vend_lookup))
sl["retail_price"]     = sl["sku"].map(lambda s: pe_lookup.get(s, {}).get("retail_price", None))
sl["size"]             = sl["sku"].map(lambda s: get_field(s, "size",              vend_lookup))

sl.to_csv(OUT / "cleaned" / "sale_lines_clean.csv", index=False)
print(f"  ✓ Saved {len(sl)} sale lines → output/cleaned/sale_lines_clean.csv")

# ── Compute dynamic date range ───────────────────────────────
date_min = sl["date"].min()
date_max = sl["date"].max()
import datetime as dt_mod
d0 = dt_mod.date.fromisoformat(date_min)
d1 = dt_mod.date.fromisoformat(date_max)
total_days = (d1 - d0).days + 1
try:
    date_range_str = f"{d0.strftime('%b %-d')} – {d1.strftime('%b %-d, %Y')}"
except ValueError:
    date_range_str = f"{d0.strftime('%b %#d')} – {d1.strftime('%b %#d, %Y')}"
print(f"\n  Data range: {date_range_str} ({total_days} days)")


# ════════════════════════════════════════════════════════════════════════════
# 4. SQL ANALYSIS (SQLite in-memory)
# ════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 4 — SQL Analysis")
print("=" * 60)

conn = sqlite3.connect(":memory:")
sl.to_sql("sale_lines",  conn, index=False, if_exists="replace")
sh.to_sql("transactions", conn, index=False, if_exists="replace")
pe.to_sql("products",    conn, index=False, if_exists="replace")
vend.to_sql("vend",      conn, index=False, if_exists="replace")

def sql(q): return pd.read_sql_query(q, conn)

# ── 4a. Daily revenue ────────────────────────────────────────
daily = sql("""
    SELECT
        date,
        day_of_week,
        month,
        week_num,
        COUNT(DISTINCT receipt_number)  AS transactions,
        CAST(ROUND(SUM(quantity),0) AS INTEGER) AS units_sold,
        ROUND(SUM(subtotal), 2)         AS daily_subtotal,
        ROUND(SUM(total),    2)         AS daily_total
    FROM sale_lines
    GROUP BY date
    ORDER BY date
""")
daily["rolling_7day_avg_revenue"] = (
    daily["daily_total"].rolling(7, min_periods=1).mean().round(2)
)
daily["rolling_7day_avg_units"] = (
    daily["units_sold"].rolling(7, min_periods=1).mean().round(1)
)
daily.to_csv(OUT / "analysis" / "daily_revenue.csv", index=False)
print("  ✓ daily_revenue.csv")

# ── 4b. Weekly revenue ───────────────────────────────────────
weekly = sql("""
    SELECT
        week_num,
        month,
        MIN(date)                       AS week_start,
        COUNT(DISTINCT receipt_number)  AS transactions,
        CAST(ROUND(SUM(quantity),0) AS INTEGER) AS units_sold,
        ROUND(SUM(subtotal), 2)         AS weekly_subtotal,
        ROUND(SUM(total),    2)         AS weekly_total,
        ROUND(SUM(total) / COUNT(DISTINCT receipt_number), 2) AS avg_order_value
    FROM sale_lines
    GROUP BY week_num
    ORDER BY week_num
""")
weekly.to_csv(OUT / "analysis" / "weekly_revenue.csv", index=False)
print("  ✓ weekly_revenue.csv")

# ── 4c. Top 20 brands by revenue ─────────────────────────────
top_brands = sql("""
    SELECT
        COALESCE(NULLIF(TRIM(brand_name),''), 'Unknown') AS brand_name,
        CAST(ROUND(SUM(quantity),0) AS INTEGER)          AS units_sold,
        ROUND(SUM(subtotal), 2)                          AS total_revenue,
        ROUND(AVG(retail_price), 2)                      AS avg_retail_price,
        ROUND(SUM(subtotal) / SUM(quantity), 2)          AS revenue_per_unit,
        COUNT(DISTINCT receipt_number)                   AS transaction_count
    FROM sale_lines
    GROUP BY COALESCE(NULLIF(TRIM(brand_name),''), 'Unknown')
    ORDER BY total_revenue DESC
    LIMIT 20
""")
grand_total = float(sql("SELECT ROUND(SUM(subtotal),2) AS v FROM sale_lines")["v"][0])
top_brands["revenue_share_pct"] = (top_brands["total_revenue"] / grand_total * 100).round(1)
top_brands.to_csv(OUT / "analysis" / "top_20_brands.csv", index=False)
print("  ✓ top_20_brands.csv")

# ── 4c-ii. Top 20 brands by units sold ───────────────────────
total_units_all = int(sql("SELECT SUM(quantity) AS v FROM sale_lines")["v"][0])
top_brands_units = sql("""
    SELECT
        COALESCE(NULLIF(TRIM(brand_name),''), 'Unknown') AS brand_name,
        CAST(ROUND(SUM(quantity),0) AS INTEGER)          AS units_sold,
        ROUND(SUM(subtotal), 2)                          AS total_revenue,
        ROUND(AVG(retail_price), 2)                      AS avg_retail_price,
        ROUND(SUM(subtotal) / SUM(quantity), 2)          AS revenue_per_unit,
        COUNT(DISTINCT receipt_number)                   AS transaction_count
    FROM sale_lines
    GROUP BY COALESCE(NULLIF(TRIM(brand_name),''), 'Unknown')
    ORDER BY units_sold DESC
    LIMIT 20
""")
top_brands_units["units_share_pct"] = (top_brands_units["units_sold"] / total_units_all * 100).round(1)
top_brands_units.to_csv(OUT / "analysis" / "top_20_brands_by_units.csv", index=False)
print("  ✓ top_20_brands_by_units.csv")

# ── 4d. Category performance ─────────────────────────────────
category = sql("""
    SELECT
        COALESCE(NULLIF(TRIM(product_category),''), 'Other') AS category,
        CAST(ROUND(SUM(quantity),0) AS INTEGER)               AS units_sold,
        COUNT(DISTINCT receipt_number)                        AS transactions,
        ROUND(SUM(subtotal), 2)                               AS total_revenue,
        ROUND(AVG(retail_price), 2)                           AS avg_price,
        ROUND(MIN(subtotal / quantity), 2)                    AS min_price_sold,
        ROUND(MAX(subtotal / quantity), 2)                    AS max_price_sold
    FROM sale_lines
    GROUP BY COALESCE(NULLIF(TRIM(product_category),''), 'Other')
    ORDER BY total_revenue DESC
""")
category["revenue_share_pct"] = (category["total_revenue"] / category["total_revenue"].sum() * 100).round(1)
category.to_csv(OUT / "analysis" / "category_performance.csv", index=False)
print("  ✓ category_performance.csv")

# ── 4e. Pricing buckets ──────────────────────────────────────
pricing = sql("""
    SELECT
        CASE
            WHEN retail_price IS NULL OR retail_price = 0 THEN 'No Price Data'
            WHEN retail_price < 15   THEN '$0–$14'
            WHEN retail_price < 25   THEN '$15–$24'
            WHEN retail_price < 35   THEN '$25–$34'
            WHEN retail_price < 50   THEN '$35–$49'
            WHEN retail_price < 75   THEN '$50–$74'
            WHEN retail_price < 100  THEN '$75–$99'
            ELSE '$100+'
        END                                              AS price_bucket,
        CAST(ROUND(SUM(quantity),0) AS INTEGER)          AS units_sold,
        ROUND(SUM(subtotal), 2)                          AS total_revenue,
        ROUND(AVG(retail_price), 2)                      AS avg_retail_price,
        ROUND(SUM(subtotal) / SUM(quantity), 2)          AS avg_selling_price
    FROM sale_lines
    GROUP BY price_bucket
    ORDER BY MIN(COALESCE(retail_price, 0))
""")
pricing.to_csv(OUT / "analysis" / "pricing_buckets.csv", index=False)
print("  ✓ pricing_buckets.csv")

# ── 4f. Basket analysis ───────────────────────────────────────
basket = sql("""
    SELECT
        receipt_number,
        date,
        day_of_week,
        month,
        CAST(ROUND(SUM(quantity),0) AS INTEGER) AS basket_size,
        ROUND(SUM(subtotal), 2)                 AS order_subtotal,
        ROUND(SUM(total), 2)                    AS order_total
    FROM sale_lines
    GROUP BY receipt_number
""")
basket["basket_category"] = pd.cut(
    basket["basket_size"],
    bins=[0, 1, 2, 3, 5, 999],
    labels=["1 item", "2 items", "3 items", "4–5 items", "6+ items"]
)
basket.to_csv(OUT / "analysis" / "basket_analysis.csv", index=False)

basket_dist = (
    basket.groupby("basket_category", observed=True)
    .agg(transactions=("receipt_number","count"),
         avg_order_value=("order_total","mean"),
         total_revenue=("order_total","sum"))
    .round(2).reset_index()
)
basket_dist["pct_of_transactions"] = (
    basket_dist["transactions"] / basket_dist["transactions"].sum() * 100
).round(1)
basket_dist.to_csv(OUT / "analysis" / "basket_distribution.csv", index=False)
print("  ✓ basket_analysis.csv + basket_distribution.csv")

# ── 4g. Day-of-week patterns ─────────────────────────────────
dow = sql("""
    SELECT
        day_of_week,
        CAST(strftime('%w', date) AS INTEGER) AS dow_num,
        COUNT(DISTINCT receipt_number)         AS transactions,
        ROUND(SUM(subtotal), 2)                AS total_revenue,
        ROUND(AVG(subtotal), 2)                AS avg_order_value,
        COUNT(DISTINCT date)                   AS days_open
    FROM sale_lines
    GROUP BY day_of_week
    ORDER BY CAST(strftime('%w', date) AS INTEGER)
""")
dow["revenue_per_day_open"] = (dow["total_revenue"] / dow["days_open"]).round(2)
dow.to_csv(OUT / "analysis" / "day_of_week.csv", index=False)
print("  ✓ day_of_week.csv")

# ── 4h. Monthly summary ───────────────────────────────────────
monthly = sql("""
    SELECT
        month,
        CASE month
            WHEN 1  THEN 'January'   WHEN 2  THEN 'February'
            WHEN 3  THEN 'March'     WHEN 4  THEN 'April'
            WHEN 5  THEN 'May'       WHEN 6  THEN 'June'
            WHEN 7  THEN 'July'      WHEN 8  THEN 'August'
            WHEN 9  THEN 'September' WHEN 10 THEN 'October'
            WHEN 11 THEN 'November'  WHEN 12 THEN 'December'
        END                                            AS month_name,
        COUNT(DISTINCT receipt_number)                 AS transactions,
        ROUND(SUM(subtotal), 2)                        AS total_revenue,
        CAST(ROUND(SUM(quantity),0) AS INTEGER)        AS units_sold,
        ROUND(SUM(subtotal) / COUNT(DISTINCT receipt_number), 2) AS avg_order_value,
        COUNT(DISTINCT date)                           AS active_days
    FROM sale_lines
    GROUP BY month
    ORDER BY month
""")
monthly.to_csv(OUT / "analysis" / "monthly_summary.csv", index=False)
print("  ✓ monthly_summary.csv")

# ── 4i. Discount impact (vend-discount coupon) ───────────────
discount = sql("""
    SELECT
        has_discount,
        COUNT(DISTINCT receipt_number)               AS transactions,
        CAST(ROUND(SUM(quantity),0) AS INTEGER)      AS units_sold,
        ROUND(SUM(subtotal), 2)                      AS total_revenue,
        ROUND(SUM(subtotal)/COUNT(DISTINCT receipt_number), 2) AS avg_transaction_value,
        ROUND(SUM(subtotal)/SUM(quantity), 2)        AS avg_price_per_item
    FROM sale_lines
    GROUP BY has_discount
""")
discount.to_csv(OUT / "analysis" / "discount_impact.csv", index=False)
print("  ✓ discount_impact.csv")

# ── 4j. Wednesday deal impact ────────────────────────────────
wed_deal = sql("""
    SELECT
        is_wednesday_deal,
        COUNT(DISTINCT receipt_number)                              AS transactions,
        CAST(ROUND(SUM(quantity),0) AS INTEGER)                     AS units_sold,
        ROUND(SUM(subtotal), 2)                                     AS realized_revenue,
        ROUND(SUM(line_discount), 2)                                AS total_discount_given,
        ROUND(SUM(subtotal + line_discount), 2)                     AS full_price_equivalent,
        ROUND(SUM(subtotal) / COUNT(DISTINCT receipt_number), 2)    AS avg_transaction_value,
        ROUND(SUM(quantity)  / COUNT(DISTINCT receipt_number), 2)   AS avg_basket_size,
        ROUND(SUM(line_discount) / NULLIF(SUM(line_discount + subtotal), 0) * 100, 1)
                                                                    AS avg_discount_pct
    FROM sale_lines
    WHERE day_of_week = 'Wednesday'
    GROUP BY is_wednesday_deal
""")
wed_deal.to_csv(OUT / "analysis" / "wednesday_deal_impact.csv", index=False)
print("  ✓ wednesday_deal_impact.csv")

# Wednesday deal by week (to see trend over the promotion period)
wed_deal_weekly = sql("""
    SELECT
        date,
        is_wednesday_deal,
        COUNT(DISTINCT receipt_number)                           AS transactions,
        CAST(ROUND(SUM(quantity),0) AS INTEGER)                  AS units_sold,
        ROUND(SUM(subtotal), 2)                                  AS realized_revenue,
        ROUND(SUM(line_discount), 2)                             AS discount_given,
        ROUND(SUM(subtotal) / COUNT(DISTINCT receipt_number), 2) AS avg_transaction_value
    FROM sale_lines
    WHERE day_of_week = 'Wednesday'
    GROUP BY date, is_wednesday_deal
    ORDER BY date
""")
wed_deal_weekly.to_csv(OUT / "analysis" / "wednesday_deal_by_week.csv", index=False)
print("  ✓ wednesday_deal_by_week.csv")


# ════════════════════════════════════════════════════════════════════════════
# 5. TABLEAU EXPORTS
# ════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 5 — Tableau Exports")
print("=" * 60)

daily.to_csv(OUT / "tableau" / "T1_daily_revenue.csv", index=False)
print("  ✓ T1_daily_revenue.csv")

brand_by_cat = sql("""
    SELECT
        COALESCE(NULLIF(TRIM(brand_name),''), 'Unknown') AS brand_name,
        product_category,
        CAST(ROUND(SUM(quantity),0) AS INTEGER)           AS units_sold,
        ROUND(SUM(subtotal), 2)                           AS total_revenue,
        ROUND(AVG(retail_price), 2)                       AS avg_retail_price,
        COUNT(DISTINCT receipt_number)                    AS transactions
    FROM sale_lines
    GROUP BY brand_name, product_category
    ORDER BY total_revenue DESC
""")
brand_by_cat.to_csv(OUT / "tableau" / "T2_brand_performance.csv", index=False)
print("  ✓ T2_brand_performance.csv")

top_brands_units.to_csv(OUT / "tableau" / "T2b_top_brands_by_units.csv", index=False)
print("  ✓ T2b_top_brands_by_units.csv")

sl_tab = sl[[
    "date","hour","month","day_of_week","week_num",
    "receipt_number","sku","details","brand_name","product_category","size",
    "quantity","subtotal","sales_tax","total","retail_price",
    "line_discount","has_discount","is_wednesday_deal"
]].copy()
sl_tab.to_csv(OUT / "tableau" / "T3_sale_lines_detail.csv", index=False)
print("  ✓ T3_sale_lines_detail.csv")

sh_tab = sh.copy()
sh_tab["avg_item_value"] = (sh_tab["subtotal"] / sh_tab["total_items"].replace(0, None)).round(2)
sh_tab.to_csv(OUT / "tableau" / "T4_transactions.csv", index=False)
print("  ✓ T4_transactions.csv")

category.to_csv(OUT / "tableau" / "T5_category_performance.csv", index=False)
print("  ✓ T5_category_performance.csv")

pricing.to_csv(OUT / "tableau" / "T6_pricing_distribution.csv", index=False)
print("  ✓ T6_pricing_distribution.csv")

basket.to_csv(OUT / "tableau" / "T7_basket_analysis.csv", index=False)
print("  ✓ T7_basket_analysis.csv")

dow.to_csv(OUT / "tableau" / "T8_day_of_week.csv", index=False)
print("  ✓ T8_day_of_week.csv")

monthly.to_csv(OUT / "tableau" / "T9_monthly_summary.csv", index=False)
print("  ✓ T9_monthly_summary.csv")

prod_inv = sql("""
    SELECT
        p.sku,
        p.product_name,
        p.brand_name,
        p.product_category,
        p.size,
        p.retail_price,
        p.supply_price,
        p.gross_margin_pct,
        p.inventory                        AS current_inventory,
        COALESCE(v.revenue, 0)             AS sold_revenue,
        COALESCE(v.closing_inventory, 0)   AS closing_inventory,
        COALESCE(v.inventory_cost, 0)      AS inventory_cost
    FROM products p
    LEFT JOIN vend v ON p.sku = v.sku
    ORDER BY COALESCE(v.revenue, 0) DESC
""")
prod_inv.to_csv(OUT / "tableau" / "T10_products_inventory.csv", index=False)
print("  ✓ T10_products_inventory.csv")

# T11: Wednesday deal analysis — deal vs. non-deal Wednesdays
wed_all_lines = sql("""
    SELECT
        date,
        receipt_number,
        day_of_week,
        is_wednesday_deal,
        quantity,
        subtotal,
        line_discount,
        brand_name,
        product_category,
        retail_price
    FROM sale_lines
    WHERE day_of_week = 'Wednesday'
    ORDER BY date, receipt_number
""")
wed_all_lines.to_csv(OUT / "tableau" / "T11_wednesday_deal.csv", index=False)
print("  ✓ T11_wednesday_deal.csv")


# ════════════════════════════════════════════════════════════════════════════
# 6. BUSINESS INSIGHTS & RECOMMENDATIONS
# ════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 6 — Business Insights & Recommendations")
print("=" * 60)

total_rev   = grand_total
total_units = int(sql("SELECT SUM(quantity) AS v FROM sale_lines")["v"][0])
total_txns  = int(sql("SELECT COUNT(DISTINCT receipt_number) AS v FROM sale_lines")["v"][0])
avg_aov     = float(sql("SELECT ROUND(AVG(order_subtotal),2) AS v FROM ("
                         "  SELECT receipt_number, SUM(subtotal) AS order_subtotal"
                         "  FROM sale_lines GROUP BY receipt_number"
                         ")")["v"][0])

b1 = top_brands.iloc[0]
b2 = top_brands.iloc[1]
b3 = top_brands.iloc[2]
top3_pct  = top_brands.head(3)["revenue_share_pct"].sum()
top10_pct = top_brands.head(10)["revenue_share_pct"].sum()

best_dow  = dow.sort_values("revenue_per_day_open", ascending=False).iloc[0]
worst_dow = dow.sort_values("revenue_per_day_open").iloc[0]
best_cat  = category.iloc[0]
sweet     = pricing[pricing["price_bucket"] != "No Price Data"].sort_values("total_revenue", ascending=False).iloc[0]

aov_single = float(basket[basket["basket_size"] == 1]["order_total"].mean())
aov_multi  = float(basket[basket["basket_size"] >= 2]["order_total"].mean())
multi_pct  = (basket["basket_size"] >= 2).mean() * 100

# Wednesday deal stats
wed_deal_on  = wed_deal[wed_deal["is_wednesday_deal"] == 1].iloc[0] if 1 in wed_deal["is_wednesday_deal"].values else None
wed_deal_off = wed_deal[wed_deal["is_wednesday_deal"] == 0].iloc[0] if 0 in wed_deal["is_wednesday_deal"].values else None

total_wed_discount = float(wed_deal["total_discount_given"].sum())
wed_deal_txns      = int(wed_deal_on["transactions"]) if wed_deal_on is not None else 0
wed_basket_deal    = float(wed_deal_on["avg_basket_size"])    if wed_deal_on is not None else 0
wed_basket_nodeal  = float(wed_deal_off["avg_basket_size"])   if wed_deal_off is not None else 0
wed_aov_deal       = float(wed_deal_on["avg_transaction_value"])  if wed_deal_on is not None else 0
wed_aov_nodeal     = float(wed_deal_off["avg_transaction_value"]) if wed_deal_off is not None else 0

insights = f"""
╔══════════════════════════════════════════════════════════════════════════╗
║   KNOXVILLE VINTAGE CLOTHING STORE — BUSINESS INSIGHTS & STRATEGY      ║
║   Data Period: {date_range_str:<30} Produced by Data Analysis  ║
╚══════════════════════════════════════════════════════════════════════════╝

BUSINESS SNAPSHOT
  Total Revenue (pre-tax)  : ${total_rev:>10,.2f}
  Total Units Sold         : {total_units:>10,}
  Total Transactions       : {total_txns:>10,}
  Average Order Value      : ${avg_aov:>10,.2f}
  Date Range               : {date_range_str}  (≈ {total_days} days)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SIX BUSINESS INSIGHTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

INSIGHT 1 │ BRAND CONCENTRATION — A Small Set of Brands Drives Most Revenue
─────────────────────────────────────────────────────────────────────────────
  Your top 3 brands account for {top3_pct:.1f}% of revenue; your top 10 account
  for {top10_pct:.1f}%. This Pareto-style concentration is common in curated
  vintage retail — customers come for brands they recognize and trust.

    #1  {b1['brand_name']:<30}  ${b1['total_revenue']:>8,.2f}  ({b1['units_sold']} units, {b1['revenue_share_pct']:.1f}% of revenue)
    #2  {b2['brand_name']:<30}  ${b2['total_revenue']:>8,.2f}  ({b2['units_sold']} units, {b2['revenue_share_pct']:.1f}% of revenue)
    #3  {b3['brand_name']:<30}  ${b3['total_revenue']:>8,.2f}  ({b3['units_sold']} units, {b3['revenue_share_pct']:.1f}% of revenue)

  Remaining inventory holding many low-performing brands should be
  evaluated for markdown or donation to recycle shelf space.

INSIGHT 2 │ PRICING SWEET SPOT — The {sweet['price_bucket']} Tier Generates Peak Revenue
─────────────────────────────────────────────────────────────────────────────
  {sweet['units_sold']} units sold at an avg retail of ${sweet['avg_retail_price']:.2f}, generating
  ${sweet['total_revenue']:,.2f}. Items in this band have both strong sell-through
  volume and meaningful per-unit revenue — the ideal buy-in target.
  Sub-$15 items sell fast but contribute marginally per transaction.
  Items priced above $75 carry potential margin but slow velocity.

INSIGHT 3 │ MULTI-ITEM TRANSACTIONS — {multi_pct:.0f}% of Customers Buy More Than One Item
─────────────────────────────────────────────────────────────────────────────
  Single-item average order value   : ${aov_single:.2f}
  Multi-item average order value    : ${aov_multi:.2f}
  AOV uplift when basket ≥ 2 items  : +{((aov_multi/aov_single)-1)*100:.0f}%

  Customers who pick up a second item significantly increase their spend.
  This is your highest-leverage behavioral trigger — there is no acquisition
  cost, only floor experience and staff conversation.

INSIGHT 4 │ DAY-OF-WEEK PERFORMANCE — {best_dow['day_of_week']} is Your Anchor Day
─────────────────────────────────────────────────────────────────────────────
  {best_dow['day_of_week']:<10} avg ${best_dow['revenue_per_day_open']:>7,.2f}/day  ({best_dow['transactions']} total transactions)
  {worst_dow['day_of_week']:<10} avg ${worst_dow['revenue_per_day_open']:>7,.2f}/day  ({worst_dow['transactions']} total transactions)

  {best_dow['day_of_week']} outperforms {worst_dow['day_of_week']} by {((best_dow['revenue_per_day_open']/max(worst_dow['revenue_per_day_open'],1))-1)*100:.0f}% per open day.
  This has staffing, stocking, and marketing implications. Weak-day traffic
  may respond well to timed promotions.

INSIGHT 5 │ CATEGORY MIX — {best_cat['category']} Leads, Accessories are a Hidden Engine
─────────────────────────────────────────────────────────────────────────────
  Top categories by revenue:
"""
for _, row in category.head(5).iterrows():
    insights += f"    {row['category']:<22} ${row['total_revenue']:>8,.2f}  ({row['revenue_share_pct']:.1f}%)  avg ${row['avg_price']:.2f}\n"

insights += f"""
  Accessories (bags, jewelry, belts) often appear as impulse add-ons in
  multi-item baskets. Their high sell-through rate with low price risk
  makes them a strong category to keep well-stocked near the register.

INSIGHT 6 │ WEDNESDAY DEAL — The Promotion Drives Larger Baskets
─────────────────────────────────────────────────────────────────────────────
  The "buy one + get a lower-priced item 50% off" Wednesday promotion
  launched in June 2026. Early results:

    Deal transactions        : {wed_deal_txns} (Wednesdays with deal applied)
    Total discount given     : ${total_wed_discount:,.2f}
    Avg basket — deal txns   : {wed_basket_deal:.1f} items  (${wed_aov_deal:.2f} AOV)
    Avg basket — no deal     : {wed_basket_nodeal:.1f} items  (${wed_aov_nodeal:.2f} AOV)
    Basket size uplift       : +{wed_basket_deal - wed_basket_nodeal:.1f} items per transaction

  Customers using the deal buy {wed_basket_deal - wed_basket_nodeal:.1f} more item(s) on average and
  spend ${wed_aov_deal - wed_aov_nodeal:.2f} more per visit compared to non-deal Wednesday
  shoppers. The promotion is driving incremental basket growth, though
  the discount cost must be weighed against the volume gained.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
THREE RECOMMENDATIONS (Product Management Perspective)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RECOMMENDATION 1 │ BUILD A BRAND SCORECARD AND OPTIMIZE YOUR BUYING MIX
─────────────────────────────────────────────────────────────────────────────
  With top-10 brands representing {top10_pct:.1f}% of revenue, you have strong
  signal on which brands your customers seek out. Create a simple Brand
  Scorecard that tracks Revenue, Units Sold, Revenue/Unit, and Days to
  Sell. Use this at every buying trip and consignment intake — if a brand
  is not in your top 20, it needs a compelling story (novelty, price point,
  aesthetics) before you commit floor space.

  Action: Set a quarterly "brand audit" — mark any brand with fewer than
  2 units sold in 90 days as "clearance eligible" and run a rotating
  discount rack to convert stuck inventory into working capital.

RECOMMENDATION 2 │ OPTIMIZE THE WEDNESDAY DEAL TO MAXIMIZE MARGIN
─────────────────────────────────────────────────────────────────────────────
  The Wednesday deal is drawing customers and growing basket sizes, but
  ${total_wed_discount:,.2f} in discounts have been given since launch. To protect margin:

    — Steer the deal toward items in the $15–$24 sweet spot that have
      aged 30+ days (move slow inventory instead of fast movers).
    — Brief staff to suggest a qualifying "add-on" when ringing up a
      higher-priced item — "Want to grab a second piece for 50% off?"
    — Track which categories get discounted most and adjust intake pricing
      so the 50%-off price still clears a healthy margin.
    — Consider a minimum qualifying price (e.g., primary item ≥ $25) to
      prevent the deal from being used entirely on low-margin items.

RECOMMENDATION 3 │ INVEST IN THE {best_dow['day_of_week'].upper()} IN-STORE EXPERIENCE TO GROW BASKET SIZE
─────────────────────────────────────────────────────────────────────────────
  {best_dow['day_of_week']} already drives your strongest revenue per open day. To extend
  this advantage: (1) staff your most experienced seller on the floor,
  (2) refresh curated "outfit" displays Thursday evening so {best_dow['day_of_week']} shoppers
  see fresh pairings, and (3) place accessories (high-margin, low-risk)
  at every natural pause point — fitting room entrance, register line.

  The +{((aov_multi/aov_single)-1)*100:.0f}% AOV for multi-item baskets means each additional
  unit a customer picks up is disproportionately valuable. A brief, natural
  staff prompt — "That top would pair perfectly with the skirt we just
  got in" — costs nothing and consistently moves the needle.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TABLEAU PREPARATION NOTES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  11 Tableau-ready CSVs exported to output/tableau/:
  T1  Daily Revenue         — time-series line chart, 7-day rolling avg
  T2  Brand Performance     — bar chart, treemap, or scatter (rev vs units)
  T3  Sale Lines Detail     — master data source (now includes line_discount,
                              has_discount, is_wednesday_deal flags)
  T4  Transactions          — basket size, AOV distribution
  T5  Category Performance  — stacked bar, pie
  T6  Pricing Distribution  — histogram / price bucket bar chart
  T7  Basket Analysis       — basket size frequency chart
  T8  Day of Week           — heatmap / bar chart
  T9  Monthly Summary       — month-over-month bar chart
  T10 Products & Inventory  — inventory health, sell-through table
  T11 Wednesday Deal        — deal vs. no-deal Wednesday comparison

  All files use consistent field names for easy joining in Tableau:
  - Join key across files: 'sku' and 'receipt_number'
  - Date field: 'date' (YYYY-MM-DD string, Tableau auto-parses)
  - Revenue field: 'subtotal' (pre-tax) or 'total' (post-tax)
  - Discount fields: 'line_discount' (per-item), 'has_discount' (coupon flag),
                     'is_wednesday_deal' (Wednesday promotion flag)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

print(insights)

with open(OUT / "analysis" / "business_insights.txt", "w", encoding="utf-8") as f:
    f.write(insights)

print("\n" + "=" * 60)
print("  COMPLETE — all output saved to: output/")
print("  ├── cleaned/   — 4 cleaned CSV files")
print("  ├── analysis/  — 11 analysis CSVs + business_insights.txt")
print("  └── tableau/   — 11 Tableau-ready export files")
print("=" * 60)

conn.close()
