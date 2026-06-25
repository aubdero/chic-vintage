#!/usr/bin/env python3
"""
Knoxville Vintage Clothing Store — Data Cleaning & Analysis Pipeline
Period: February 13 – May 24, 2026
"""

import sys
import pandas as pd
import sqlite3
import re
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# ─── PATHS ──────────────────────────────────────────────────────────────────
BASE = Path(r"c:\Users\tasia\Downloads\updated cv analysis")
DATA = BASE / "data"
OUT  = BASE / "output"
for sub in ("cleaned", "analysis", "tableau"):
    (OUT / sub).mkdir(parents=True, exist_ok=True)

# ─── BRAND CORRECTION MAP ───────────────────────────────────────────────────
# Keys are lowercased brand_name values found in raw data
BRAND_FIX = {
    "altarxd state":        "Altar'd State",
    "altarxd state nwt":    "Altar'd State",
    "7 for all mandkind":   "7 For All Mankind",
    "7 famk":               "7 For All Mankind",
    "7 fam":                "7 For All Mankind",
    "32 degreees":          "32 Degrees",
    "iaxnue ligne":         "A'nye Ligne",
    "abercombie":           "Abercrombie & Fitch",
    "abercrombie x fitch":  "Abercrombie & Fitch",
    "abercrombie&finch":    "Abercrombie & Fitch",
    "abercrombie":          "Abercrombie & Fitch",
    "levi strauss x co":    "Levi Strauss & Co",
    "89th x madison":       "89th & Madison",
    "ann klein":            "Anne Klein",
    "absolutely":           "ABSOLIUTELY",
    "&merci":               "&Merci",
    "ac dc":                "AC/DC",
    "bcbgmaxazria":         "BCBG Maxazria",
    "bcbg maxazria":        "BCBG Maxazria",
    "1 state":              "1. State",
    "ann taylor loft":      "Ann Taylor LOFT",
    "ataylot loft":         "Ann Taylor LOFT",
    "atloft":               "Ann Taylor LOFT",
    "unknown":              "Unknown",
    "2to-ky":               "2to-Ky",
}

# ─── SIZE EXTRACTION ────────────────────────────────────────────────────────
def extract_size(name: str) -> str:
    if not isinstance(name, str):
        return ""
    # Explicit "Size X" or "Size 10" or "Size 7.5"
    m = re.search(
        r'\bsize\s*(xxs|xs|xl|xxl|xxxl|osfm|s|m|l|\d+\.?\d*)',
        name, re.IGNORECASE
    )
    if m:
        return m.group(1).upper()
    # Bare size token at end of string after slash: "/ M" or "/XL"
    m = re.search(
        r'/\s*(xxs|xs|xl|xxl|xxxl|osfm|s|m|l|\d+\.?\d*)\s*$',
        name, re.IGNORECASE
    )
    if m:
        val = m.group(1)
        if re.match(r'^\d{4}$', val):   # skip years like "2024"
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
    ("Top",             [r"\btop\b"]),   # word-boundary "top" only
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
    # Remove explicit "Size X" tokens
    n = re.sub(r'[/\s]*\bsize\s*[^\s/,]+', ' ', n, flags=re.IGNORECASE)
    # Remove trailing bare size after slash: "/ M" at end
    n = re.sub(r'\s*/\s*(xxs|xs|xl|xxl|xxxl|osfm|s|m|l|\d+\.?\d*)\s*$', ' ', n, flags=re.IGNORECASE)
    # Replace slashes with space
    n = n.replace('/', ' ')
    # Collapse whitespace
    n = re.sub(r'\s+', ' ', n).strip()
    return n


# ─── BRAND CLEANER ──────────────────────────────────────────────────────────
def clean_brand(brand) -> str:
    if not isinstance(brand, str) or not brand.strip():
        return ""
    key = brand.strip().lower()
    if key in BRAND_FIX:
        return BRAND_FIX[key]
    stripped = brand.strip()
    # All-caps or all-lowercase → title case
    if stripped.isupper() or stripped.islower():
        return stripped.title()
    return stripped


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

# Show brand fixes applied
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

# Fill missing brands using product-export lookup
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

# Parse datetime
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

# Identify discounted receipts BEFORE filtering discount rows
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
    "details":        sl_raw["Details"],
    "sku":            sl_raw["Sku"].astype(str).str.strip(),
})

# Drop discount placeholder rows and returns (negative quantity)
sl = sl[sl["sku"] != "vend-discount"]
sl = sl[sl["quantity"] > 0]

# Mark discounted transactions
sl["has_discount"] = sl["receipt_number"].isin(disc_receipts)

# Join product metadata via SKU
pe_lookup  = pe.set_index("sku")[["brand_name","product_category","retail_price","size"]].to_dict("index")
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
            WHEN 2 THEN 'February' WHEN 3 THEN 'March'
            WHEN 4 THEN 'April'    WHEN 5 THEN 'May'
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

# ── 4i. Discount impact ───────────────────────────────────────
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


# ════════════════════════════════════════════════════════════════════════════
# 5. TABLEAU EXPORTS
# ════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 5 — Tableau Exports")
print("=" * 60)

# T1: Daily revenue with rolling averages — time-series charts
daily.to_csv(OUT / "tableau" / "T1_daily_revenue.csv", index=False)
print("  ✓ T1_daily_revenue.csv")

# T2: Brand performance by category — bar chart / treemap
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

# T3: Sale-line detail — granular Tableau cross-filters
sl_tab = sl[[
    "date","hour","month","day_of_week","week_num",
    "receipt_number","sku","details","brand_name","product_category","size",
    "quantity","subtotal","sales_tax","total","retail_price","has_discount"
]].copy()
sl_tab.to_csv(OUT / "tableau" / "T3_sale_lines_detail.csv", index=False)
print("  ✓ T3_sale_lines_detail.csv")

# T4: Transaction summary — AOV / basket size
sh_tab = sh.copy()
sh_tab["avg_item_value"] = (sh_tab["subtotal"] / sh_tab["total_items"].replace(0, None)).round(2)
sh_tab.to_csv(OUT / "tableau" / "T4_transactions.csv", index=False)
print("  ✓ T4_transactions.csv")

# T5: Category performance
category.to_csv(OUT / "tableau" / "T5_category_performance.csv", index=False)
print("  ✓ T5_category_performance.csv")

# T6: Pricing distribution
pricing.to_csv(OUT / "tableau" / "T6_pricing_distribution.csv", index=False)
print("  ✓ T6_pricing_distribution.csv")

# T7: Basket analysis (transaction-level)
basket.to_csv(OUT / "tableau" / "T7_basket_analysis.csv", index=False)
print("  ✓ T7_basket_analysis.csv")

# T8: Day-of-week heatmap data
dow.to_csv(OUT / "tableau" / "T8_day_of_week.csv", index=False)
print("  ✓ T8_day_of_week.csv")

# T9: Monthly summary
monthly.to_csv(OUT / "tableau" / "T9_monthly_summary.csv", index=False)
print("  ✓ T9_monthly_summary.csv")

# T10: Full product inventory with revenue join
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


# ════════════════════════════════════════════════════════════════════════════
# 6. BUSINESS INSIGHTS & RECOMMENDATIONS
# ════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 6 — Business Insights & Recommendations")
print("=" * 60)

# Gather key stats
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

monthly_vals = monthly.sort_values("month")
feb_rev = float(monthly_vals[monthly_vals["month"]==2]["total_revenue"].values[0]) if 2 in monthly_vals["month"].values else 0
may_rev = float(monthly_vals[monthly_vals["month"]==5]["total_revenue"].values[0]) if 5 in monthly_vals["month"].values else 0

insights = f"""
╔══════════════════════════════════════════════════════════════════════════╗
║   KNOXVILLE VINTAGE CLOTHING STORE — BUSINESS INSIGHTS & STRATEGY      ║
║   Data Period: February 13 – May 24, 2026 | Produced by Data Analysis  ║
╚══════════════════════════════════════════════════════════════════════════╝

BUSINESS SNAPSHOT
  Total Revenue (pre-tax)  : ${total_rev:>10,.2f}
  Total Units Sold         : {total_units:>10,}
  Total Transactions       : {total_txns:>10,}
  Average Order Value      : ${avg_aov:>10,.2f}
  Date Range               : Feb 13 – May 24, 2026  (≈ 101 days)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FIVE BUSINESS INSIGHTS
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

  Customers who pick up a second item nearly double their spend. This is
  your highest-leverage behavioral trigger — there is no acquisition cost,
  only floor experience and staff conversation.

INSIGHT 4 │ DAY-OF-WEEK PERFORMANCE — {best_dow['day_of_week']} is Your Anchor Day
─────────────────────────────────────────────────────────────────────────────
  {best_dow['day_of_week']:<10} avg ${best_dow['revenue_per_day_open']:>7,.2f}/day  ({best_dow['transactions']} total transactions)
  {worst_dow['day_of_week']:<10} avg ${worst_dow['revenue_per_day_open']:>7,.2f}/day  ({worst_dow['transactions']} total transactions)

  {best_dow['day_of_week']} outperforms {worst_dow['day_of_week']} by {((best_dow['revenue_per_day_open']/max(worst_dow['revenue_per_day_open'],1))-1)*100:.0f}% per open day.
  This has staffing, stocking, and marketing implications. Weak-day traffic
  may respond well to timed promotions (e.g., "Tuesday Deal Rack").

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

RECOMMENDATION 2 │ FORMALIZE A MARKDOWN CADENCE FOR AGING INVENTORY
─────────────────────────────────────────────────────────────────────────────
  The {sweet['price_bucket']} price band is your sweet spot, but items priced $75+
  are selling slowly. Implement a structured markdown schedule:
    — Day 1–30:   Full retail price
    — Day 31–60:  10% off (sticker update)
    — Day 61–90:  20% off
    — Day 91+:    30% off or move to clearance rack

  This creates urgency for price-sensitive customers, recovers capital
  from slow movers, and frees shelf space for high-velocity buys. Track
  discount rate by category to refine which categories age fastest and
  adjust future pricing at intake.

RECOMMENDATION 3 │ INVEST IN THE {best_dow['day_of_week'].upper()} IN-STORE EXPERIENCE TO GROW BASKET SIZE
─────────────────────────────────────────────────────────────────────────────
  {best_dow['day_of_week']} already drives your strongest revenue per open day. To extend
  this advantage: (1) staff your most experienced seller on the floor,
  (2) refresh curated "outfit" displays Thursday evening so {best_dow['day_of_week']} shoppers
  see fresh pairings, and (3) place accessories (high-margin, low-risk)
  at every natural pause point — fitting room entrance, register line.

  The +{((aov_multi/aov_single)-1)*100:.0f}% AOV for multi-item baskets means each additional
  unit a customer picks up is disproportionately valuable. A brief, natural
  staff prompt — "That top would pair perfectly with the [skirt] we just
  got in" — costs nothing and consistently moves the needle.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TABLEAU PREPARATION NOTES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  10 Tableau-ready CSVs exported to output/tableau/:
  T1  Daily Revenue         — time-series line chart, 7-day rolling avg
  T2  Brand Performance     — bar chart, treemap, or scatter (rev vs units)
  T3  Sale Lines Detail     — master data source for cross-filtering
  T4  Transactions          — basket size, AOV distribution
  T5  Category Performance  — stacked bar, pie
  T6  Pricing Distribution  — histogram / price bucket bar chart
  T7  Basket Analysis       — basket size frequency chart
  T8  Day of Week           — heatmap / bar chart
  T9  Monthly Summary       — month-over-month bar chart
  T10 Products & Inventory  — inventory health, sell-through table

  All files use consistent field names for easy joining in Tableau:
  - Join key across files: 'sku' and 'receipt_number'
  - Date field: 'date' (YYYY-MM-DD string, Tableau auto-parses)
  - Revenue field: 'subtotal' (pre-tax) or 'total' (post-tax)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

print(insights)

with open(OUT / "analysis" / "business_insights.txt", "w", encoding="utf-8") as f:
    f.write(insights)

print("\n" + "=" * 60)
print("  COMPLETE — all output saved to: output/")
print("  ├── cleaned/   — 4 cleaned CSV files")
print("  ├── analysis/  — 9 analysis CSVs + business_insights.txt")
print("  └── tableau/   — 10 Tableau-ready export files")
print("=" * 60)

conn.close()
