import json
from pathlib import Path
from typing import Dict, Any, Optional
import time
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class CacheManager:
    """Gestionnaire de cache pour les métadonnées vidéo."""
    
    def __init__(self, cache_file: str = "cache/metadata_cache.json"):
        self.cache_file = Path(cache_file)
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.load_cache()

    def load_cache(self) -> None:
        """Charge le cache depuis le fichier."""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r') as f:
                    self.cache = json.load(f)
                self.clean_expired_entries()
        except Exception as e:
            logger.error(f"Erreur lors du chargement du cache : {e}")
            self.cache = {}

    def save_cache(self) -> None:
        """Sauvegarde le cache dans le fichier."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=4)
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde du cache : {e}")

    def get_metadata(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Récupère les métadonnées depuis le cache."""
        key = str(Path(file_path).resolve())
        entry = self.cache.get(key)
        
        if entry and self._is_entry_valid(entry, file_path):
            return entry["metadata"]
        return None

    def set_metadata(self, file_path: str, metadata: Dict[str, Any], 
                    duration_days: int = 7) -> None:
        """Stocke les métadonnées dans le cache."""
        key = str(Path(file_path).resolve())
        self.cache[key] = {
            "metadata": metadata,
            "timestamp": time.time(),
            "expires": (datetime.now() + timedelta(days=duration_days)).timestamp(),
            "file_size": Path(file_path).stat().st_size,
            "mtime": Path(file_path).stat().st_mtime
        }
        self.save_cache()

    def _is_entry_valid(self, entry: Dict[str, Any], file_path: str) -> bool:
        """Vérifie si une entrée du cache est toujours valide."""
        path = Path(file_path)
        if not path.exists():
            return False
            
        current_stats = path.stat()
        return (
            time.time() < entry["expires"] and
            current_stats.st_size == entry["file_size"] and
            current_stats.st_mtime == entry["mtime"]
        )

    def clean_expired_entries(self) -> None:
        """Nettoie les entrées expirées du cache."""
        current_time = time.time()
        expired = [
            key for key, entry in self.cache.items()
            if current_time > entry["expires"] or not Path(key).exists()
        ]
        
        for key in expired:
            del self.cache[key]
            
        if expired:
            self.save_cache()

    def clear_cache(self) -> None:
        """Vide complètement le cache."""
        self.cache.clear()
        self.save_cache()
