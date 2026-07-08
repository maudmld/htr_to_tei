# HTR_to_tei
A short transformation pipeline for the LostMa project. The input is the ALTO-XML files produced by the HTR team, output is one clean ALTO-XML file per witness that will be use in input for another repository. 

## Pour lancer la pipeline 

Cloner le repository 

Créer un environnement virtuel 

python3 -m venv env

Se placer dans le dossier du repo

Lancer en ligne de commande 

python pipeline.py \
    --input /chemin/vers/dossier/ALTO-XML \
    --db    /chemin/vers/DuckDB \
    --output ./output \
    --witness INT 
