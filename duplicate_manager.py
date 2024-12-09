from moviepy.editor import VideoFileClip
from PIL import Image
import imagehash
import librosa
import numpy as np
from scipy.spatial.distance import hamming
import json
import os
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from send2trash import send2trash
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from config_manager import config
from video_utils import get_audio_signature
from ui_manager import ui
from ffmpeg_utils import repair_video

class DuplicateReason:
    """Classe pour stocker et expliquer les raisons de similarité entre deux vidéos."""
    
    def __init__(self):
        self.reasons: List[str] = []
        self.scores: Dict[str, float] = {}
        self.total_score: float = 0.0
    
    def add_reason(self, name: str, score: float, details: Optional[str] = None) -> None:
        """
        Ajoute une raison de similarité avec son score.
        
        Args:
            name: Nom de la métrique de comparaison
            score: Score de similarité (entre 0 et 1)
            details: Détails optionnels sur la comparaison
        """
        self.scores[name] = score
        if details:
            self.reasons.append(f"{name} ({score:.1%}): {details}")
        else:
            self.reasons.append(f"{name}: {score:.1%}")
        self.total_score = sum(self.scores.values()) / len(self.scores)
    
    def get_summary(self) -> str:
        """Retourne un résumé des raisons de similarité."""
        if not self.reasons:
            return "Aucune raison de similarité"
        return "\n".join([f"- {reason}" for reason in self.reasons])
    
    def get_total_score(self) -> float:
        """Retourne le score total de similarité."""
        return self.total_score

class VideoInfo:
    """Classe pour stocker et gérer les informations d'une vidéo."""
    
    def __init__(self, file_path: str):
        """
        Initialise une nouvelle instance de VideoInfo.
        
        Args:
            file_path: Chemin vers le fichier vidéo
        """
        self.file_path = str(Path(file_path))
        self.info: Dict[str, Any] = {}
        self.is_corrupted: bool = False
        self.is_repaired: bool = False
        self.repair_path: Optional[str] = None
        self.error: Optional[str] = None
    
    def analyze(self, metadata_cache: Optional[Dict] = None, try_repair: bool = False) -> bool:
        """
        Analyse la vidéo et stocke ses informations.
        
        Args:
            metadata_cache: Cache optionnel des métadonnées
            try_repair: Si True, tente de réparer la vidéo si elle est corrompue
            
        Returns:
            True si l'analyse a réussi, False sinon
        """
        try:
            # Vérifier le cache
            if metadata_cache and self.file_path in metadata_cache:
                cached_data = metadata_cache[self.file_path]
                # Vérifier si les données du cache sont toujours valides
                if self._is_cache_valid(cached_data):
                    self.info = cached_data
                    return True
            
            file_path = Path(self.file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"Le fichier n'existe pas : {self.file_path}")
            
            # Extraire les métadonnées de base
            self._extract_basic_metadata(file_path)
            
            # Analyser le contenu vidéo
            with VideoFileClip(self.file_path) as video:
                self._analyze_video_content(video)
                
                # Analyser l'audio si présent
                if video.audio:
                    self._analyze_audio_content()
            
            # Mettre en cache les résultats
            if metadata_cache is not None:
                metadata_cache[self.file_path] = self.info
            
            return True
            
        except Exception as e:
            self._handle_analysis_error(e, try_repair)
            return False

    def _is_cache_valid(self, cached_data: Dict) -> bool:
        """Vérifie si les données en cache sont toujours valides."""
        try:
            file_stats = Path(self.file_path).stat()
            return (
                cached_data.get("file_size") == file_stats.st_size and
                cached_data.get("modification_time") == file_stats.st_mtime
            )
        except Exception:
            return False

    def _extract_basic_metadata(self, file_path: Path) -> None:
        """Extrait les métadonnées de base du fichier."""
        stats = file_path.stat()
        self.info.update({
            "file_size": stats.st_size,
            "creation_time": stats.st_ctime,
            "modification_time": stats.st_mtime,
            "last_analyzed": datetime.now().isoformat()
        })

    def _analyze_video_content(self, video: VideoFileClip) -> None:
        """Analyse le contenu de la vidéo."""
        if video.duration <= 0:
            raise ValueError("La durée de la vidéo est invalide")
        
        self.info.update({
            "duration": video.duration,
            "resolution": (video.w, video.h),
            "fps": video.fps,
            "has_audio": video.audio is not None,
            "frame_count": int(video.duration * video.fps)
        })
        
        # Extraire des frames à des moments clés
        self._extract_key_frames(video)
        
        # Analyser les codecs
        try:
            self.info["codec_info"] = video.reader.infos
        except Exception as e:
            ui.show_warning(f"Impossible de récupérer les infos codec : {e}")
            self.info["codec_info"] = {}

    def _extract_key_frames(self, video: VideoFileClip) -> None:
        """Extrait et analyse les frames clés de la vidéo."""
        frame_times = [0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0]
        self.info["hashes"] = []
        self.info["scene_changes"] = []
        last_frame = None
        
        for t in [p * video.duration for p in frame_times]:
            try:
                frame = video.get_frame(t)
                frame_hash = str(imagehash.average_hash(Image.fromarray(frame)))
                self.info["hashes"].append(frame_hash)
                
                # Détecter les changements de scène
                if last_frame is not None:
                    diff = np.mean(np.abs(frame - last_frame))
                    if diff > 50:  # Seuil arbitraire pour les changements de scène
                        self.info["scene_changes"].append(t)
                last_frame = frame
                
            except Exception as e:
                ui.show_warning(f"Erreur lors de l'extraction de la frame à {t}s : {e}")

    def _analyze_audio_content(self) -> None:
        """Analyse le contenu audio de la vidéo."""
        try:
            audio_sig = get_audio_signature(self.file_path)
            if isinstance(audio_sig, np.ndarray):
                self.info["audio_signature"] = audio_sig.tolist()
                
                # Analyser les caractéristiques audio
                y, sr = librosa.load(self.file_path, duration=30.0)
                self.info["audio_features"] = {
                    "tempo": float(librosa.beat.tempo(y=y, sr=sr)[0]),
                    "rms_energy": float(np.mean(librosa.feature.rms(y=y))),
                    "zero_crossing_rate": float(np.mean(librosa.feature.zero_crossing_rate(y=y)))
                }
        except Exception as e:
            ui.show_warning(f"Erreur lors de l'extraction audio : {e}")
            self.info["audio_signature"] = None
            self.info["audio_features"] = {}

    def _handle_analysis_error(self, error: Exception, try_repair: bool) -> None:
        """Gère les erreurs d'analyse."""
        self.is_corrupted = True
        self.error = str(error)
        ui.show_error(f"Erreur lors de l'analyse de {os.path.basename(self.file_path)} : {error}")
        
        if try_repair:
            self._try_repair()

    def _try_repair(self) -> bool:
        """
        Tente de réparer la vidéo si elle est corrompue.
        
        Returns:
            True si la réparation a réussi, False sinon
        """
        ui.show_warning(f"Tentative de réparation de : {os.path.basename(self.file_path)}")
        ui.show_info(f"Erreur originale : {self.error}")
        
        success, result = repair_video(self.file_path)
        
        if success and result:
            self.is_repaired = True
            self.repair_path = result
            ui.show_success("Réparation réussie !")
            
            # Analyser le fichier réparé
            original_path = self.file_path
            self.file_path = result
            success = self.analyze(try_repair=False)
            self.file_path = original_path
            
            if success:
                self.info["repaired"] = True
                self.info["repaired_path"] = result
                return True
        else:
            ui.show_error("La réparation a échoué")
        
        return False
    
    def get_display_info(self) -> Dict[str, Any]:
        """
        Retourne les informations formatées pour l'affichage.
        
        Returns:
            Dictionnaire des informations formatées
        """
        if not self.info:
            return {
                'name': os.path.basename(self.file_path),
                'error': self.error or "Pas d'informations disponibles"
            }
        
        return {
            'name': os.path.basename(self.file_path),
            'size': self.info['file_size'],
            'duration': round(self.info['duration'], 2),
            'resolution': f"{self.info['resolution'][0]}x{self.info['resolution'][1]}",
            'fps': round(self.info['fps'], 2),
            'codec': self.info.get('codec_info', {}).get('codec_name', 'N/A'),
            'bitrate': self.info.get('codec_info', {}).get('bit_rate', 'N/A'),
            'has_audio': self.info.get('has_audio', False),
            'creation_time': datetime.fromtimestamp(self.info['creation_time']).strftime('%Y-%m-%d %H:%M:%S'),
            'is_repaired': self.is_repaired,
            'repair_path': self.repair_path if self.is_repaired else None
        }

def compare_videos(video1: VideoInfo, video2: VideoInfo, threshold: float = 0.85) -> Tuple[bool, DuplicateReason]:
    """
    Compare deux vidéos et retourne si elles sont similaires avec les raisons détaillées.
    
    Args:
        video1: Première vidéo à comparer
        video2: Deuxième vidéo à comparer
        threshold: Seuil de similarité (entre 0 et 1)
        
    Returns:
        Tuple contenant un booléen (True si similaires) et les raisons de similarité
    """
    reason = DuplicateReason()
    
    # Vérification des informations
    if not video1.info or not video2.info:
        return False, reason
    
    # Vérification rapide de la taille
    size_ratio = abs(video1.info["file_size"] - video2.info["file_size"]) / max(video1.info["file_size"], video2.info["file_size"])
    if size_ratio < 0.01:
        reason.add_reason("Taille identique", 1.0, "Les fichiers ont exactement la même taille")
        return True, reason
    
    # Comparaison de durée (20% du score)
    duration_diff = abs(video1.info["duration"] - video2.info["duration"])
    duration_score = max(0, 1 - (duration_diff / max(video1.info["duration"], video2.info["duration"])))
    reason.add_reason("Durée", duration_score, f"Différence de {duration_diff:.1f} secondes")
    
    # Comparaison des frames (40% du score)
    if not video1.info.get("hashes") or not video2.info.get("hashes"):
        reason.add_reason("Contenu visuel", 0.0, "Impossible de comparer les frames")
        frame_score = 0.0
    else:
        hash_similarities = []
        for h1, h2 in zip(video1.info["hashes"], video2.info["hashes"]):
            try:
                hash1 = imagehash.hex_to_hash(h1) if isinstance(h1, str) else h1
                hash2 = imagehash.hex_to_hash(h2) if isinstance(h2, str) else h2
                similarity = 1 - hamming(hash1.hash.flatten(), hash2.hash.flatten())
                hash_similarities.append(similarity)
            except Exception as e:
                ui.show_warning(f"Erreur lors de la comparaison des hashes : {e}")
        
        frame_score = sum(hash_similarities) / len(hash_similarities) if hash_similarities else 0.0
        reason.add_reason("Contenu visuel", frame_score, f"Similarité des images : {frame_score:.1%}")
    
    # Comparaison audio (40% du score)
    if not video1.info.get("audio_signature") or not video2.info.get("audio_signature"):
        reason.add_reason("Audio", 0.0, "Pas de piste audio dans au moins une des vidéos")
        audio_sim = 0.0
    else:
        try:
            audio_sim = np.dot(video1.info["audio_signature"], video2.info["audio_signature"]) / (
                np.linalg.norm(video1.info["audio_signature"]) * np.linalg.norm(video2.info["audio_signature"])
            )
            reason.add_reason("Audio", audio_sim, f"Similarité audio : {audio_sim:.1%}")
        except Exception as e:
            ui.show_warning(f"Erreur lors de la comparaison audio : {e}")
            audio_sim = 0.0
            reason.add_reason("Audio", 0.0, f"Erreur de comparaison : {e}")
    
    # Calcul du score final pondéré
    final_score = (
        0.2 * duration_score +  # Durée : 20%
        0.4 * frame_score +     # Contenu visuel : 40%
        0.4 * audio_sim         # Audio : 40%
    )
    
    reason.total_score = final_score
    return final_score >= threshold, reason

def find_duplicates_in_folder(directory: str, threshold: float = 0.85, timecode: float = 60.0,
                            reset_analysis: bool = False, try_repair: bool = False):
    """Recherche et gère les doublons de vidéos avec une interface utilisateur améliorée."""
    
    ignored_duplicates = load_ignored_duplicates()
    metadata_cache = {} if reset_analysis else load_metadata_cache()
    
    stats = {
        'total': 0,
        'analyzed': 0,
        'corrupted': 0,
        'repaired': 0,
        'failed': 0,
        'space_saved': 0,
        'errors': []
    }
    
    ui.show_header("Recherche de doublons vidéo", f"Dossier : {directory}")
    
    # Récupérer la liste des fichiers vidéo
    video_files = []
    with ui.show_progress(total=100) as (progress, task):
        for root, _, files in os.walk(directory):
            for file in files:
                if any(file.lower().endswith(ext) for ext in get_video_formats()):
                    video_files.append(os.path.join(root, file))
            progress.update(task, advance=5)  # Mise à jour progressive
    
    if not video_files:
        ui.show_warning(f"Aucun fichier vidéo trouvé dans {directory}")
        return
    
    stats['total'] = len(video_files)
    ui.show_info(f"Fichiers vidéo trouvés : {len(video_files)}")
    
    # Analyser les fichiers
    videos = {}
    with ui.show_progress(total=len(video_files)) as (progress, task):
        with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
            futures = []
            for file_path in video_files:
                video = VideoInfo(file_path)
                futures.append(executor.submit(video.analyze, metadata_cache, try_repair))
                videos[file_path] = video
            
            for future in futures:
                try:
                    success = future.result()
                    if success:
                        stats['analyzed'] += 1
                    else:
                        stats['corrupted'] += 1
                except Exception as e:
                    stats['errors'].append(str(e))
                    stats['failed'] += 1
                progress.update(task, advance=1)
    
    # Sauvegarder le cache des métadonnées
    save_metadata_cache({path: video.info for path, video in videos.items() if not video.is_corrupted})
    
    if not any(not v.is_corrupted for v in videos.values()):
        ui.show_error("Aucun fichier n'a pu être analysé correctement")
        return
    
    # Chercher les doublons
    duplicates = []
    with ui.show_progress(total=len(videos)) as (progress, task):
        video_items = list(videos.items())
        for i, (path1, video1) in enumerate(video_items):
            if video1.is_corrupted:
                continue
            for path2, video2 in video_items[i + 1:]:
                if video2.is_corrupted:
                    continue
                if (path1, path2) not in ignored_duplicates:
                    is_duplicate, reason = compare_videos(video1, video2, threshold)
                    if is_duplicate:
                        duplicates.append((path1, path2, reason))
            progress.update(task, advance=1)
    
    if duplicates:
        ui.show_info(f"\nDoublons trouvés : {len(duplicates)} paires")
        total_space = 0
        
        for file1, file2, reason in duplicates:
            video1 = videos[file1]
            video2 = videos[file2]
            
            # Afficher la comparaison détaillée
            ui.show_file_comparison(
                video1.get_display_info(),
                video2.get_display_info()
            )
            
            # Afficher les raisons de similarité
            ui.show_info("\nRaisons de similarité :")
            ui.show_info(reason.get_summary())
            
            # Suggérer automatiquement le fichier à supprimer
            size1, size2 = video1.info['file_size'], video2.info['file_size']
            bigger_file = file1 if size1 > size2 else file2
            smaller_file = file2 if size1 > size2 else file1
            size_diff = abs(size1 - size2)
            
            ui.show_info(f"\nSuggestion : Supprimer {os.path.basename(bigger_file)}")
            ui.show_info(f"Raison : Plus lourd de {ui.format_size(size_diff)}")
            
            if ui.confirm_action("Voulez-vous voir les images de ces fichiers ?"):
                show_images((file1, file2), timecode)
            
            action = ui.prompt_input(
                "Action (s: supprimer le plus lourd, k: garder les deux, i: ignorer, q: quitter) : ",
                default="s"
            ).lower()
            
            if action == 'q':
                break
            elif action == 'i':
                ignored_duplicates.append((file1, file2))
                save_ignored_duplicates(ignored_duplicates)
                ui.show_info("Paire ignorée et sauvegardée")
            elif action == 's':
                try:
                    send2trash(bigger_file)
                    total_space += os.path.getsize(bigger_file)
                    ui.show_success(f"Fichier déplacé vers la corbeille : {os.path.basename(bigger_file)}")
                    ui.show_info(f"Fichier conservé : {os.path.basename(smaller_file)}")
                except Exception as e:
                    ui.show_error(f"Erreur lors de la suppression : {str(e)}")
        
        if total_space > 0:
            ui.show_success(f"Espace total libéré : {ui.format_size(total_space)}")
    else:
        ui.show_info("Aucun doublon trouvé !")

def show_images(duplicates: Tuple[str, str], timecode: float):
    """Affiche des images des vidéos pour comparaison visuelle."""
    for path in duplicates:
        ui.show_info(f"Affichage d'une image pour : {os.path.basename(path)} au temps {timecode}s")
        try:
            display_image_from_video(path, timecode)
        except Exception as e:
            ui.show_error(f"Erreur lors de l'affichage de l'image pour {os.path.basename(path)}: {str(e)}")
