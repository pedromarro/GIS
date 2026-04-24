##Hey, just a way to retrieve geolocation from a webpage, including the complete address and name

import re
from pathlib import Path

import pandas as pd
import geopandas as gpd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from playwright.sync_api import sync_playwright


URL = "https://super24.com.gt/ubicaciones/"
OUTDIR = Path("super24_output")
OUTDIR.mkdir(exist_ok=True)

SAMPLE_SIZE = 100
HEADLESS = False


def clean_text(text: str) -> str:
    if not text:
        return ""

    replacements = {
        "ä": "a", "á": "a", "ã": "a", "â": "a", "å": "a", "ą": "a", "à": "a",
        "ë": "e", "é": "e", "ê": "e", "ė": "e", "ę": "e", "è": "e",
        "í": "i", "ï": "i", "ì": "i", "î": "i", "ī": "i",
        "ñ": "ni",
        "Ä": "A", "Á": "A", "Ã": "A", "Â": "A", "Å": "A", "Ą": "A", "À": "A",
        "Ë": "E", "É": "E", "Ê": "E", "Ė": "E", "Ę": "E", "È": "E",
        "Í": "I", "Ï": "I", "Ì": "I", "Î": "I", "Ī": "I",
        "Ñ": "Ni",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def scrape_page_text() -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_page(ignore_https_errors=True)

        page.goto(URL, wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(5000)

        try:
            page.get_by_text("SÍ", exact=True).click(timeout=5000)
            page.wait_for_timeout(5000)
        except Exception:
            pass

        for _ in range(12):
            page.mouse.wheel(0, 5000)
            page.wait_for_timeout(1200)

        text = page.locator("body").inner_text()
        browser.close()

    return text


def parse_locations(page_text: str) -> list[dict]:
    lines = [
        clean_text(line)
        for line in page_text.splitlines()
        if clean_text(line)
    ]

    start_idx = 0
    for i, line in enumerate(lines):
        if line.upper() == "UBICACIONES":
            start_idx = i + 1
            break

    lines = lines[start_idx:]

    rows = []
    i = 0
    while i < len(lines) - 1:
        current = lines[i].upper()

        if current.startswith("SUPER 24"):
            next_line = lines[i + 1]

            if not next_line.upper().startswith("SUPER 24"):
                rows.append({
                    "NOMBRE_TIENDA": clean_text(lines[i]).upper(),
                    "DIRECCION": clean_text(next_line).upper()
                })
                i += 2
                continue

        i += 1

    unique = []
    seen = set()
    for row in rows:
        key = (row["NOMBRE_TIENDA"], row["DIRECCION"])
        if key not in seen:
            seen.add(key)
            unique.append(row)

    return unique


def geocode_rows(rows: list[dict]) -> pd.DataFrame:
    geolocator = Nominatim(user_agent="super24_ppma", timeout=20)
    geocode = RateLimiter(
        geolocator.geocode,
        min_delay_seconds=1.5,
        max_retries=3,
        error_wait_seconds=5.0,
        swallow_exceptions=True
    )

    results = []
    total = len(rows)

    for idx, row in enumerate(rows, start=1):
        address_full = row["DIRECCION"]

        address_simple = re.sub(
            r'\b(LOCAL|LOCALES|APARTAMENTO|APTO|INTERIOR GASOLINERA|INTERIOR|LOCAL NO\.?|NIVEL|CC|CENTRO COMERCIAL)\b.*',
            '',
            address_full,
            flags=re.IGNORECASE
        )
        address_simple = clean_text(address_simple)

        print(f"{idx}/{total}")

        loc = geocode(f"{address_full}, Guatemala")
        if loc is None:
            loc = geocode(f"{address_simple}, Guatemala")

        results.append({
            "NOMBRE_TIENDA": row["NOMBRE_TIENDA"],
            "DIRECCION": row["DIRECCION"],
            "LONGITUDE": loc.longitude if loc else None,
            "LATITUDE": loc.latitude if loc else None
        })

    return pd.DataFrame(
        results,
        columns=["NOMBRE_TIENDA", "DIRECCION", "LONGITUDE", "LATITUDE"]
    )


def export_outputs(df: pd.DataFrame) -> None:
    csv_path = OUTDIR / "super24_listado.csv"
    xlsx_path = OUTDIR / "super24_listado.xlsx"
    geojson_path = OUTDIR / "super24_puntos.geojson"

    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    df.to_excel(xlsx_path, index=False)

    valid = df[df["LONGITUDE"].notna() & df["LATITUDE"].notna()].copy()

    if not valid.empty:
        gdf = gpd.GeoDataFrame(
            valid,
            geometry=gpd.points_from_xy(valid["LONGITUDE"], valid["LATITUDE"]),
            crs="EPSG:4326"
        )
        gdf.to_file(geojson_path, driver="GeoJSON")
        print(f"GeoJSON guardado en: {geojson_path}")
    else:
        print("No hay coordenadas válidas para exportar GeoJSON.")

    print(f"CSV guardado en: {csv_path}")
    print(f"Excel guardado en: {xlsx_path}")


def main():
    text = scrape_page_text()

    raw_text_path = OUTDIR / "super24_raw_text.txt"
    with open(raw_text_path, "w", encoding="utf-8") as f:
        f.write(text)

    rows = parse_locations(text)

    print(f"Registros extraídos: {len(rows)}")

    rows = rows[:SAMPLE_SIZE]

    print(f"Registros procesados: {len(rows)}")

    df = geocode_rows(rows)

    export_outputs(df)


if __name__ == "__main__":
    main()
































































































###sabes que es abusivo? Que te hagan perder tiempo en una prueba técnica, que te cuestionen por qué decidiste entregar una muestra, que les expliques tus razones y que aún así se ofendan.
### sermonear a las juventudes que somos unos huevones porque no queremos que nos utlicen y que queremos perder para ganar es pura cagada
###nahhhh, una cosa pero barbara. Pero bueno, para que vean que sí le sé.
