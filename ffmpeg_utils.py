import os
import subprocess
from send2trash import send2trash
from pathlib import Path
from ffmpeg_progress_yield import FfmpegProgress
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
from moviepy.editor import VideoFileClip
from PIL import Image
import imagehash
import logging
from typing import Dict, List, Tuple, Optional, Any
from video_utils import get_audio_signature
from ui_manager import ui

# Configuration du logging
logger = logging.getLogger(__name__)

console = Console()

def get_video_metadata(file_path: str) -> Dict[str, Any]:
    """
    Retourne les métadonnées de la vidéo.
    
    Args:
        file_path: Chemin vers le fichier vidéo
        
    Returns:
        Dict contenant les métadonnées
        
    Raises:
        FileNotFoundError: Si le fichier n'existe pas
        RuntimeError: Si ffmpeg n'est pas installé
        ValueError: Si la vidéo est invalide
    """
    check_ffmpeg_installed()
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"Le fichier n'existe pas : {file_path}")
    
    metadata: Dict[str, Any] = {
        "file_size": file_path.stat().st_size / (1024 * 1024),  # Taille en Mo
        "title": None,
        "duration": None,
        "resolution": None,
        "fps": None,
        "frame_hashes": [],
        "audio_signature": None
    }
    
    try:
        # Extraction du titre avec ffprobe
        result = subprocess.run([
            "ffprobe", "-v", "quiet", "-show_entries", "format_tags=title",
            "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)
        ], capture_output=True, text=True, check=True)
        metadata["title"] = result.stdout.strip() or None
        
    except subprocess.CalledProcessError as e:
        logger.warning(f"Impossible d'extraire le titre : {e}")
    
    try:
        with VideoFileClip(str(file_path)) as video:
            if video.duration <= 0:
                raise ValueError("Durée de vidéo invalide")
            
            metadata.update({
                "duration": video.duration,
                "resolution": (video.w, video.h),
                "fps": video.fps
            })
            
            # Extraire des frames à intervalles réguliers
            frame_times = [t for t in range(60, int(video.duration), 60)]
            if frame_times:  # S'assurer qu'on a au moins une frame
                frame_times.insert(0, 0)  # Ajouter le début
                frame_times.append(int(video.duration))  # Ajouter la fin
                
                for t in frame_times:
                    try:
                        frame = video.get_frame(t)
                        frame_hash = imagehash.average_hash(Image.fromarray(frame))
                        metadata["frame_hashes"].append(str(frame_hash))
                    except Exception as e:
                        logger.warning(f"Erreur lors de l'extraction de la frame à {t}s : {e}")
            
            # Générer la signature audio si présente
            if video.audio:
                try:
                    metadata["audio_signature"] = get_audio_signature(str(file_path))
                except Exception as e:
                    logger.warning(f"Erreur lors de l'extraction de la signature audio : {e}")
            
            return metadata
            
    except Exception as e:
        raise ValueError(f"Erreur lors de l'analyse de la vidéo : {e}")

def check_ffmpeg_installed() -> None:
    """
    Vérifie si ffmpeg est installé.
    
    Raises:
        RuntimeError: Si ffmpeg n'est pas installé
    """
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise RuntimeError("FFmpeg n'est pas installé ou n'est pas accessible") from e

def run_ffmpeg_with_progress(
    command: List[str],
    description: str,
    duration_override: Optional[float] = None,
    delete_source: bool = False
) -> bool:
    """
    Exécute une commande ffmpeg avec affichage de progression.
    
    Args:
        command: La commande FFmpeg à exécuter
        description: Description de l'opération
        duration_override: Durée totale si connue
        delete_source: Supprimer le fichier source après succès
        
    Returns:
        True si l'opération a réussi, False sinon
    """
    logger.debug(f"Exécution de la commande : {' '.join(command)}")
    
    try:
        ff = FfmpegProgress(command)
        with ui.show_progress() as progress:
            task = progress.add_task(description, total=100)
            
            for progress_data in ff.run_command_with_progress():
                percent = progress_data.get('progress', 0)
                time = progress_data.get('time', 0)
                
                if duration_override:
                    percent = min(100, (time / duration_override) * 100)
                
                progress.update(task, completed=percent)
            
            # Vérifier le code de retour
            if ff.process.returncode != 0:
                raise subprocess.CalledProcessError(
                    ff.process.returncode,
                    command,
                    ff.process.stdout,
                    ff.process.stderr
                )
            
            if delete_source:
                source_file = Path(command[command.index('-i') + 1])
                if source_file.exists():
                    send2trash(str(source_file))
                    logger.info(f"Fichier source déplacé vers la corbeille : {source_file}")
            
            return True
            
    except Exception as e:
        logger.error(f"Erreur lors de l'exécution de FFmpeg : {e}")
        ui.show_error(f"Erreur lors de l'exécution de FFmpeg : {e}")
        return False

def convert_file_action(
    file_path: str,
    output_format: str,
    delete_larger_original: bool = False,
    bitrate: str = "800k",
    crf: int = 23,
    resolution: Optional[str] = None,
    max_attempts: int = 3
) -> Tuple[bool, Optional[str]]:
    """
    Tente de convertir un fichier vidéo avec ajustements progressifs de la qualité si nécessaire.
    
    Args:
        file_path: Chemin du fichier à convertir
        output_format: Format de sortie (.mp4, .mkv, etc.)
        delete_larger_original: Supprimer l'original si plus grand
        bitrate: Débit binaire cible
        crf: Facteur de qualité constante (0-51, plus bas = meilleure qualité)
        resolution: Résolution cible (ex: "1920x1080")
        max_attempts: Nombre maximum de tentatives
        
    Returns:
        Tuple (succès, chemin du fichier de sortie ou None)
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Le fichier n'existe pas : {file_path}")
    
    # Déterminer le fichier de sortie
    output_path = file_path.with_suffix(output_format)
    if output_path.exists():
        counter = 1
        while output_path.exists():
            output_path = file_path.with_stem(f"{file_path.stem}_{counter}").with_suffix(output_format)
            counter += 1
    
    original_size = file_path.stat().st_size
    logger.info(f"Conversion de {file_path} vers {output_path}")
    
    for attempt in range(max_attempts):
        # Construire la commande ffmpeg
        command = ["ffmpeg", "-i", str(file_path)]
        
        # Ajouter les options de conversion
        if resolution:
            command.extend(["-vf", f"scale={resolution}"])
        
        # Ajuster la qualité selon la tentative
        adjusted_crf = min(51, crf + (attempt * 3))
        command.extend([
            "-c:v", "libx264",
            "-crf", str(adjusted_crf),
            "-preset", "medium",
            "-b:v", bitrate,
            "-c:a", "aac",
            "-b:a", "128k",
            "-y",
            str(output_path)
        ])
        
        # Exécuter la conversion
        success = run_ffmpeg_with_progress(
            command,
            f"Tentative {attempt + 1}/{max_attempts} - CRF {adjusted_crf}"
        )
        
        if success and output_path.exists():
            new_size = output_path.stat().st_size
            
            # Vérifier si le fichier est plus petit
            if new_size < original_size:
                if delete_larger_original:
                    send2trash(str(file_path))
                    logger.info(f"Original plus grand supprimé : {file_path}")
                return True, str(output_path)
            
            # Si le fichier est plus grand, supprimer et réessayer
            output_path.unlink()
            logger.warning(f"Fichier converti plus grand ({new_size} > {original_size}), nouvelle tentative")
        
        if not success:
            break
    
    logger.error("Échec de la conversion après plusieurs tentatives")
    return False, None

def process_files_in_folder(
    directory: str,
    formats: List[str],
    min_size_mb: float,
    delete_larger_original: bool = False,
    keyword: str = "cvt",
    force: bool = False
) -> Tuple[int, int]:
    """
    Traite les fichiers vidéo d'un dossier pour conversion.
    
    Args:
        directory: Dossier à traiter
        formats: Formats vidéo à traiter
        min_size_mb: Taille minimale en Mo pour traiter un fichier
        delete_larger_original: Supprimer l'original si plus grand
        keyword: Mot-clé pour les fichiers .nocvt
        force: Forcer la conversion même si .nocvt existe
        
    Returns:
        Tuple (nombre de fichiers traités, nombre de succès)
    """
    directory = Path(directory)
    if not directory.exists():
        raise FileNotFoundError(f"Le dossier n'existe pas : {directory}")
    
    processed = 0
    success = 0
    
    # Parcourir les fichiers vidéo
    for ext in formats:
        for file_path in directory.rglob(f"*{ext}"):
            # Vérifier les conditions de traitement
            if not force:
                nocvt_file = file_path.with_suffix(".nocvt")
                if nocvt_file.exists():
                    logger.info(f"Fichier ignoré (nocvt) : {file_path}")
                    continue
            
            # Vérifier la taille
            size_mb = file_path.stat().st_size / (1024 * 1024)
            if size_mb < min_size_mb:
                logger.info(f"Fichier ignoré (trop petit) : {file_path}")
                continue
            
            processed += 1
            
            try:
                # Convertir le fichier
                result, output_path = convert_file_action(
                    str(file_path),
                    ".mp4",
                    delete_larger_original=delete_larger_original
                )
                
                if result:
                    success += 1
                    logger.info(f"Conversion réussie : {output_path}")
                else:
                    logger.error(f"Échec de la conversion : {file_path}")
                    
            except Exception as e:
                logger.error(f"Erreur lors du traitement de {file_path} : {e}")
    
    return processed, success

def repair_video(file_path: str) -> Tuple[bool, Optional[str]]:
    """
    Tente de réparer un fichier vidéo corrompu en utilisant FFmpeg.
    
    Args:
        file_path: Chemin du fichier à réparer
        
    Returns:
        Tuple (succès de la réparation, chemin du fichier réparé ou None)
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Le fichier n'existe pas : {file_path}")
    
    # Créer le nom du fichier réparé
    repaired_path = file_path.with_stem(f"{file_path.stem}_repaired")
    if repaired_path.exists():
        counter = 1
        while repaired_path.exists():
            repaired_path = file_path.with_stem(f"{file_path.stem}_repaired_{counter}")
            counter += 1
    
    logger.info(f"Tentative de réparation de {file_path}")
    
    try:
        # Première tentative : copie directe avec FFmpeg
        command = [
            "ffmpeg",
            "-err_detect", "ignore_err",
            "-i", str(file_path),
            "-c", "copy",
            "-y",
            str(repaired_path)
        ]
        
        if run_ffmpeg_with_progress(command, "Tentative de réparation (copie)"):
            logger.info(f"Réparation réussie (copie) : {repaired_path}")
            return True, str(repaired_path)
        
        # Deuxième tentative : réencodage complet
        command = [
            "ffmpeg",
            "-err_detect", "ignore_err",
            "-i", str(file_path),
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-y",
            str(repaired_path)
        ]
        
        if run_ffmpeg_with_progress(command, "Tentative de réparation (réencodage)"):
            logger.info(f"Réparation réussie (réencodage) : {repaired_path}")
            return True, str(repaired_path)
        
        # Si les deux tentatives échouent
        if repaired_path.exists():
            repaired_path.unlink()
        logger.error(f"Échec de la réparation : {file_path}")
        return False, None
        
    except Exception as e:
        logger.error(f"Erreur lors de la réparation : {e}")
        if repaired_path.exists():
            repaired_path.unlink()
        return False, None
