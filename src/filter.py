"""
src/filter.py
-------------
Filtre le fichier XML fusionné en ne conservant que les pages dont
le folio physique est inclus dans les page_ranges de la table Part
de DuckDB.

Jointure DuckDB :
    witness."observed_on_pages H-ID"  →  INTEGER[]
    Part."H-ID"                        →  BIGINT
    Part."page_ranges"                 →  VARCHAR[]
"""

import re
import logging
from pathlib import Path
from lxml import etree
import duckdb

log = logging.getLogger(__name__)

SIDE_ORDER = {"r": 0, "v": 1}


# ── Parsing des folios ────────────────────────────────────────

def parse_folio(s: str) -> tuple | None:
    """
    Parse un folio physique en tuple comparable.
    '3v'  → (3, 1)
    '12r' → (12, 0)
    '169' → (169, 0)  # pagination arabe, traité comme recto
    """
    s = s.strip().lower()
    m = re.fullmatch(r"(\d+)([rv]?)", s)
    if not m:
        return None
    return (int(m.group(1)), SIDE_ORDER.get(m.group(2), 0))


def parse_pages_range(raw: str) -> tuple | None:
    """
    Parse une valeur page_ranges depuis DuckDB.
    "['12r-26v']" → ((12,0), (26,1))
    "['169-212']" → ((169,0), (212,0))
    "['?']"       → None (ignoré)
    """
    if not raw:
        return None
    cleaned = re.sub(r"^\['\s*|\s*'\]$", "", str(raw).strip())
    if cleaned in ("?", "") or not re.search(r"\d", cleaned):
        log.warning(f"  page_range non parsable (ignoré) : {raw!r}")
        return None
    m = re.fullmatch(r"([^\-]+)-([^\-]+)", cleaned)
    if m:
        f = parse_folio(m.group(1).strip())
        t = parse_folio(m.group(2).strip())
        if f and t:
            return (f, t)
        log.warning(f"  Plage non parsable (ignorée) : {raw!r}")
        return None
    single = parse_folio(cleaned)
    if single:
        return (single, single)
    log.warning(f"  page_range non parsable (ignoré) : {raw!r}")
    return None


def extract_folio_from_filename(filename: str) -> tuple | None:
    """
    Extrait le folio physique depuis le nom de fichier ALTO.
    Pattern : f{vue_iiif}-f-{folio_physique}.jpg
    'f10-f-3v.jpg'   → (3, 1)
    'f100-f-48v.jpg' → (48, 1)
    """
    m = re.search(r"-f-(\d+[rv]?)\.", filename, re.IGNORECASE)
    if not m:
        log.warning(f"  Impossible d'extraire le folio depuis : {filename!r}")
        return None
    return parse_folio(m.group(1))


def folio_in_range(folio: tuple, range_from: tuple, range_to: tuple) -> bool:
    return range_from <= folio <= range_to


# ── Chargement DuckDB ─────────────────────────────────────────

def load_pages_ranges(db_path: Path, witness_hid: int | None = None) -> list[tuple]:
    """
    Charge les page_ranges depuis DuckDB.
    Si witness_hid est fourni, filtre sur ce témoin via la jointure
    witness."observed_on_pages H-ID" → Part."H-ID".
    """
    con = duckdb.connect(str(db_path), read_only=True)

    if witness_hid:
        query = """
            SELECT UNNEST(p."page_ranges") AS page_range
            FROM witness w
            JOIN Part p
              ON p."H-ID" = ANY(w."observed_on_pages H-ID")
            WHERE w."H-ID" = ?
              AND p."page_ranges" IS NOT NULL
        """
        rows = con.execute(query, [witness_hid]).fetchall()
    else:
        query = """
            SELECT UNNEST("page_ranges") AS page_range
            FROM Part
            WHERE "page_ranges" IS NOT NULL
        """
        rows = con.execute(query).fetchall()

    con.close()

    ranges = []
    for (raw,) in rows:
        if raw is None:
            continue
        parsed = parse_pages_range(str(raw))
        if parsed:
            ranges.append(parsed)

    log.info(f"  {len(ranges)} plage(s) valide(s) chargée(s) depuis DuckDB.")
    return ranges


# ── Filtrage XML ──────────────────────────────────────────────

def filter_merged_xml(
    input_file: Path,
    output_file: Path,
    ranges: list[tuple],
) -> tuple[int, int]:
    """
    Filtre le XML fusionné et écrit le résultat.
    Retourne (pages_conservées, pages_exclues).
    """
    tree = etree.parse(input_file)
    root = tree.getroot()

    root_out = etree.Element("alto_filtered")
    root_out.set("source_file", str(input_file))

    kept, skipped = 0, 0

    for page_el in root.findall("page"):
        source = page_el.get("source", "")
        folio = extract_folio_from_filename(source)

        if folio is None:
            skipped += 1
            continue

        if any(folio_in_range(folio, r[0], r[1]) for r in ranges):
            root_out.append(page_el)
            kept += 1
            log.info(f"  ✓ {source}")
        else:
            skipped += 1
            log.info(f"  ✗ {source}")

    tree_out = etree.ElementTree(root_out)
    etree.indent(tree_out, space="  ")
    tree_out.write(output_file, xml_declaration=True, encoding="UTF-8", pretty_print=True)

    return kept, skipped
