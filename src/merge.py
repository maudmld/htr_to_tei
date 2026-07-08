"""
src/merge.py
------------
Fusionne les fichiers ALTO 4 d'un dossier en extrayant uniquement
les <String CONTENT="..."/> appartenant aux blocs taggés MainZone.
"""

from pathlib import Path
from lxml import etree

NS = {"alto": "http://www.loc.gov/standards/alto/ns-v4#"}


def get_mainzone_id(root: etree._Element) -> set[str]:
    """
    Récupère les IDs des tags dont le LABEL est 'MainZone'
    depuis l'élément global <Tags>.
    Retourne un set d'IDs (ex. {'BT43014'}).
    """
    return {
        tag.get("ID")
        for tag in root.findall(".//alto:Tags/alto:OtherTag", NS)
        if tag.get("LABEL") == "MainZone"
    }


def extract_strings_from_file(filepath: Path) -> tuple[str, list[str]]:
    """
    Analyse un fichier ALTO et retourne :
    - le nom du fichier image source (depuis <fileName>)
    - la liste des CONTENT des <String> dans les blocs MainZone
    """
    tree = etree.parse(filepath)
    root = tree.getroot()

    # 1. Identifier le ou les IDs MainZone
    mainzone_ids = get_mainzone_id(root)
    if not mainzone_ids:
        print(f"  [!] Aucun tag MainZone trouvé dans {filepath.name}, fichier ignoré.")
        return filepath.name, []

    # 2. Récupérer le nom de l'image source
    filename_el = root.find(
        ".//alto:Description/alto:sourceImageInformation/alto:fileName", NS
    )
    source_name = filename_el.text if filename_el is not None else filepath.name

    # 3. Sélectionner les TextBlock dont @TAGREFS référence un ID MainZone
    strings = []
    for block in root.findall(".//alto:TextBlock", NS):
        tagrefs = set(block.get("TAGREFS", "").split())
        if tagrefs & mainzone_ids:
            for string_el in block.findall(".//alto:String", NS):
                content = string_el.get("CONTENT", "").strip()
                if content:
                    strings.append(content)

    return source_name, strings


def merge_alto_folder(input_dir: Path, output_file: Path) -> int:
    """
    Parcourt tous les fichiers .xml du dossier input_dir,
    extrait les String MainZone et produit un XML fusionné.
    Retourne le nombre de pages traitées.
    """
    alto_files = sorted(input_dir.glob("*.xml"))
    if not alto_files:
        print(f"  [!] Aucun fichier .xml trouvé dans {input_dir}")
        return 0

    root_out = etree.Element("alto_merged")
    root_out.set("source_dir", str(input_dir))
    total_strings = 0

    for filepath in alto_files:
        print(f"  · {filepath.name}")
        source_name, strings = extract_strings_from_file(filepath)

        page_el = etree.SubElement(root_out, "page")
        page_el.set("source", source_name)
        page_el.set("file", filepath.name)

        for content in strings:
            line_el = etree.SubElement(page_el, "line")
            line_el.text = content
            total_strings += 1

    tree_out = etree.ElementTree(root_out)
    etree.indent(tree_out, space="  ")
    tree_out.write(output_file, xml_declaration=True, encoding="UTF-8", pretty_print=True)

    print(f"  → {len(alto_files)} fichier(s), {total_strings} ligne(s) extraite(s).")
    return len(alto_files)
