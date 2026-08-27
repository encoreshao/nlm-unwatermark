# nlm-unwatermark

![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-lightgrey.svg)
[![GitHub stars](https://img.shields.io/github/stars/encoreshao/nlm-unwatermark?style=social)](https://github.com/encoreshao/nlm-unwatermark/stargazers)
[![GitHub issues](https://img.shields.io/github/issues/encoreshao/nlm-unwatermark)](https://github.com/encoreshao/nlm-unwatermark/issues)

[English](README.md) | [中文](README_zh.md) | [Français](README_fr.md) | [日本語](README_ja.md)

Supprime le filigrane « NotebookLM » des exports PDF, PPTX et image (PNG/JPG/WEBP) grâce à de l'inpainting par vision par ordinateur plutôt qu'un simple aplat de couleur, afin de préserver dégradés, textures et bordures de diapositives.

## Avant / Après

| Avant | Après |
| --- | --- |
| ![Avant : page avec le filigrane NotebookLM](docs/images/before.png) | ![Après : filigrane supprimé, arrière-plan restauré](docs/images/after.png) |

## Table des matières

- [Avant / Après](#avant--après)
- [Fonctionnement](#fonctionnement)
- [Prérequis](#prérequis)
- [Installation](#installation)
- [Utilisation](#utilisation)
  - [Options](#options)
- [Exécutable autonome](#exécutable-autonome)
- [Structure du projet](#structure-du-projet)
- [Développement](#développement)
- [Contribuer](#contribuer)
- [Mentions légales et usage raisonnable](#mentions-légales-et-usage-raisonnable)
- [Licence](#licence)

## Fonctionnement

1. **Détection** — une analyse de contraste combinée à un appariement de gabarit de texte localise le filigrane, en ignorant le contenu voisin de la diapositive.
2. **Reconstruction** — l'arrière-plan situé sous le filigrane est reconstitué à partir d'une zone propre voisine de la même page (avec repli sur de l'inpainting si aucune zone propre n'est trouvée).
3. **Correction** — pour les PDF, le texte du filigrane est supprimé directement dans la couche de texte (rédaction, et non superposition), avec une retouche raster limitée pour l'icône ; les PPTX et images sont corrigés directement dans les pixels rendus.

## Prérequis

- Python 3.9 ou version ultérieure
- pip
- Dépendances (installées automatiquement) : [PyMuPDF](https://pypi.org/project/PyMuPDF/), [Pillow](https://pypi.org/project/Pillow/), [opencv-python-headless](https://pypi.org/project/opencv-python-headless/), [NumPy](https://pypi.org/project/numpy/), [tqdm](https://pypi.org/project/tqdm/)

## Installation

```bash
git clone https://github.com/encoreshao/nlm-unwatermark.git
cd nlm-unwatermark
python3 -m venv venv && source venv/bin/activate   # Windows : venv\Scripts\activate
pip install -r requirements.txt
pip install -e .           # optionnel — donne accès à la commande `nlm-unwatermark`
```

Vérifiez l'installation :

```bash
nlm-unwatermark --help
```

Si le message d'utilisation s'affiche, l'installation est prête.

## Utilisation

```bash
nlm-unwatermark file.pdf                # → file_cleaned.pdf
nlm-unwatermark file.pptx                # → file_cleaned.pptx
nlm-unwatermark slide.png                # → slide_cleaned.png
nlm-unwatermark ./my_folder/             # traite en lot tous les fichiers pris en charge d'un dossier
nlm-unwatermark file.pdf --preview       # PDF uniquement : ne traite que la première page
nlm-unwatermark file.pdf -o out.pdf      # chemin de sortie personnalisé
```

Vous n'avez pas exécuté `pip install -e .` ? Utilisez plutôt `python -m nlm_unwatermark file.pdf` — comportement identique.

### Options

| Option | Valeur par défaut | Description |
|---|---|---|
| `-o`, `--output` | `<nom>_cleaned.<ext>` | Chemin de sortie (traitement d'un seul fichier uniquement) |
| `--preview` | désactivé | PDF uniquement — ne traite que la première page |
| `--margin-x` | `400` | Largeur de recherche depuis le bord droit, en px |
| `--margin-y` | `120` | Hauteur de recherche depuis le bord inférieur, en px |
| `--threshold` | `22` | Seuil de contraste pour les pixels candidats |
| `--text-threshold` | `0.33` | Confiance d'appariement de gabarit requise pour compter comme texte |
| `--scale` | `3.5` | Facteur de rendu PDF / d'agrandissement d'image |
| `--radius` | `3` | Rayon d'inpainting (reconstruction de repli uniquement) |
| `--no-patch-heal` | désactivé | Utilise l'inpainting simple au lieu de la reconstruction par zone propre |
| `--debug` | désactivé | Enregistre les masques de détection dans `debug_watermark/` |

## Exécutable autonome

Vous ne voulez pas configurer Python ? Un exécutable autonome à fichier unique (sans interpréteur ni dépendances requises) peut être créé pour Windows, macOS et Linux — voir [Développement](#développement) ci-dessous.

```bash
# Windows
dist\nlm-unwatermark.exe file.pdf

# macOS / Linux
dist/nlm-unwatermark file.pdf
```

## Structure du projet

```
nlm_unwatermark/
├── cli.py              point d'entrée CLI (nlm-unwatermark / python -m nlm_unwatermark)
├── config.py            paramètres ajustables de détection/suppression
├── detection.py          localisation du filigrane (extraction de candidats + appariement de gabarit)
├── reconstruction.py      reconstruction d'arrière-plan / inpainting
├── engine.py              relie la détection et la reconstruction
└── formats/               processeurs par format : pdf.py, image.py, pptx.py
packaging/
├── entry_point.py         point d'entrée à imports absolus, compatible PyInstaller
└── nlm-unwatermark.spec   spécification de build PyInstaller
docs/
└── BUILD.md               instructions pour créer un exécutable autonome
```

## Développement

Configurez un environnement de développement local comme indiqué dans [Installation](#installation) — **à l'intérieur de cet environnement virtuel**, jamais depuis un interpréteur Python global/partagé — puis installez les dépendances de build si vous prévoyez d'empaqueter un exécutable :

```bash
python3 -m venv venv && source venv/bin/activate   # Windows : venv\Scripts\activate
pip install -r requirements.txt -r requirements-build.txt
python -m PyInstaller packaging/nlm-unwatermark.spec --noconfirm
```

> **Pourquoi un venv isolé est indispensable :** PyInstaller trace statiquement tous les imports qu'il peut trouver, y compris ceux atteints uniquement par des chemins de code optionnels et inutilisés (ex. `Table.to_pandas()` de PyMuPDF). Si vous construisez depuis un interpréteur partagé/global contenant des paquets lourds sans rapport (pandas, torch, etc.), PyInstaller peut les embarquer aussi, et le build peut échouer — une erreur du type `numpy.dtype size changed` signale généralement une paire `pandas`/`numpy` incompatible importée depuis l'extérieur de ce projet. Un venv propre ne contenant que `requirements.txt` + `requirements-build.txt` évite entièrement ce problème.

Les détails complets du build — y compris la raison pour laquelle la spec cible `packaging/entry_point.py` plutôt que `nlm_unwatermark/__main__.py` — se trouvent dans [docs/BUILD.md](docs/BUILD.md).

Le réglage du comportement de détection/suppression (marges, seuils, rayon d'inpainting, etc.) se trouve dans `nlm_unwatermark/config.py`, exposé sous forme d'options CLI dans `nlm_unwatermark/cli.py` — voir le tableau [Options](#options) ci-dessus.

## Contribuer

Les pull requests sont les bienvenues — [ouvrez une issue](https://github.com/encoreshao/nlm-unwatermark/issues/new) avant de commencer tout changement non trivial.

## Mentions légales et usage raisonnable

Utilisez cet outil uniquement sur des documents que vous possédez ou que vous avez le droit de modifier — l'usage qui en est fait relève de votre responsabilité. La suppression du filigrane est légitime lorsque vous êtes propriétaire du contenu généré (Google indique ne revendiquer aucune propriété sur les productions de NotebookLM) ; cet outil vise à vous aider à nettoyer vos propres exports. Il est fourni sous licence MIT, mais l'utiliser pour contourner les exigences d'attribution ou de paywall d'un service payant n'est pas un usage approuvé.

## Licence

MIT © 2026 [Encore Shao](LICENSE)
