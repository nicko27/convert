
import json
import imagehash
from pathlib import Path
import numpy as np
import os

CONFIG_FILE = "config.json"

def update_video_formats(formats):
    """Met à jour la liste des formats vidéo dans la configuration."""
    config = load_config()
    config["video_formats"] = formats
    save_config(config)

def load_config():
    """Charge la configuration depuis le fichier JSON."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as file:
            return json.load(file)
    else:
        # Structure par défaut si le fichier n'existe pas
        config = {
            "directories_memory": {
                "last_directory": "",
                "saved_directories": []
            },
            "cleanup_keywords": [],
            "video_formats": [".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".webm"],
            "ignore_keyword": "cvt",
            "ignored_duplicates": {}
        }
        save_config(config)
        return config

def save_config(config):
    """Enregistre la configuration dans le fichier JSON."""
    with open(CONFIG_FILE, "w") as file:
        json.dump(config, file, indent=4)


def get_video_formats():
    """Retourne la liste des formats vidéo définis dans la configuration, ou une liste par défaut si non définie."""
    config = load_config()
    return config.get("video_formats", [".mp4", ".mkv", ".avi", ".mov"])

def set_video_formats(formats):
    """Met à jour et sauvegarde la liste des formats vidéo dans la configuration."""
    # Normalise les formats en minuscules et en enlevant les espaces
    normalized_formats = [fmt.strip().lower() for fmt in formats if fmt.strip()]
    config = load_config()
    config["video_formats"] = normalized_formats
    save_config(config)

def save_video_formats(formats: list) -> None:
    """Sauvegarde une liste de formats de fichiers vidéo dans le fichier JSON."""
    data = load_json_data()
    data["video_formats"] = formats
    save_json_data(data)

def load_json_data() -> dict:
    """Charge les données du fichier JSON de configuration, renvoie un dictionnaire par défaut si le fichier est corrompu ou inexistant."""
    if not os.path.exists(CONFIG_FILE):
        return {"last_directories": {}, "video_metadata": {}, "ignored_duplicates": {}, "video_formats": [".mp4", ".mkv", ".avi", ".mov"]}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        # Si le fichier est corrompu, réinitialiser avec des valeurs par défaut
        data = {"last_directories": {}, "video_metadata": {}, "ignored_duplicates": {}, "video_formats": [".mp4", ".mkv", ".avi", ".mov"]}
        save_json_data(data)
    
    # Convertir les hash en ImageHash et audio_signature en ndarray si nécessaire
    for video_path, metadata in data.get("video_metadata", {}).items():
        if "hashes" in metadata:
            metadata["hashes"] = [imagehash.hex_to_hash(h) if isinstance(h, str) else h for h in metadata["hashes"]]
        if "audio_signature" in metadata and isinstance(metadata["audio_signature"], list):
            metadata["audio_signature"] = np.array(metadata["audio_signature"])  # Convertir en ndarray
    return data

def save_json_data(data: dict) -> None:
    """Enregistre les données dans le fichier JSON de configuration, en convertissant les types non compatibles JSON."""
    for video_path, metadata in data.get("video_metadata", {}).items():
        if "hashes" in metadata:
            metadata["hashes"] = [str(h) for h in metadata["hashes"]]  # Convertir les hash en chaînes
        if "audio_signature" in metadata and isinstance(metadata["audio_signature"], np.ndarray):
            metadata["audio_signature"] = metadata["audio_signature"].tolist()  # Convertir ndarray en liste

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def remember_directory(directory: str, function: str) -> None:
    """Sauvegarde le dernier répertoire utilisé pour une fonction spécifique dans config.json."""
    data = load_json_data()
    if "last_directories" not in data:
        data["last_directories"] = {}
    data["last_directories"][function] = directory  # Sauvegarde le dossier pour la fonction donnée
    save_json_data(data)

def get_last_directory(function: str) -> str:
    """Récupère le dernier répertoire utilisé pour une fonction spécifique, ou une chaîne vide si non défini."""
    data = load_json_data()
    return data.get("last_directories", {}).get(function, "")

def load_ignored_duplicates() -> dict:
    """Charge les doublons ignorés depuis le fichier JSON."""
    data = load_json_data()
    return data.get("ignored_duplicates", {})

def save_ignored_duplicates(ignored_duplicates: dict) -> None:
    """Enregistre les doublons ignorés dans le fichier JSON."""
    data = load_json_data()
    data["ignored_duplicates"] = ignored_duplicates
    save_json_data(data)

def get_video_formats() -> list:
    """Récupère les formats de fichiers vidéo depuis le fichier JSON ou renvoie une liste par défaut."""
    data = load_json_data()
    return data.get("video_formats", [".mp4", ".mkv", ".avi", ".mov"])

def save_video_formats(formats: list) -> None:
    """Sauvegarde une liste de formats de fichiers vidéo dans le fichier JSON."""
    data = load_json_data()
    data["video_formats"] = formats
    save_json_data(data)
