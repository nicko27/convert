import json
import imagehash
from pathlib import Path
import numpy as np
import os
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from ui_manager import ui

class ConfigManager:
    """Gestionnaire de configuration centralisé pour l'application."""
    
    DEFAULT_CONFIG = {
        "app_settings": {
            "video_formats": [".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".webm"],
            "max_threads": os.cpu_count(),
            "repair_threshold": 0.8,
            "similarity_threshold": 0.9,
            "default_language": "fr",
            "save_backups": True,
            "backup_interval_days": 7
        },
        "directories": {
            "last_used": {},
            "favorites": [],
            "excluded": []
        },
        "video_metadata": {},
        "ignored_duplicates": set(),
        "last_backup": None
    }
    
    def __init__(self, config_file: str = "config.json"):
        """
        Initialise le gestionnaire de configuration.
        
        Args:
            config_file (str): Chemin vers le fichier de configuration
        """
        self.config_file = config_file
        self.config = self._load_config()
        self._check_backup()
    
    def _load_config(self) -> Dict:
        """
        Charge la configuration depuis le fichier JSON.
        
        Returns:
            Dict: Configuration chargée ou configuration par défaut
        """
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                # Mise à jour avec les nouvelles clés par défaut
                self._update_config_structure(config)
            else:
                config = self.DEFAULT_CONFIG.copy()
                self._save_config(config)
            return config
        except Exception as e:
            ui.show_error(f"Erreur lors du chargement de la configuration : {str(e)}")
            return self.DEFAULT_CONFIG.copy()
    
    def _save_config(self, config: Dict) -> None:
        """
        Sauvegarde la configuration dans le fichier JSON.
        
        Args:
            config (Dict): Configuration à sauvegarder
        """
        try:
            # Créer une copie pour la sauvegarde
            save_config = config.copy()
            
            # Convertir les types non-JSON
            if "video_metadata" in save_config:
                for metadata in save_config["video_metadata"].values():
                    if "hashes" in metadata:
                        metadata["hashes"] = [str(h) for h in metadata["hashes"]]
                    if "audio_signature" in metadata:
                        if isinstance(metadata["audio_signature"], np.ndarray):
                            metadata["audio_signature"] = metadata["audio_signature"].tolist()
            
            # Convertir set en list pour la sérialisation JSON
            if "ignored_duplicates" in save_config:
                save_config["ignored_duplicates"] = list(save_config["ignored_duplicates"])
            
            # Sauvegarder avec backup
            if self.get_setting("save_backups"):
                self._create_backup()
            
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(save_config, f, indent=4)
                
        except Exception as e:
            ui.show_error(f"Erreur lors de la sauvegarde de la configuration : {str(e)}")
    
    def _update_config_structure(self, config: Dict) -> None:
        """
        Met à jour la structure de la configuration avec les nouvelles clés par défaut.
        
        Args:
            config (Dict): Configuration à mettre à jour
        """
        def deep_update(source: Dict, target: Dict) -> Dict:
            for key, value in source.items():
                if key not in target:
                    target[key] = value
                elif isinstance(value, dict) and isinstance(target[key], dict):
                    deep_update(value, target[key])
            return target
        
        self.config = deep_update(self.DEFAULT_CONFIG, config)
    
    def _check_backup(self) -> None:
        """Vérifie si une sauvegarde est nécessaire selon l'intervalle configuré."""
        if not self.get_setting("save_backups"):
            return
            
        last_backup = self.config.get("last_backup")
        if last_backup:
            last_backup = datetime.fromisoformat(last_backup)
            days_since_backup = (datetime.now() - last_backup).days
            if days_since_backup >= self.get_setting("backup_interval_days"):
                self._create_backup()
        else:
            self._create_backup()
    
    def _create_backup(self) -> None:
        """Crée une sauvegarde du fichier de configuration."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"{self.config_file}.{timestamp}.bak"
            
            if os.path.exists(self.config_file):
                import shutil
                shutil.copy2(self.config_file, backup_file)
                self.config["last_backup"] = datetime.now().isoformat()
                ui.show_info(f"Sauvegarde créée : {backup_file}")
        except Exception as e:
            ui.show_error(f"Erreur lors de la création de la sauvegarde : {str(e)}")
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Récupère un paramètre de configuration.
        
        Args:
            key (str): Clé du paramètre
            default (Any, optional): Valeur par défaut si la clé n'existe pas
            
        Returns:
            Any: Valeur du paramètre
        """
        return self.config["app_settings"].get(key, default)
    
    def set_setting(self, key: str, value: Any) -> None:
        """
        Définit un paramètre de configuration.
        
        Args:
            key (str): Clé du paramètre
            value (Any): Nouvelle valeur
        """
        self.config["app_settings"][key] = value
        self._save_config(self.config)
    
    def remember_directory(self, directory: str, function: str) -> None:
        """
        Mémorise un répertoire pour une fonction spécifique.
        
        Args:
            directory (str): Chemin du répertoire
            function (str): Nom de la fonction
        """
        self.config["directories"]["last_used"][function] = directory
        self._save_config(self.config)
    
    def get_last_directory(self, function: str) -> str:
        """
        Récupère le dernier répertoire utilisé pour une fonction.
        
        Args:
            function (str): Nom de la fonction
            
        Returns:
            str: Chemin du dernier répertoire utilisé ou chaîne vide
        """
        return self.config["directories"]["last_used"].get(function, "")
    
    def add_favorite_directory(self, directory: str) -> None:
        """
        Ajoute un répertoire aux favoris.
        
        Args:
            directory (str): Chemin du répertoire
        """
        if directory not in self.config["directories"]["favorites"]:
            self.config["directories"]["favorites"].append(directory)
            self._save_config(self.config)
    
    def remove_favorite_directory(self, directory: str) -> None:
        """
        Retire un répertoire des favoris.
        
        Args:
            directory (str): Chemin du répertoire
        """
        if directory in self.config["directories"]["favorites"]:
            self.config["directories"]["favorites"].remove(directory)
            self._save_config(self.config)
    
    def get_video_formats(self) -> List[str]:
        """
        Récupère la liste des formats vidéo supportés.
        
        Returns:
            List[str]: Liste des extensions de fichiers vidéo
        """
        return self.get_setting("video_formats")
    
    def set_video_formats(self, formats: List[str]) -> None:
        """
        Définit la liste des formats vidéo supportés.
        
        Args:
            formats (List[str]): Liste des extensions de fichiers vidéo
        """
        # Normaliser les formats
        normalized = [fmt.strip().lower() for fmt in formats if fmt.strip()]
        self.set_setting("video_formats", normalized)
    
    def add_ignored_duplicate(self, file1: str, file2: str) -> None:
        """
        Ajoute une paire de fichiers aux doublons ignorés.
        
        Args:
            file1 (str): Premier fichier
            file2 (str): Second fichier
        """
        pair = tuple(sorted([file1, file2]))
        self.config["ignored_duplicates"].add(pair)
        self._save_config(self.config)
    
    def is_ignored_duplicate(self, file1: str, file2: str) -> bool:
        """
        Vérifie si une paire de fichiers est dans les doublons ignorés.
        
        Args:
            file1 (str): Premier fichier
            file2 (str): Second fichier
            
        Returns:
            bool: True si la paire est ignorée
        """
        pair = tuple(sorted([file1, file2]))
        return pair in self.config["ignored_duplicates"]
    
    def clear_ignored_duplicates(self) -> None:
        """Efface la liste des doublons ignorés."""
        self.config["ignored_duplicates"].clear()
        self._save_config(self.config)

# Instance globale du gestionnaire de configuration
config = ConfigManager()
