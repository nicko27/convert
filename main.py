#!/usr/bin/env python3

import sys
import logging
import argparse
from pathlib import Path
from rich.traceback import install
from ui_manager import ui
from menu import display_menu
from config_manager import config

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('video_manager.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Installation du gestionnaire d'erreurs Rich
install(show_locals=True)

def parse_args():
    """Parse les arguments en ligne de commande."""
    parser = argparse.ArgumentParser(description="Gestionnaire de vidéos avancé")
    parser.add_argument("-d", "--directory", type=str, help="Dossier de travail initial")
    parser.add_argument("-v", "--verbose", action="store_true", help="Mode verbeux")
    parser.add_argument("--debug", action="store_true", help="Mode debug")
    return parser.parse_args()

def main():
    """Point d'entrée principal de l'application."""
    try:
        # Parser les arguments
        args = parse_args()
        
        # Configurer le niveau de log
        if args.debug:
            logging.getLogger().setLevel(logging.DEBUG)
        elif args.verbose:
            logging.getLogger().setLevel(logging.INFO)
        else:
            logging.getLogger().setLevel(logging.WARNING)
        
        # Définir le dossier de travail initial si spécifié
        if args.directory:
            directory = Path(args.directory)
            if not directory.exists():
                ui.show_error(f"Le dossier spécifié n'existe pas : {directory}")
                return 1
            config.set_last_directory(str(directory))
        
        # Afficher le message de bienvenue
        ui.show_title("Bienvenue dans le gestionnaire de vidéos !")
        
        # Lancer le menu principal
        display_menu()
        
        return 0
        
    except KeyboardInterrupt:
        ui.show_warning("\nOpération annulée par l'utilisateur")
        return 130
    except Exception as e:
        logger.exception("Erreur inattendue dans l'application")
        ui.show_error(f"Une erreur inattendue s'est produite : {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
