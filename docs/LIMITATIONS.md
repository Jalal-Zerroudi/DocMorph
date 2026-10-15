# Limites de fidélité

DocMorph privilégie les conversions fiables. Ce document indique, pour chaque conversion, ce qui
est bien conservé et ce qui ne l'est pas.

## Office / ODF / TXT / RTF vers PDF (LibreOffice)

Fiabilité **élevée**.

- Le rendu dépend des polices installées. Les polices Microsoft (Calibri, Cambria) sont
  remplacées par des équivalents métriquement compatibles (Carlito, Caladea), ce qui conserve la
  pagination. D'autres polices absentes peuvent décaler le texte.
- Excel : les feuilles larges sont découpées sur plusieurs pages selon la zone d'impression
  définie dans le classeur. Une feuille sans mise en page prévue pour l'impression donne souvent
  un PDF peu lisible.
- PowerPoint : animations, transitions et vidéos sont perdues (une page par diapositive).
- SmartArt, macros, champs dynamiques complexes et certaines formes DOCX récentes peuvent
  être rendus de façon approximative.

## TXT / RTF vers DOCX, DOCX vers DOC (LibreOffice)

Fiabilité **élevée**. Les fichiers TXT sont lus en UTF-8, UTF-16 ou Windows-1252 (détection
automatique). Le format DOC (Word 97) ne gère pas certaines fonctions récentes de Word.

## JPG / PNG vers PDF (img2pdf)

Fiabilité **élevée** et sans perte : l'image est intégrée telle quelle, sans recompression.
Les PNG avec transparence sont aplatis sur fond blanc (seul cas où l'image est réencodée).
Chaque image donne un PDF distinct.

## PDF numérique vers TXT (PyMuPDF)

Fiabilité **élevée** pour le texte lui-même.

- L'ordre de lecture sur deux colonnes est reconstruit par une heuristique : colonne gauche,
  puis colonne droite, séparées par les blocs pleine largeur (titre, figures). Sur des pages
  majoritairement en arabe, la colonne droite est lue en premier. Les mises en page plus
  complexes (trois colonnes, encadrés) peuvent donner un ordre imparfait.
- Les équations sont extraites caractère par caractère (indices et exposants aplatis).
- Les PDF dont les polices n'ont pas de table Unicode produisent du texte illisible : dans ce
  cas, l'OCR est la seule solution.

## PDF vers Word : mode « fidèle à la mise en page » (pdf2docx)

Fiabilité **moyenne**. C'est la conversion la plus délicate : un PDF ne contient pas de
structure (paragraphes, tableaux, colonnes), seulement des positions de caractères.

- Ce qui fonctionne bien : texte simple, polices, couleurs, images, tableaux à bordures.
- Deux colonnes : souvent rendues par des sections ou des cadres, parfois mal découpées.
- Équations : jamais converties en équations Word ; elles deviennent du texte morcelé ou
  des images.
- Notes de bas de page, en-têtes et pieds de page : convertis en texte ordinaire.
- Arabe : le sens de lecture de droite à gauche n'est pas garanti ; la mise en forme des
  paragraphes peut nécessiter une retouche.
- Disponible uniquement pour les PDF numériques.

## PDF vers Word : mode « structure modifiable » (Docling + Pandoc)

Fiabilité de la **structure** : bonne ; fidélité de la **mise en page** : faible par conception.

- Docling (modèles d'IA locaux) reconnaît titres, paragraphes, listes, tableaux, figures et
  ordre de lecture sur deux colonnes, puis transcrit les formules en LaTeX. Pandoc les
  convertit en **équations Word natives et modifiables**.
- La mise en page d'origine (colonnes, positions, polices exactes) n'est pas reproduite : le
  document Word est sur une seule colonne, avec les styles Word par défaut.
- Seules les **équations isolées** (sur leur propre ligne) deviennent des équations Word.
  Les formules **dans le texte** (par exemple « pour tout $t > 0$ ») restent du texte simple :
  indices et exposants sont aplatis (`u0` au lieu de u₀).
- Les formules complexes (matrices, alignements sur plusieurs lignes) peuvent être mal
  reconnues ; une formule non interprétable par Pandoc reste affichée en LaTeX brut.
- Les numéros d'équation (1), (2) ne sont pas conservés.
- Les en-têtes et pieds de page répétés sont généralement supprimés.
- Pour les documents à dominante arabe, le document Word est marqué de droite à gauche.
- Plus lent : de quelques secondes par page sur GPU à plusieurs dizaines sur CPU. Avec 4 Go de
  mémoire graphique, un très gros document peut saturer le GPU : la conversion repasse alors
  automatiquement sur le CPU.

## PDF scanné vers TXT (OCRmyPDF + Tesseract)

- Langues : français, anglais et arabe (réglables via `DOCMORPH_OCR_LANGS`).
- Qualité directement liée à la numérisation : en dessous de 200 dpi, attendez-vous à des
  erreurs. Les pages sont redressées et réorientées automatiquement.
- L'arabe est moins bien reconnu que le français et l'anglais, surtout avec des polices
  calligraphiques ou une numérisation de faible qualité.
- Les équations ne sont pas reconnues correctement par Tesseract.

## PDF scanné vers DOCX (Docling avec OCR Tesseract + Pandoc)

Mêmes limites que le mode « structure », auxquelles s'ajoutent celles de l'OCR. Le mode
« fidèle » n'est pas proposé pour les PDF scannés : pdf2docx ne produirait que des images.

## Détection PDF numérique ou scanné

Une page est considérée comme scannée lorsqu'elle contient moins de 25 caractères extractibles
et que des images couvrent au moins la moitié de sa surface. Le document entier est traité
comme scanné si au moins la moitié de ses pages le sont (les 200 premières pages sont
analysées). Un PDF mixte majoritairement numérique est donc converti sans OCR ; ses pages
scannées restent sous forme d'images.

## Non pris en charge

- PDF protégés par mot de passe.
- Fichiers de plus de 200 Mo (réglable via `DOCMORPH_MAX_UPLOAD_MB`).
- PDF vers Excel ou PowerPoint, et la conversion des images en texte (non demandées).
