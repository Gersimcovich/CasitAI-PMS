from __future__ import annotations

import argparse
import csv
import os
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUT_CSV = DATA_DIR / "amadeus_rates.csv"

ENV_PATH = ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)


def env_required(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        raise RuntimeError(f"Missing {name} in {ENV_PATH}")
    return v


def normalize_host(host: str) -> str:
    host = (host or "").strip().rstrip("/")
    if not host:
        return host
    if not host.startswith("http://") and not host.startswith("https://"):
        host = "https://" + host
    return host


def http_debug_raise(r: requests.Response, label: str, verbose_400: bool = False) -> None:
    if r.status_code < 400:
        return
    payload = None
    try:
        payload = r.json()
    except Exception:
        payload = {"raw": (r.text or "")[:2000]}
    if r.status_code == 400 and not verbose_400:
        reason = ""
        try:
            reason = (payload.get("errors") or [{}])[0].get("title") or ""
        except Exception:
            reason = ""
        raise RuntimeError(f"{label} 400 {reason}".strip())
    raise RuntimeError(f"{label} status={r.status_code} payload={payload}")


def get_token(host: str, client_id: str, client_secret: str, timeout_s: int = 30) -> str:
    host = normalize_host(host)
    url = f"{host}/v1/security/oauth2/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }
    r = requests.post(url, data=data, timeout=timeout_s)
    http_debug_raise(r, "token")
    j = r.json()
    token = j.get("access_token")
    if not token:
        raise RuntimeError(f"token missing in response: {j}")
    return token


def hotels_by_geocode(
    host: str,
    token: str,
    latitude: float,
    longitude: float,
    radius_km: int = 6,
    timeout_s: int = 30,
) -> list[dict[str, Any]]:
    host = normalize_host(host)
    url = f"{host}/v1/reference-data/locations/hotels/by-geocode"
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "radius": radius_km,
        "radiusUnit": "KM",
    }
    r = requests.get(url, headers=headers, params=params, timeout=timeout_s)
    http_debug_raise(r, "hotels_by_geocode")
    return (r.json() or {}).get("data", []) or []


def hotel_offers(
    host: str,
    token: str,
    hotel_id: str,
    check_in: str,
    check_out: str,
    adults: int,
    room_quantity: int = 1,
    currency: str = "USD",
    timeout_s: int = 30,
) -> dict[str, Any]:
    host = normalize_host(host)
    url = f"{host}/v3/shopping/hotel-offers"
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "hotelIds": hotel_id,
        "adults": adults,
        "checkInDate": check_in,
        "checkOutDate": check_out,
        "roomQuantity": room_quantity,
        "currency": currency,
    }
    r = requests.get(url, headers=headers, params=params, timeout=timeout_s)
    if r.status_code == 400:
        payload = {}
        try:
            payload = r.json()
        except Exception:
            payload = {"raw": (r.text or "")[:2000]}
        return {"_error": payload, "_status": 400}
    if r.status_code == 429:
        payload = {}
        try:
            payload = r.json()
        except Exception:
            payload = {"raw": (r.text or "")[:2000]}
        return {"_error": payload, "_status": 429}
    http_debug_raise(r, "hotel_offers")
    return r.json() or {}


def safe_float(x: Any) -> float | None:
    try:
        if x is None:
            return None
        s = str(x).strip()
        if not s:
            return None
        return float(s)
    except Exception:
        return None


def pick_cheapest_offer(payload: dict[str, Any]) -> dict[str, Any] | None:
    data = payload.get("data") or []
    if not data:
        return None

    offers = (data[0].get("offers") or []) if isinstance(data[0], dict) else []
    best = None
    best_total = None

    for off in offers:
        price = (off or {}).get("price") or {}
        total = safe_float(price.get("total"))
        if total is None:
            continue
        if best is None or (best_total is not None and total < best_total):
            best = off
            best_total = total

    return best


def offer_fields(offer: dict[str, Any], hotel: dict[str, Any]) -> dict[str, Any]:
    price = (offer.get("price") or {}) if isinstance(offer, dict) else {}
    room = (offer.get("room") or {}) if isinstance(offer, dict) else {}

    room_type = ""
    if isinstance(room, dict):
        room_type = (
            room.get("typeEstimated", {}).get("category")
            or room.get("typeEstimated", {}).get("bedType")
            or room.get("description", {}).get("text")
            or room.get("name")
            or ""
        )

    total = safe_float(price.get("total"))
    currency = (price.get("currency") or "") if isinstance(price, dict) else ""

    return {
        "hotel_id": hotel.get("hotelId", ""),
        "hotel_name": hotel.get("name", ""),
        "hotel_address": (hotel.get("address") or {}).get("lines", [""])[0] if isinstance(hotel.get("address"), dict) else "",
        "hotel_city": (hotel.get("address") or {}).get("cityName", "") if isinstance(hotel.get("address"), dict) else "",
        "hotel_postal": (hotel.get("address") or {}).get("postalCode", "") if isinstance(hotel.get("address"), dict) else "",
        "hotel_lat": (hotel.get("geoCode") or {}).get("latitude", "") if isinstance(hotel.get("geoCode"), dict) else "",
        "hotel_lng": (hotel.get("geoCode") or {}).get("longitude", "") if isinstance(hotel.get("geoCode"), dict) else "",
        "room_type": room_type,
        "rate_total": total if total is not None else "",
        "currency": currency,
    }


def street_filter(h: dict[str, Any]) -> bool:
    addr = (h.get("address") or {}) if isinstance(h.get("address"), dict) else {}
    lines = addr.get("lines") or []
    line = (lines[0] if lines else "") or ""
    s = line.lower()
    return ("ocean dr" in s) or ("collins" in s) or ("washington" in s)


@dataclass
class Row:
    run_time: str
    stay_date: str
    adults: int
    hotel_id: str
    hotel_name: str
    room_type: str
    total: Any
    currency: str
    address_line: str


def ensure_csv_header(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    with path.open("w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "run_time",
                "stay_date",
                "adults",
                "hotel_id",
                "hotel_name",
                "room_type",
                "total",
                "currency",
                "address_line",
            ],
        )
        w.writeheader()


def append_rows(path: Path, rows: list[Row]) -> None:
    ensure_csv_header(path)
    with path.open("a", newline="", encoding="utf8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "run_time",
                "stay_date",
                "adults",
                "hotel_id",
                "hotel_name",
                "room_type",
                "total",
                "currency",
                "address_line",
            ],
        )
        for r in rows:
            w.writerow(
                {
                    "run_time": r.run_time,
                    "stay_date": r.stay_date,
                    "adults": r.adults,
                    "hotel_id": r.hotel_id,
                    "hotel_name": r.hotel_name,
                    "room_type": r.room_type,
                    "total": r.total,
                    "currency": r.currency,
                    "address_line": r.address_line,
                }
            )


def run(
    days_out: int = 1,
    nights: int = 1,
    adults_list: tuple[int, ...] = (2, 4),
    currency: str = "USD",
    radius_km: int = 6,
    max_hotels: int = 20,
    sleep_s: float = 0.35,
) -> None:
    host = normalize_host(env_required("AMADEUS_HOST"))
    client_id = env_required("AMADEUS_CLIENT_ID")
    client_secret = env_required("AMADEUS_CLIENT_SECRET")

    token = get_token(host, client_id, client_secret)

    mb_lat = 25.790654
    mb_lng = -80.130045

    hotels = hotels_by_geocode(host, token, mb_lat, mb_lng, radius_km=radius_km)
    print(f"Found {len(hotels)} hotels near Miami Beach (radius {radius_km} KM)")

    hotels = [h for h in hotels if street_filter(h)]
    print("Filtered to {} hotels on Ocean Drive, Collins Ave, Washington Ave".format(len(hotels)))

    if max_hotels and len(hotels) > max_hotels:
        hotels = hotels[: max_hotels]
        print(f"Using first {max_hotels} hotels to avoid 429 rate limit in test")

    run_time = datetime.now().isoformat(timespec="seconds")
    out_rows: list[Row] = []

    for d in range(days_out):
        stay = date.today() + timedelta(days=d)
        check_in = stay.isoformat()
        check_out = (stay + timedelta(days=nights)).isoformat()

        for h in hotels:
            hotel_id = h.get("hotelId", "")
            if not hotel_id:
                continue

            addr_line = ""
            addr = h.get("address") or {}
            if isinstance(addr, dict):
                lines = addr.get("lines") or []
                addr_line = (lines[0] if lines else "") or ""

            for adults in adults_list:
                payload = hotel_offers(
                    host=host,
                    token=token,
                    hotel_id=hotel_id,
                    check_in=check_in,
                    check_out=check_out,
                    adults=int(adults),
                    room_quantity=1,
                    currency=currency,
                )

                if payload.get("_status") == 429:
                    print("Hit 429 rate limit. Stop early and reduce max_hotels or increase sleep.")
                    append_rows(OUT_CSV, out_rows)
                    print(f"Saved {len(out_rows)} rows to {OUT_CSV}")
                    return

                if payload.get("_status") == 400:
                    time.sleep(sleep_s)
                    continue

                best = pick_cheapest_offer(payload)
                if not best:
                    time.sleep(sleep_s)
                    continue

                f = offer_fields(best, h)
                total = f.get("rate_total", "")
                room_type = f.get("room_type", "")
                cur = f.get("currency", currency) or currency

                if total != "":
                    print(f"{stay.isoformat()} adults={adults} {h.get('name','')} total={total} {cur}")

                out_rows.append(
                    Row(
                        run_time=run_time,
                        stay_date=stay.isoformat(),
                        adults=int(adults),
                        hotel_id=str(hotel_id),
                        hotel_name=str(h.get("name", "")),
                        room_type=str(room_type),
                        total=total,
                        currency=str(cur),
                        address_line=str(addr_line),
                    )
                )

                time.sleep(sleep_s)

    append_rows(OUT_CSV, out_rows)
    print(f"Saved {len(out_rows)} rows to {OUT_CSV}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=1)
    p.add_argument("--nights", type=int, default=1)
    p.add_argument("--adults", type=str, default="2,4")
    p.add_argument("--currency", type=str, default="USD")
    p.add_argument("--radius-km", type=int, default=6)
    p.add_argument("--max-hotels", type=int, default=20)
    p.add_argument("--sleep", type=float, default=0.35)
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    adults_list = tuple(int(x.strip()) for x in args.adults.split(",") if x.strip())
    run(
        days_out=args.days,
        nights=args.nights,
        adults_list=adults_list,
        currency=args.currency,
        radius_km=args.radius_km,
        max_hotels=args.max_hotels,
        sleep_s=args.sleep,
    )