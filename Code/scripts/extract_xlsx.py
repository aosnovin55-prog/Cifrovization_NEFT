"""
Извлечение ряда WABT и лимита из .xlsx без pandas: чтение XML внутри zip.

Основной сценарий (main): лист WABT — колонка B (WABT), ось t = 0,1,2,…
Вспомогательно: parse_wabt_sheet_datetime — дата из колонки A (для других скриптов).
"""

import argparse
import csv
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

# Пространства имён OOXML для workbook / sheet / sharedStrings.
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RELNS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
DOCRELNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

# Дата/время в Excel: целая и дробная часть серийного номера (эпоха 1899-12-30).
_EXCEL_DATETIME_EPOCH = datetime(1899, 12, 30)


def excel_serial_to_datetime(serial: float) -> datetime:
    """Перевод серийного номера Excel в datetime (дата отсчёта как в Excel)."""
    return _EXCEL_DATETIME_EPOCH + timedelta(days=float(serial))


def parse_time_from_wabt_first_column(raw: str) -> datetime | None:
    """Первая колонка листа WABT: серийный номер Excel или текст даты."""
    raw = (raw or "").strip().replace(",", ".")
    if not raw:
        return None
    try:
        val = float(raw)
        if 20000.0 < val < 800000.0:
            return excel_serial_to_datetime(val)
    except ValueError:
        pass
    for fmt in (
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    ):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def col_to_num(cell_ref: str) -> int:
    """Номер колонки по ссылке ячейки: A=1, B=2, …, Z=26, AA=27."""
    match = re.match(r"([A-Z]+)", cell_ref or "")
    if not match:
        return 0
    value = 0
    for ch in match.group(1):
        value = value * 26 + (ord(ch) - 64)
    return value


def read_shared_strings(zf: zipfile.ZipFile):
    """Массив общих строковых значений (тип ячейки `s` ссылается по индексу)."""
    path = "xl/sharedStrings.xml"
    if path not in zf.namelist():
        return []
    root = ET.fromstring(zf.read(path))
    values = []
    for si in root.findall(f"{NS}si"):
        values.append("".join(t.text or "" for t in si.iter(f"{NS}t")))
    return values


def cell_text(cell: ET.Element, shared):
    """Текстовое значение ячейки: shared string, inlineStr или число в <v>."""
    cell_type = cell.get("t")
    value = cell.find(f"{NS}v")
    if cell_type == "s" and value is not None and (value.text or "").isdigit():
        idx = int(value.text)
        return shared[idx] if 0 <= idx < len(shared) else ""
    if cell_type == "inlineStr":
        inline = cell.find(f"{NS}is")
        if inline is not None:
            return "".join(t.text or "" for t in inline.iter(f"{NS}t"))
    return value.text if value is not None and value.text is not None else ""


def get_sheet_target(zf: zipfile.ZipFile, sheet_name: str):
    """Путь к xml листа внутри архива по имени (как в Excel)."""
    wb = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rid_to_target = {r.get("Id"): r.get("Target") for r in rels.findall(f"{RELNS}Relationship")}
    for s in wb.findall(f".//{NS}sheet"):
        if s.get("name") == sheet_name:
            rid = s.get(f"{DOCRELNS}id")
            target = rid_to_target.get(rid, "")
            if target.startswith("/"):
                target = target[1:]
            if not target.startswith("xl/"):
                target = f"xl/{target.split('xl/')[-1]}"
            return target
    raise ValueError(f"Sheet '{sheet_name}' not found")


def parse_wabt_sheet(xlsx_path: Path):
    """Список (t, wabt): только колонка B, t счётчик строк (для пайплайна и CLI)."""
    with zipfile.ZipFile(xlsx_path) as zf:
        shared = read_shared_strings(zf)
        target = get_sheet_target(zf, "WABT")
        root = ET.fromstring(zf.read(target))
        rows = root.findall(f".//{NS}sheetData/{NS}row")
        out = []
        t = 0.0
        for row in rows[1:]:
            cells = {col_to_num(c.get("r", "")): c for c in row.findall(f"{NS}c")}
            if 2 not in cells:
                continue
            raw = cell_text(cells[2], shared).replace(",", ".")
            try:
                wabt = float(raw)
            except ValueError:
                continue
            out.append((t, wabt))
            t += 1.0
        return out


def parse_wabt_sheet_datetime(xlsx_path: Path) -> list[tuple[datetime, float]]:
    """Ряд WABT с осью времени из первой колонки (серийный номер Excel или строка даты)."""
    with zipfile.ZipFile(xlsx_path) as zf:
        shared = read_shared_strings(zf)
        target = get_sheet_target(zf, "WABT")
        root = ET.fromstring(zf.read(target))
        rows = root.findall(f".//{NS}sheetData/{NS}row")
        out: list[tuple[datetime, float]] = []
        for row in rows[1:]:
            cells = {col_to_num(c.get("r", "")): c for c in row.findall(f"{NS}c")}
            if 1 not in cells or 2 not in cells:
                continue
            raw_t = cell_text(cells[1], shared)
            raw_w = cell_text(cells[2], shared).replace(",", ".")
            ts = parse_time_from_wabt_first_column(raw_t)
            if ts is None:
                continue
            try:
                wabt = float(raw_w)
            except ValueError:
                continue
            out.append((ts, wabt))
        return out


def parse_limit_sheet(xlsx_path: Path):
    """Число с листа «Ограничение»: первая строка, значение из колонки B."""
    with zipfile.ZipFile(xlsx_path) as zf:
        shared = read_shared_strings(zf)
        target = get_sheet_target(zf, "Ограничение")
        root = ET.fromstring(zf.read(target))
        row = root.find(f".//{NS}sheetData/{NS}row[@r='1']")
        if row is None:
            raise ValueError("Limit row not found")
        cells = {col_to_num(c.get("r", "")): c for c in row.findall(f"{NS}c")}
        raw = cell_text(cells.get(2), shared).replace(",", ".")
        return float(raw)


def main():
    """CLI: записать CSV `t,wabt` и текстовый файл с лимитом."""
    parser = argparse.ArgumentParser(description="Extract WABT series and limit from xlsx")
    parser.add_argument("xlsx", type=Path)
    parser.add_argument("out_csv", type=Path)
    parser.add_argument("--limit_out", type=Path, required=True)
    args = parser.parse_args()

    series = parse_wabt_sheet(args.xlsx)
    limit = parse_limit_sheet(args.xlsx)

    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["t", "wabt"])
        writer.writerows(series)

    args.limit_out.write_text(str(limit), encoding="utf-8")


if __name__ == "__main__":
    main()
