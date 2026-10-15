# DocMorph - Conception

Date : 2026-10-15

## Intention

Convertisseur de documents personnel, 100 % local sous WSL2 Ubuntu, sans API externe ni
service cloud. Utilisé par une seule personne, sur son PC, via une interface web minimale.
La conversion prioritaire est **PDF vers Word** appliquée à des **articles et mémoires
scientifiques** (deux colonnes, équations, figures, références) en **français, anglais et arabe**.

## Objectifs

- Convertir : DOC/DOCX, XLS/XLSX, PPT/PPTX, ODT/ODS/ODP, TXT/RTF vers PDF ; TXT/RTF vers DOCX ;
  JPG/PNG vers PDF ; PDF vers DOCX/DOC/TXT ; PDF scanné vers TXT/DOCX (OCR).
- Détecter automatiquement le format d'entrée et distinguer PDF numérique et PDF scanné.
- N'annoncer que les conversions réellement possibles sur la machine.
- PDF vers Word en deux modes :
  - **fidèle** (mise en page conservée au mieux) ;
  - **structure** (texte, titres, tableaux, figures et équations Word modifiables).
- Plusieurs fichiers à la fois, téléchargement individuel ou en ZIP.
- Fonctionnement hors ligne après installation.

## Non-objectifs

- Multi-utilisateurs, authentification, exposition sur le réseau.
- Historique des conversions, CLI (non demandés).
- Dépendance à Microsoft Office ou à un service payant.

## Anti-objectifs

- Annoncer une conversion qui produit un résultat inutilisable sans le dire.
- Conversions approximatives multipliées au détriment de la fiabilité.

## Contraintes

- Outils gratuits et open source uniquement.
- WSL2 Ubuntu (machine cible : Ubuntu 26.04, GPU Quadro P620 4 Go, architecture Pascal).
- Limites de fidélité documentées (`docs/LIMITATIONS.md`).

## Moteurs

| Conversion | Moteur |
|---|---|
| Office / ODF / TXT / RTF vers PDF | LibreOffice headless |
| TXT / RTF vers DOCX, DOCX vers DOC | LibreOffice headless |
| JPG / PNG vers PDF | img2pdf (sans recompression) |
| PDF numérique vers TXT | PyMuPDF (ordre de lecture par blocs) |
| PDF scanné vers TXT | OCRmyPDF (Tesseract fra+eng+ara) puis PyMuPDF |
| PDF vers DOCX, mode fidèle | pdf2docx |
| PDF vers DOCX, mode structure | Docling (formules en LaTeX) puis Pandoc (LaTeX vers équations Word) |
| PDF scanné vers DOCX | Docling avec OCR Tesseract puis Pandoc |
| PDF vers DOC | chaîne PDF vers DOCX puis LibreOffice |

## Architecture

- `docmorph/core` : modèles (formats, modes, statuts), erreurs typées, détection, registre.
- `docmorph/engines` : un module par moteur. Chaque moteur déclare ses routes
  `(source, cible, mode)` et `is_available()`.
- Le registre résout une route directe ou une chaîne courte explicite (PDF vers DOCX puis DOC).
- `docmorph/api` : FastAPI, gestionnaire de tâches en arrière-plan, stockage temporaire.
- `docmorph/web` : HTML/JS/CSS sans framework, servis par FastAPI.

Tâches : exécutées dans un pool de threads ; un sémaphore limite à une conversion Docling
à la fois (GPU), un autre limite LibreOffice. Chaque appel LibreOffice utilise un profil
utilisateur temporaire distinct.

Stockage : `~/.cache/docmorph` (système de fichiers Linux), purge après 24 h,
200 Mo maximum par fichier. Écoute sur `127.0.0.1` uniquement.

## API

- `GET /api/formats`
- `POST /api/detect`
- `POST /api/convert` (multi-fichiers, `target`, `mode`)
- `GET /api/jobs/{id}`, `GET /api/jobs/{id}/download`, `GET /api/batches/{id}/zip`

Erreurs : `UnsupportedFormat`, `ConversionNotAvailable`, `ConversionFailed`, `FileTooLarge`,
`Timeout`.

## Choix du constructeur

- Docling plutôt que Marker (licence MIT).
- Environnement virtuel natif plutôt que Docker.
- Python 3.12 via `uv` : Ubuntu 26.04 fournit Python 3.14, pas encore couvert par toutes les
  dépendances de Docling.
- PyTorch CUDA 12.6 : les versions CUDA plus récentes ne prennent plus en charge les GPU Pascal.
  Docling choisit le GPU s'il est utilisable, sinon le CPU (`DOCMORPH_DEVICE` pour forcer).
- Avec 4 Go de VRAM, le modèle de formules peut manquer de mémoire sur de gros documents ;
  la conversion bascule alors automatiquement sur le CPU.
- Interface : statut par fichier (en cours, terminé, échec) en plus du strict minimum demandé.
