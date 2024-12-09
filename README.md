# Gestionnaire de Vidéos

Un outil puissant pour la gestion, la conversion et l'optimisation de vos fichiers vidéo.

## Fonctionnalités

- Conversion de vidéos vers différents formats
- Détection et gestion des doublons
- Réparation de fichiers vidéo corrompus
- Gestion intelligente des métadonnées
- Interface utilisateur interactive
- Support des expressions régulières pour le renommage

## Prérequis

- Python 3.8 ou supérieur
- FFmpeg installé sur le système
- Les dépendances Python listées dans requirements.txt

## Installation

1. Cloner le dépôt :
```bash
git clone [URL_DU_REPO]
cd convert
```

2. Installer les dépendances :
```bash
pip install -r requirements.txt
```

3. Vérifier que FFmpeg est installé :
```bash
ffmpeg -version
```

## Utilisation

Lancer l'application :
```bash
python main.py
```

Options disponibles :
- `-d, --directory` : Spécifier le dossier de travail
- `-v, --verbose` : Mode verbeux
- `--debug` : Mode debug

## Configuration

Le fichier `config/default_config.json` contient les paramètres par défaut :
- Formats vidéo supportés
- Paramètres de conversion
- Configuration de l'interface
- Paramètres de performance

## Tests

Lancer les tests :
```bash
pytest tests/
```

Vérification des types :
```bash
mypy .
```

## Structure du Projet

- `main.py` : Point d'entrée de l'application
- `ffmpeg_utils.py` : Utilitaires FFmpeg
- `file_utils.py` : Gestion des fichiers
- `duplicate_manager.py` : Gestion des doublons
- `cache_manager.py` : Système de cache
- `config_manager.py` : Gestion de la configuration
- `ui_manager.py` : Interface utilisateur
- `menu.py` : Menu interactif
- `tests/` : Tests unitaires
- `config/` : Fichiers de configuration

## Contribution

1. Fork le projet
2. Créer une branche pour votre fonctionnalité
3. Commiter vos changements
4. Pousser vers la branche
5. Ouvrir une Pull Request

## Licence

[Spécifier la licence]
