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
from video_utils import *
import shutil

console = Console()

def get_video_metadata(file_path: str) -> dict:
    """
    Retourne les métadonnées de la vidéo : titre, durée, résolution, fps, taille, hash de frames et signature audio.
    Capture la première image après une minute, puis toutes les 60 secondes.
    """
    check_ffmpeg_installed()

    # Obtenir les métadonnées de base avec ffprobe (y compris le titre)
    try:
        # Extraction du titre avec ffprobe
        title = subprocess.check_output([
            "ffprobe", "-v", "quiet", "-show_entries", "format_tags=title",
            "-of", "default=noprint_wrappers=1:nokey=1", file_path
        ]).decode().strip()
    except subprocess.CalledProcessError:
        title = None

    # Extraction des métadonnées techniques avec moviepy
    try:
        with VideoFileClip(file_path) as video:
            duration = video.duration
            resolution = (video.w, video.h)
            fps = video.fps
            file_size = os.path.getsize(file_path) / (1024 * 1024)  # Taille en Mo

            # Obtenir les hash de frames (1min, +60s incréments)
            frame_hashes = []
            for t in range(60, int(duration), 60):  # commence à 1 minute, puis incrémente de 60s
                if t < duration:
                    frame = video.get_frame(t)
                    frame_hash = imagehash.average_hash(Image.fromarray(frame))
                    frame_hashes.append(str(frame_hash))

            # Générer la signature audio
            audio_signature = get_audio_signature(file_path) if video.audio else None

        return {
            "title": title,
            "duration": duration,
            "resolution": resolution,
            "fps": fps,
            "frame_hashes": frame_hashes,
            "audio_signature": audio_signature,
            "file_size": file_size
        }
    except Exception as e:
        console.print(f"[bold red]Erreur lors de l'analyse de {file_path} : {e}[/bold red]")
        return None

def check_ffmpeg_installed() -> None:
    """Vérifie si ffmpeg est installé."""
    if shutil.which("ffmpeg") is None:
        console.print(":x: [bold red]Erreur :[/bold red] `ffmpeg` n'est pas installé ou n'est pas accessible.")
        raise FileNotFoundError("ffmpeg not found")

def run_ffmpeg_with_progress(command: list, description: str, duration_override: float = None, delete_source: bool = False) -> None:
    """Exécute une commande ffmpeg avec affichage de progression."""
    console.print(f"{description}...")
    command_with_progress = [command[0], "-progress", "-", "-nostats"] + command[1:]

    try:
        ff = FfmpegProgress(command_with_progress)
        with Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(description, total=100)
            for current_progress in ff.run_command_with_progress(duration_override=duration_override):
                progress.update(task, completed=current_progress)
    except Exception as e:
        console.print(f"[bold red]Erreur lors de l'exécution de la commande ffmpeg : {e}[/bold red]")

    # Supprime le fichier source si demandé
    if delete_source:
        try:
            os.remove(command[2])  # command[2] est le fichier source dans ce cas
            console.print(f"[bold red]Fichier source supprimé : {command[2]}[/bold red]")
        except Exception as e:
            console.print(f"[bold red]Erreur lors de la suppression de {command[2]} : {e}[/bold red]")

def convert_file_action(file_path: str, output_format: str, delete_larger_original: bool = False, bitrate: str = "800k", crf: int = 23, resolution: str = None, max_attempts: int = 3) -> bool:
    """Attempts to convert a video file with progressive encoding quality adjustments if necessary."""
    output_file = Path(file_path).with_suffix(f".cvt.{output_format}")
    attempt = 1
    success = False
    
    while attempt <= max_attempts:
        console.print(f"Conversion de {file_path.name} (Tentative {attempt}/{max_attempts})...")
        
        # Build ffmpeg command with encoding settings
        command = ["ffmpeg", "-i", str(file_path), "-y"]
        command += ["-b:v", bitrate] if bitrate else []
        command += ["-crf", str(crf)]
        if resolution:
            command += ["-vf", f"scale={resolution}"]
        command.append(str(output_file))
        
        # Track conversion progress
        with Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(f"Conversion de {file_path.name}", total=100)
            try:
                ff = FfmpegProgress(command)
                for percentage in ff.run_command_with_progress():
                    progress.update(task, completed=percentage)
                
                console.print(f":white_check_mark: Conversion terminée pour [bold green]{output_file}[/bold green]")
                
                # Size comparison
                original_size = file_path.stat().st_size
                converted_size = output_file.stat().st_size
                if converted_size < original_size:
                    success = True
                    if delete_larger_original:
                        send2trash(file_path)
                        console.print(f"[bold red]Fichier original supprimé car plus grand : {file_path}[/bold red]")
                    break  # Stop further attempts if successful
                else:
                    # Adjust settings for next attempt
                    crf += 2  # Increase CRF for more compression
                    bitrate = str(int(int(bitrate[:-1]) * 0.8)) + "k"  # Reduce bitrate by 20%
                    attempt += 1
                    output_file.unlink()  # Delete larger converted file

            except Exception as e:
                console.print(f"[bold red]Erreur lors de la conversion : {e}[/bold red]")
                break

    # Mark as .nocvt if unsuccessful
    if not success:
        console.print(f"[bold yellow]Conversion échouée après {max_attempts} tentatives. Renommage du fichier original avec '.nocvt'.[/bold yellow]")
        file_path.rename(file_path.with_suffix(".nocvt" + file_path.suffix))
    return success

def process_files_in_folder(directory: str, formats: list, min_size_mb: float, delete_larger_original: bool = False, keyword: str = "cvt", force: bool = False):
    """Processes video files in a folder for conversion, applying size checks and renaming .nocvt files if necessary."""
    min_size_bytes = min_size_mb * 1024 * 1024
    video_files = [
        f for f in Path(directory).rglob('*')
        if f.suffix in formats and f.stat().st_size >= min_size_bytes and keyword not in f.stem and (force or not f.name.endswith(".nocvt"))
    ]
    total_files = len(video_files)

    console.print(f"[bold green]{total_files} fichiers vidéo trouvés dans {directory}, taille >= {min_size_mb} Mo sans '{keyword}'[/bold green]")
    
    for idx, file_path in enumerate(video_files, start=1):
        console.print(f"[bold yellow]Traitement du fichier {idx}/{total_files} : {file_path.name}[/bold yellow]")
        success = convert_file_action(file_path, "mp4", delete_larger_original)

        if not success:
            console.print(f"[bold red]Conversion non optimisée pour {file_path.name}. Marqué comme '.nocvt'.[/bold red]")
