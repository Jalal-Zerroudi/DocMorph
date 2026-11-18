# Contribuer à DocMorph

Merci de contribuer à DocMorph. Ce guide complète le README avec un environnement de développement léger, les commandes de test et les vérifications attendues avant un commit.

## Prérequis

- Python 3.11, 3.12 ou 3.13 ; Python 3.12 est la version utilisée par le script d'installation WSL.
- WSL2 Ubuntu pour vérifier le parcours d'installation complet.
- Les exécutables externes nécessaires uniquement aux conversions concernées : LibreOffice, Tesseract, OCRmyPDF, Pandoc et Docling.

Les tests qui dépendent d'un exécutable absent sont ignorés. Il n'est donc pas nécessaire d'installer tous les moteurs pour travailler sur le registre, la configuration, la détection ou l'API.

## Environnement de développement

Depuis la racine du dépôt :

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

Pour tester également le mode structure :

```bash
python -m pip install -e '.[dev,structure]'
```

L'installation complète destinée à l'utilisation sous WSL reste disponible avec :

```bash
bash scripts/install_wsl.sh
```

## Exécuter les vérifications

Suite rapide :

```bash
pytest
```

Tests ciblés utiles pendant le développement :

```bash
pytest tests/test_config.py
pytest tests/test_detect.py
pytest tests/test_registry.py
pytest tests/test_api.py
```

Tests dépendant de moteurs externes :

```bash
pytest -m libreoffice
pytest -m ocr
DOCMORPH_TEST_STRUCTURE=1 pytest -m structure
```

Vérifiez enfin les moteurs réellement disponibles sur la machine :

```bash
python -m docmorph.doctor
```

## Repères d'architecture

- `docmorph/core/` contient les modèles, les erreurs, la détection et le registre de conversions.
- `docmorph/engines/` isole les intégrations avec les moteurs externes.
- `docmorph/api/` gère FastAPI, les tâches et le stockage temporaire.
- `docmorph/web/` contient l'interface sans framework.
- `tests/` doit couvrir le comportement observable plutôt que les détails internes.

Lors de l'ajout d'une conversion, déclarez clairement les formats source et cible, le mode éventuel et les conditions de disponibilité. Ajoutez ensuite le moteur à `default_engines()` dans `docmorph/engines/__init__.py`.

## Invariants à préserver

- Détecter le type réel du fichier au lieu de faire confiance à son extension.
- Ne jamais réutiliser un chemin fourni par le client pour nommer un résultat.
- Ne pas exposer au client les détails internes d'une erreur de conversion.
- Supprimer les fichiers partiels lorsqu'un envoi ou une conversion échoue.
- Conserver des noms de sortie uniques dans les lots et les archives ZIP.
- Respecter les limites configurées de taille, de durée et de concurrence.
- Maintenir l'écoute locale par défaut sur `127.0.0.1`.

Toute modification du cycle de vie des tâches doit également préciser son effet sur les statuts, les téléchargements, les archives ZIP et le nettoyage après expiration.

## Documentation et commits

Mettez à jour le README ou `docs/LIMITATIONS.md` lorsqu'un changement affecte :

- la matrice des conversions ;
- une dépendance système ou une option d'installation ;
- une variable d'environnement ;
- une route ou une réponse de l'API ;
- la fidélité, les performances ou les limites d'un moteur.

Utilisez un message de commit clair suivant Conventional Commits, par exemple `fix: remove partial upload files`, `test: cover duplicate output names` ou `docs: clarify OCR requirements`.

## Checklist avant commit

- [ ] Les tests pertinents passent ou les dépendances manquantes expliquant les tests ignorés sont identifiées.
- [ ] `python -m docmorph.doctor` ne révèle pas de régression inattendue.
- [ ] Aucun document utilisateur, résultat de conversion, modèle ou secret n'est ajouté au dépôt.
- [ ] Les erreurs publiques restent génériques et les détails techniques restent dans les journaux.
- [ ] La documentation correspond au comportement réellement livré.
