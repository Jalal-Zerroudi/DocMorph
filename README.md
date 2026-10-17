# DocMorph

Convertisseur universel de documents **100 % local** sous WSL2 Ubuntu : moteur Python modulaire,
API REST FastAPI et interface web minimale. Aucune API externe, aucun service cloud : après
installation, tout fonctionne hors ligne.

## Conversions

| Source | Cibles | Moteur |
|---|---|---|
| DOC, DOCX, XLS, XLSX, PPT, PPTX, ODT, ODS, ODP | PDF | LibreOffice headless |
| TXT, RTF | PDF, DOCX | LibreOffice headless |
| JPG, PNG | PDF | img2pdf |
| PDF numérique | TXT | PyMuPDF |
| PDF numérique | DOCX, DOC — mode **fidèle** | pdf2docx |
| PDF numérique | DOCX, DOC — mode **structure** (équations Word) | Docling + Pandoc |
| PDF scanné | TXT | OCRmyPDF + Tesseract (fra, eng, ara) |
| PDF scanné | DOCX, DOC | Docling (OCR Tesseract) + Pandoc |

Le format est détecté à partir du contenu du fichier, pas de son extension. Seules les
conversions dont le moteur est installé sont proposées. Les limites de fidélité sont détaillées
dans [docs/LIMITATIONS.md](docs/LIMITATIONS.md).

## Installation (WSL2 Ubuntu)

Depuis un terminal Ubuntu :

```bash
git clone https://github.com/Jalal-Zerroudi/DocMorph.git
cd DocMorph
bash scripts/install_wsl.sh
```

Le script :

1. installe les paquets système (`sudo`) : LibreOffice, Tesseract et les langues fra/eng/ara,
   Ghostscript, Pandoc, libmagic et les polices (Noto, Carlito, Caladea, polices arabes) ;
2. installe [uv](https://docs.astral.sh/uv/) puis crée un environnement Python 3.12 dans
   `~/.venvs/docmorph`, sur le disque Linux, car `/mnt/d` est lent depuis WSL ;
3. installe PyTorch CUDA 12.6, DocMorph et Docling ;
4. télécharge une fois pour toutes les modèles Docling (`~/.cache/docling/models`) ;
5. affiche le diagnostic `python -m docmorph.doctor`.

Options :

- `--cpu` : PyTorch sans CUDA (pas de GPU NVIDIA) ;
- `--no-structure` : sans Docling (installation légère, sans mode « structure ») ;
- `--skip-apt` : ne touche pas aux paquets système.

**GPU.** Le pilote NVIDIA s'installe côté Windows ; WSL2 y accède directement (vérification :
`nvidia-smi`). PyTorch CUDA 12.6 est choisi parce que les versions plus récentes ne prennent
plus en charge les GPU Pascal (série GTX 10xx, Quadro Pxxx). Si le GPU n'est pas utilisable,
DocMorph bascule automatiquement sur le CPU.

## Lancement

```bash
bash scripts/run.sh
```

Ouvrez ensuite <http://localhost:8000> dans le navigateur Windows. Le serveur n'écoute que
sur `127.0.0.1`.

## Interface web

1. Déposez un ou plusieurs fichiers : le format de chacun est détecté (avec la mention
   « scanné » pour les PDF scannés).
2. Choisissez le format cible et, pour PDF vers Word, le mode :
   - **Fidèle à la mise en page** : rapide, conserve la mise en page ; les équations ne sont
     pas modifiables ;
   - **Structure modifiable** : texte, titres, tableaux et **équations Word modifiables** ;
     la mise en page d'origine n'est pas reproduite.
3. Cliquez sur **Convertir**, puis téléchargez chaque fichier ou le ZIP du lot.

## API REST

Documentation interactive : <http://localhost:8000/docs>.

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/api/formats` | Conversions disponibles, moteurs absents et raison |
| POST | `/api/detect` | `file` : format, PDF numérique ou scanné, cibles possibles |
| POST | `/api/convert` | `files` (multiple), `target`, `mode` (`auto`, `layout`, `structure`) |
| GET | `/api/jobs/{id}` | Statut d'une conversion (`queued`, `running`, `done`, `failed`) |
| GET | `/api/batches/{id}` | Statut de toutes les conversions d'un lot |
| GET | `/api/jobs/{id}/download` | Fichier converti |
| GET | `/api/batches/{id}/zip` | Tous les fichiers convertis du lot |

Exemple :

```bash
curl -F files=@article.pdf -F target=docx -F mode=structure http://localhost:8000/api/convert
curl http://localhost:8000/api/jobs/<id>
curl -OJ http://localhost:8000/api/jobs/<id>/download
```

En cas d'échec, `error.code` vaut `unsupported_format`, `conversion_not_available`,
`conversion_failed`, `file_too_large` ou `timeout`, et `error.message` explique le problème en
français.

## Configuration

| Variable | Défaut | Rôle |
|---|---|---|
| `DOCMORPH_DATA` | `~/.cache/docmorph` | Fichiers temporaires |
| `DOCMORPH_TTL_HOURS` | `24` | Durée de conservation des fichiers |
| `DOCMORPH_MAX_UPLOAD_MB` | `200` | Taille maximale par fichier |
| `DOCMORPH_OCR_LANGS` | `fra+eng+ara` | Langues Tesseract |
| `DOCMORPH_DEVICE` | `auto` | `cuda` ou `cpu` pour forcer le périphérique de Docling |
| `DOCMORPH_WORKERS` | `3` | Conversions simultanées (une seule utilise le GPU) |
| `DOCMORPH_PORT` | `8000` | Port d'écoute |

Les fichiers sont supprimés 24 h après la conversion, ainsi qu'à chaque redémarrage du serveur.

## Architecture

```
docmorph/
  core/      modèles, erreurs, détection de format, registre des conversions
  engines/   un module par moteur (LibreOffice, pdf2docx, Docling, OCR, img2pdf, PyMuPDF)
  api/       FastAPI, gestionnaire de tâches, stockage temporaire
  web/       interface HTML/JS sans framework
```

Chaque moteur déclare ses routes (format source, format cible, mode, type de PDF) et une
fonction `availability()`. Pour ajouter une conversion, il suffit d'écrire un moteur et de
l'ajouter à `default_engines()` dans `docmorph/engines/__init__.py`. Le registre gère aussi les
chaînes explicites (PDF vers DOCX puis DOC).

## Tests

```bash
source ~/.venvs/docmorph/bin/activate
pytest                                  # tests rapides ; ceux qui demandent LibreOffice ou Tesseract sont sautés s'ils manquent
DOCMORPH_TEST_STRUCTURE=1 pytest -m structure   # mode structure (lent, charge les modèles)
```
