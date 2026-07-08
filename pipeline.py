"""
pipeline.py
-----------
Orchestrateur de la chaîne de traitement HTR ALTO → XML filtré.

Étapes :
    1. Fusion des fichiers ALTO d'un dossier → merged.xml
    2. Chargement des page_ranges depuis DuckDB
    3. Filtrage du XML fusionné → filtered.xml

Usage :
    python pipeline.py \\
        --input  /chemin/vers/dossier_alto \\
        --db     /chemin/vers/base.duckdb \\
        --output ./output \\
        [--witness 48892]  # optionnel : H-ID Heurist du witness

Exemples :
    # Traitement complet sans filtre par witness
    python pipeline.py --input ./alto/arthurian --db ./lostma.duckdb

    # Avec filtre sur un witness spécifique
    python pipeline.py --input ./alto/arthurian --db ./lostma.duckdb --witness 48892

    # Dossier de sortie personnalisé
    python pipeline.py --input ./alto/arthurian --db ./lostma.duckdb --output ./output/arthurian
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime

from src.merge import merge_alto_folder
from src.filter import load_pages_ranges, filter_merged_xml


# ── Configuration du logging ──────────────────────────────────

def setup_logging(output_dir: Path) -> None:
    """Configure le logging vers la console et un fichier dans output_dir."""
    log_file = output_dir / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )
    return log_file


# ── Orchestration ─────────────────────────────────────────────

def run_pipeline(
    input_dir: Path,
    db_path: Path,
    output_dir: Path,
    witness_hid: int | None,
) -> None:

    output_dir.mkdir(parents=True, exist_ok=True)
    log_file = setup_logging(output_dir)
    log = logging.getLogger(__name__)

    log.info("=" * 60)
    log.info("  Pipeline HTR ALTO → XML filtré")
    log.info("=" * 60)
    log.info(f"  Dossier ALTO   : {input_dir}")
    log.info(f"  Base DuckDB    : {db_path}")
    log.info(f"  Dossier sortie : {output_dir}")
    log.info(f"  Witness H-ID   : {witness_hid if witness_hid else 'tous'}")
    log.info("")

    # ── Étape 1 : Fusion ALTO ─────────────────────────────────
    log.info("── Étape 1 : Fusion des fichiers ALTO ──────────────────")
    merged_file = output_dir / "merged.xml"
    n_files = merge_alto_folder(input_dir, merged_file)

    if n_files == 0:
        log.error("Aucun fichier traité. Abandon.")
        sys.exit(1)

    log.info(f"  Fichier produit : {merged_file}")
    log.info("")

    # ── Étape 2 : Chargement des page_ranges ─────────────────
    log.info("── Étape 2 : Chargement des page_ranges (DuckDB) ───────")
    ranges = load_pages_ranges(db_path, witness_hid)

    if not ranges:
        log.error("Aucune plage valide chargée. Abandon.")
        sys.exit(1)

    log.info("")

    # ── Étape 3 : Filtrage ────────────────────────────────────
    log.info("── Étape 3 : Filtrage par folio ────────────────────────")
    filtered_file = output_dir / "filtered.xml"
    kept, skipped = filter_merged_xml(merged_file, filtered_file, ranges)

    log.info("")
    log.info("=" * 60)
    log.info("  Résumé")
    log.info("=" * 60)
    log.info(f"  Fichiers ALTO traités  : {n_files}")
    log.info(f"  Plages DuckDB chargées : {len(ranges)}")
    log.info(f"  Pages conservées       : {kept}")
    log.info(f"  Pages exclues          : {skipped}")
    log.info(f"  Fichiers produits      : {merged_file.name}, {filtered_file.name}")
    log.info(f"  Log                    : {log_file.name}")
    log.info("=" * 60)


# ── Point d'entrée ────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Pipeline HTR : fusion ALTO + filtrage par page_ranges DuckDB.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--input", "-i", required=True, type=Path,
        help="Dossier contenant les fichiers ALTO (.xml)",
    )
    parser.add_argument(
        "--db", "-d", required=True, type=Path,
        help="Chemin vers la base DuckDB (.duckdb)",
    )
    parser.add_argument(
        "--output", "-o", default=Path("output"), type=Path,
        help="Dossier de sortie (défaut : ./output)",
    )
    parser.add_argument(
        "--witness", "-w", default=None, type=int,
        help="H-ID Heurist du witness à filtrer (optionnel)",
    )

    args = parser.parse_args()

    # Validation des chemins d'entrée
    if not args.input.is_dir():
        print(f"Erreur : {args.input} n'est pas un dossier valide.")
        sys.exit(1)
    if not args.db.exists():
        print(f"Erreur : base DuckDB introuvable : {args.db}")
        sys.exit(1)

    run_pipeline(args.input, args.db, args.output, args.witness)


if __name__ == "__main__":
    main()
