from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
IN_PATH = BASE_DIR / "data" / "amadeus_rates.csv"
OUT_PATH = BASE_DIR / "data" / "leads.csv"

MIN_PRICE = 50
MAX_PRICE = 300

EXCLUDE_KEYWORDS = (
    "RITZ",
    "FOUR SEASONS",
    "ST REGIS",
    "EDITION",
    "FAENA",
    "SETT AI",
    "W ",
)


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(c).strip() for c in df.columns]

    if "cheapest_total" not in df.columns:
        for c in ["total", "total_usd", "total_price", "price_total", "offer_total"]:
            if c in df.columns:
                df = df.rename(columns={c: "cheapest_total"})
                break

    if "hotel_name" not in df.columns:
        for c in ["name", "hotel", "property_name"]:
            if c in df.columns:
                df = df.rename(columns={c: "hotel_name"})
                break

    if "address" not in df.columns:
        for c in ["address_line", "hotel_address", "street", "street_address", "location"]:
            if c in df.columns:
                df = df.rename(columns={c: "address"})
                break

    if "street_match" not in df.columns:
        if "address" in df.columns:
            addr = df["address"].fillna("").astype(str).str.upper()
            df["street_match"] = addr.str.contains("OCEAN|COLLINS|WASHINGTON", regex=True)
        else:
            df["street_match"] = True

    return df


def main() -> int:
    if not IN_PATH.exists():
        print(f"Missing input file: {IN_PATH}")
        return 1

    df = pd.read_csv(IN_PATH)
    df = normalize_columns(df)

    required = ["hotel_name", "cheapest_total", "address", "street_match"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"Missing required columns: {', '.join(missing)}")
        print("Columns found:", ", ".join(df.columns))
        return 2

    df["cheapest_total"] = pd.to_numeric(df["cheapest_total"], errors="coerce")
    df = df.dropna(subset=["cheapest_total"])

    df["hotel_name_upper"] = df["hotel_name"].fillna("").astype(str).str.upper()

    exclude_pattern = "|".join([k.replace(" ", r"\s+") for k in EXCLUDE_KEYWORDS])
    mask_exclude = df["hotel_name_upper"].str.contains(exclude_pattern, regex=True)

    df = df[
        (df["cheapest_total"] >= MIN_PRICE)
        & (df["cheapest_total"] <= MAX_PRICE)
        & (df["street_match"] == True)
        & (~mask_exclude)
    ].copy()

    df = df.sort_values("cheapest_total")
    df.to_csv(OUT_PATH, index=False)

    print(f"Saved {len(df)} rows to {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())