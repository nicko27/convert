import os
import shutil
from send2trash import send2trash
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
from config_manager import config
from ui_manager import ui
import json

class FileManager:
    """Gestionnaire de fichiers avec fonctionnalités avancées."""
    
    def __init__(self):
        """Initialise le gestionnaire de fichiers."""
        self.video_formats = config.get_video_formats()
        self.operations_log = []
    
    def _log_operation(self, operation: str, source: str, destination: str = None, success: bool = True, error: str = None) -> None:
        """
        Enregistre une opération dans le journal.
        
        Args:
            operation (str): Type d'opération
            source (str): Fichier ou dossier source
            destination (str, optional): Destination si applicable
            success (bool): Succès de l'opération
            error (str, optional): Message d'erreur si échec
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'operation': operation,
            'source': source,
            'destination': destination,
            'success': success,
            'error': error,
            'file_size': os.path.getsize(source) if os.path.exists(source) else None,
            'file_type': os.path.splitext(source)[1] if source else None
        }
        self.operations_log.append(log_entry)
        
        # Sauvegarder le journal dans un fichier JSON
        self._save_log()
        
        # Notifier l'interface utilisateur
        if not success:
            ui.show_error(f"Erreur lors de {operation}: {error}")
        elif operation != 'check':  # Éviter de spammer les logs pour les vérifications
            ui.show_info(f"Opération {operation} réussie sur {os.path.basename(source)}")
    
    def _save_log(self) -> None:
        """Sauvegarde le journal des opérations dans un fichier JSON."""
        try:
            log_file = Path('logs/operations.json')
            log_file.parent.mkdir(exist_ok=True)
            
            # Garder uniquement les 1000 dernières entrées
            recent_logs = self.operations_log[-1000:]
            
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(recent_logs, f, indent=2, ensure_ascii=False)
        except Exception as e:
            ui.show_warning(f"Impossible de sauvegarder le journal: {e}")

    def get_video_files(self, directory: str) -> List[Path]:
        """
        Trouve tous les fichiers vidéo dans un dossier et ses sous-dossiers.
        
        Args:
            directory (str): Dossier à analyser
            
        Returns:
            List[Path]: Liste des fichiers vidéo trouvés
        """
        video_files = []
        try:
            for ext in self.video_formats:
                video_files.extend(Path(directory).rglob(f"*{ext}"))
            return sorted(video_files)
        except Exception as e:
            ui.show_error(f"Erreur lors de la recherche des fichiers vidéo : {str(e)}")
            return []
    
    def get_folder_stats(self, directory: str) -> Dict:
        """
        Calcule les statistiques d'un dossier.
        
        Args:
            directory (str): Dossier à analyser
            
        Returns:
            Dict: Statistiques du dossier
        """
        try:
            stats = {
                'total_size': 0,
                'file_count': 0,
                'video_count': 0,
                'video_size': 0,
                'subdirs': 0
            }
            
            for root, dirs, files in os.walk(directory):
                stats['subdirs'] += len(dirs)
                for file in files:
                    file_path = Path(root) / file
                    size = file_path.stat().st_size
                    stats['total_size'] += size
                    stats['file_count'] += 1
                    if any(file.lower().endswith(ext) for ext in self.video_formats):
                        stats['video_count'] += 1
                        stats['video_size'] += size
            
            return stats
        except Exception as e:
            ui.show_error(f"Erreur lors du calcul des statistiques : {str(e)}")
            return {}
    
    def copy_folder_contents(self, source: str, destination: str, include_root: bool = False,
                           delete_after_copy: bool = False) -> bool:
        """
        Copie les fichiers vidéo d'un dossier vers un autre.
        
        Args:
            source (str): Dossier source
            destination (str): Dossier de destination
            include_root (bool): Inclure le dossier racine
            delete_after_copy (bool): Supprimer les fichiers source après copie
            
        Returns:
            bool: True si succès
        """
        try:
            source_path = Path(source)
            dest_path = Path(destination)
            
            if not source_path.exists():
                ui.show_error(f"Le dossier source n'existe pas : {source}")
                return False
            
            # Créer le dossier de destination si nécessaire
            dest_path.mkdir(parents=True, exist_ok=True)
            
            # Trouver tous les fichiers vidéo
            files_to_copy = self.get_video_files(source)
            if not files_to_copy:
                ui.show_warning("Aucun fichier vidéo trouvé dans le dossier source")
                return False
            
            # Calculer l'espace nécessaire
            total_size = sum(f.stat().st_size for f in files_to_copy)
            free_space = shutil.disk_usage(destination).free
            if total_size > free_space:
                ui.show_error("Espace disque insuffisant pour la copie")
                return False
            
            # Copier les fichiers avec progression
            with ui.show_progress(len(files_to_copy)) as progress:
                task = progress.add_task("Copie des fichiers...", total=len(files_to_copy))
                
                for file_path in files_to_copy:
                    try:
                        # Calculer le chemin de destination
                        rel_path = file_path.relative_to(source_path)
                        if not include_root:
                            rel_path = Path(*rel_path.parts[1:]) if len(rel_path.parts) > 1 else rel_path
                        
                        dest_file = dest_path / rel_path
                        
                        # Créer les sous-dossiers nécessaires
                        dest_file.parent.mkdir(parents=True, exist_ok=True)
                        
                        # Vérifier si le fichier existe déjà
                        if dest_file.exists():
                            if dest_file.stat().st_size == file_path.stat().st_size:
                                ui.show_warning(f"Fichier déjà existant (même taille) : {rel_path}")
                                continue
                            else:
                                # Renommer avec un suffixe numérique
                                counter = 1
                                while dest_file.exists():
                                    new_name = f"{dest_file.stem}_{counter}{dest_file.suffix}"
                                    dest_file = dest_file.with_name(new_name)
                                    counter += 1
                        
                        # Copier le fichier
                        shutil.copy2(file_path, dest_file)
                        
                        # Supprimer l'original si demandé
                        if delete_after_copy:
                            send2trash(str(file_path))
                            ui.show_info(f"Fichier déplacé vers la corbeille : {rel_path}")
                        
                        self._log_operation('copy', str(file_path), str(dest_file))
                        
                    except Exception as e:
                        ui.show_error(f"Erreur lors de la copie de {file_path.name} : {str(e)}")
                        self._log_operation('copy', str(file_path), str(dest_file), False, str(e))
                    
                    progress.update(task, advance=1)
            
            ui.show_success("Copie terminée avec succès !")
            return True
            
        except Exception as e:
            ui.show_error(f"Erreur lors de la copie du dossier : {str(e)}")
            self._log_operation('copy_folder', source, destination, False, str(e))
            return False
    
    def move_folder_contents(self, source: str, destination: str, include_root: bool = False) -> bool:
        """
        Déplace les fichiers vidéo d'un dossier vers un autre.
        
        Args:
            source (str): Dossier source
            destination (str): Dossier de destination
            include_root (bool): Inclure le dossier racine
            
        Returns:
            bool: True si succès
        """
        return self.copy_folder_contents(source, destination, include_root, delete_after_copy=True)
    
    def cleanup_empty_folders(self, directory: str) -> int:
        """
        Supprime les dossiers vides récursivement.
        
        Args:
            directory (str): Dossier à nettoyer
            
        Returns:
            int: Nombre de dossiers supprimés
        """
        count = 0
        try:
            for root, dirs, _ in os.walk(directory, topdown=False):
                for d in dirs:
                    dir_path = Path(root) / d
                    try:
                        if not any(dir_path.iterdir()):
                            dir_path.rmdir()
                            count += 1
                            self._log_operation('remove_empty_dir', str(dir_path))
                            ui.show_info(f"Dossier vide supprimé : {dir_path}")
                    except Exception as e:
                        ui.show_error(f"Erreur lors de la suppression du dossier vide {dir_path} : {str(e)}")
                        self._log_operation('remove_empty_dir', str(dir_path), success=False, error=str(e))
            
            return count
            
        except Exception as e:
            ui.show_error(f"Erreur lors du nettoyage des dossiers vides : {str(e)}")
            return count

    def copy_folder_structure(self, source: str, destination: str) -> bool:
        """
        Copie uniquement la structure des dossiers sans les fichiers.
        
        Args:
            source (str): Dossier source
            destination (str): Dossier de destination
            
        Returns:
            bool: True si succès
        """
        try:
            source_path = Path(source)
            dest_path = Path(destination)
            
            if not source_path.exists():
                ui.show_error(f"Le dossier source n'existe pas : {source}")
                return False
            
            # Créer le dossier de destination s'il n'existe pas
            dest_path.mkdir(parents=True, exist_ok=True)
            
            # Parcourir et copier la structure
            for dir_path in source_path.rglob('*'):
                if dir_path.is_dir():
                    # Calculer le chemin relatif et créer le dossier correspondant
                    rel_path = dir_path.relative_to(source_path)
                    new_dir = dest_path / rel_path
                    
                    try:
                        new_dir.mkdir(parents=True, exist_ok=True)
                        self._log_operation('copy_structure', str(dir_path), str(new_dir))
                        ui.show_info(f"Dossier créé : {new_dir}")
                    except Exception as e:
                        ui.show_error(f"Erreur lors de la création du dossier {new_dir} : {str(e)}")
                        self._log_operation('copy_structure', str(dir_path), str(new_dir), 
                                         success=False, error=str(e))
            
            ui.show_success("Structure du dossier copiée avec succès !")
            return True
            
        except Exception as e:
            ui.show_error(f"Erreur lors de la copie de la structure : {str(e)}")
            self._log_operation('copy_structure', source, destination, success=False, error=str(e))
            return False

    def get_operation_stats(self) -> Dict[str, Any]:
        """
        Retourne des statistiques sur les opérations effectuées.
        
        Returns:
            Dict[str, Any]: Statistiques des opérations
        """
        stats = {
            'total_operations': len(self.operations_log),
            'success_rate': 0,
            'operations_by_type': {},
            'total_size_processed': 0,
            'errors_by_type': {},
            'most_common_errors': []
        }
        
        for op in self.operations_log:
            op_type = op['operation']
            stats['operations_by_type'][op_type] = stats['operations_by_type'].get(op_type, 0) + 1
            
            if op['success']:
                stats['success_rate'] += 1
            elif op['error']:
                error_type = op['error'].split(':')[0]
                stats['errors_by_type'][error_type] = stats['errors_by_type'].get(error_type, 0) + 1
            
            if op.get('file_size'):
                stats['total_size_processed'] += op['file_size']
        
        if stats['total_operations'] > 0:
            stats['success_rate'] = (stats['success_rate'] / stats['total_operations']) * 100
            
        # Trier les erreurs par fréquence
        stats['most_common_errors'] = sorted(
            stats['errors_by_type'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        return stats

    def save_operations_log(self, log_file: str) -> bool:
        """
        Sauvegarde le journal des opérations dans un fichier.
        
        Args:
            log_file (str): Fichier de sortie
            
        Returns:
            bool: True si succès
        """
        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                for op in self.operations_log:
                    f.write(f"{op['timestamp']} - {op['operation']} - ")
                    f.write(f"Source: {op['source']}")
                    if op['destination']:
                        f.write(f" - Destination: {op['destination']}")
                    f.write(f" - Succès: {op['success']}")
                    if op['error']:
                        f.write(f" - Erreur: {op['error']}")
                    f.write("\n")
            ui.show_success(f"Journal des opérations sauvegardé dans {log_file}")
            return True
            
        except Exception as e:
            ui.show_error(f"Erreur lors de la sauvegarde du journal : {str(e)}")
            return False

# Instance globale du gestionnaire de fichiers
file_manager = FileManager()
