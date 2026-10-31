# -*- coding: utf-8 -*-
"""One row per iceberg per day from the BYU/NIC consolidated track files."""
from __future__ import annotations

import csv
import io
import zipfile
from datetime import date, timedelta
from decimal import Decimal

SRC = r"D:\bingshan\data\consolidated_database_v8.0.zip"
OUT = r"D:\bingshan\data\南极冰山.csv"
SPOT = r"D:\bingshan\data\抽查.txt"

# Prefer a position the file does not mark as interpolated.
# NIC is the naming agency. The rest are the satellites, newest daily record first.
SENSORS = (
    ("nic", "国家冰中心"),
    ("ascat", "ASCAT"),
    ("qscat", "QuikSCAT"),
    ("oscat", "OSCAT"),
    ("ers", "ERS"),
    ("nscat", "NSCAT"),
    ("seawinds", "SeaWinds"),
    ("sass", "SASS"),
)
NM_TO_KM = Decimal("1.852")


def tidy(value: float, places: int) -> str:
    text = f"{value:.{places}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def day_of(yyyydoy: str) -> date | None:
    if len(yyyydoy) != 7 or not yyyydoy.isdigit():
        return None
    year = int(yyyydoy[:4])
    doy = int(yyyydoy[4:])
    if doy < 1 or doy > 366:
        return None
    try:
        return date(year, 1, 1) + timedelta(days=doy - 1)
    except ValueError:
        return None


def position(row: dict, sensor: str):
    lat_s = (row.get(sensor + "_1") or "").strip()
    lon_s = (row.get(sensor + "_2") or "").strip()
    if not lat_s or not lon_s:
        return None
    lat = float(lat_s)
    lon = float(lon_s)
    if lat == 0 and lon == 0:
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    flag = (row.get(sensor + "_3") or "").strip()
    return lat, lon, flag == "1"


def main() -> None:
    archive = zipfile.ZipFile(SRC)
    files = sorted(name for name in archive.namelist() if name.lower().endswith(".csv"))
    rows_out = []
    dropped_early = 0
    dropped_empty = 0
    bergs = set()
    interpolated = 0

    for name in files:
        berg = name.rsplit("/", 1)[-1][:-4].upper()
        text = archive.read(name).decode("utf-8")
        for row in csv.DictReader(io.StringIO(text)):
            when = day_of((row.get("date") or "").strip())
            if when is None:
                continue
            if when.year < 1980:
                dropped_early += 1
                continue
            chosen = None
            for sensor, label in SENSORS:
                if sensor + "_1" not in row:
                    continue
                found = position(row, sensor)
                if found is None:
                    continue
                lat, lon, is_interp = found
                if not is_interp:
                    chosen = (lat, lon, label, False)
                    break
                if chosen is None:
                    chosen = (lat, lon, label, True)
            if chosen is None:
                dropped_empty += 1
                continue
            lat, lon, label, is_interp = chosen
            length = (row.get("size_1") or "").strip()
            width = (row.get("size_2") or "").strip()
            length_km = width_km = ""
            if length and width:
                try:
                    length_n = Decimal(length)
                    width_n = Decimal(width)
                except Exception:
                    length_n = width_n = Decimal(0)
                if length_n > 0 and width_n > 0:
                    length_km = tidy(float(length_n * NM_TO_KM), 1)
                    width_km = tidy(float(width_n * NM_TO_KM), 1)
            if is_interp:
                interpolated += 1
            bergs.add(berg)
            rows_out.append(
                [
                    berg,
                    when.isoformat(),
                    tidy(lat, 4),
                    tidy(lon, 4),
                    length_km,
                    width_km,
                    label,
                    "是" if is_interp else "否",
                ]
            )

    rows_out.sort(key=lambda item: (item[0], item[1]))
    with open(OUT, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["冰山", "日期", "纬度", "经度", "长", "宽", "来源", "插值"])
        writer.writerows(rows_out)

    a68 = [row for row in rows_out if row[0] == "A68A"]
    with open(SPOT, "w", encoding="utf-8") as handle:
        handle.write(f"TOTAL {len(rows_out)}\n")
        handle.write(f"ICEBERGS {len(bergs)}\n")
        handle.write(f"INTERPOLATED {interpolated}\n")
        handle.write(f"DROPPED_BEFORE_1980 {dropped_early}\n")
        handle.write(f"DROPPED_NO_POSITION {dropped_empty}\n")
        if rows_out:
            handle.write(f"FIRST_DATE {min(r[1] for r in rows_out)}\n")
            handle.write(f"LAST_DATE {max(r[1] for r in rows_out)}\n")
        handle.write(f"A68A {len(a68)}\n")
        if a68:
            handle.write("A68A_FIRST " + ",".join(a68[0]) + "\n")
            handle.write("A68A_LAST " + ",".join(a68[-1]) + "\n")
    print(f"TOTAL {len(rows_out)} ICEBERGS {len(bergs)}", flush=True)


if __name__ == "__main__":
    main()
