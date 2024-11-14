from moviepy.editor import VideoFileClip
from PIL import Image
import imagehash
import librosa
import numpy as np
from rich.console import Console
from scipy.spatial.distance import hamming

from send2trash import send2trash
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
from prompt_toolkit import prompt
from config_manager import *
from video_utils import *

console = Console()

def similarity_score(video1: dict, video2: dict, threshold: float) -> bool:
    """Calcule un score de similarité entre deux vidéos basé sur plusieurs critères."""
    if not video1 or not video2:
        return 0

    # Comparaison de durée
    duration_similarity = 1 - abs(video1["duration"] - video2["duration"]) / max(video1["duration"], video2["duration"])

    # Comparaison de résolution
    resolution_similarity = 1 if video1["resolution"] == video2["resolution"] else 0

    # Comparaison des hash de frames avec la distance de Hamming
    hashes1 = [imagehash.hex_to_hash(h) if isinstance(h, str) else h for h in video1["hashes"]]
    hashes2 = [imagehash.hex_to_hash(h) if isinstance(h, str) else h for h in video2["hashes"]]
    
    hash_similarities = [
        1 - hamming(h1.hash.flatten(), h2.hash.flatten())
        for h1, h2 in zip(hashes1, hashes2)
    ]
    hash_similarity = sum(hash_similarities) / len(hash_similarities)

    # Comparaison de la signature audio (cosine similarity)
    if video1.get("audio_signature") is not None and video2.get("audio_signature") is not None:
        audio_similarity = np.dot(video1["audio_signature"], video2["audio_signature"]) / (
            np.linalg.norm(video1["audio_signature"]) * np.linalg.norm(video2["audio_signature"])
        )
    else:
        audio_similarity = 0

    # Calcul du score global
    overall_score = (0.4 * duration_similarity + 0.2 * resolution_similarity +
                     0.3 * hash_similarity + 0.1 * audio_similarity)
    
    return overall_score >= threshold


def get_video_infos(file_path: str) -> dict:
    """Retourne les métadonnées de la vidéo : durée, résolution, hash de frames multiples et signature audio."""
    try:
        with VideoFileClip(file_path) as video:
            duration = video.duration
            resolution = (video.w, video.h)
            fps = video.fps
            
            # Obtenir les hash de frames (début, milieu, fin)
            hashes = []
            for t in [0.1 * duration, 0.5 * duration, 0.9 * duration]:  # Prendre les frames à 10%, 50%, 90%
                frame = video.get_frame(t)
                frame_hash = imagehash.average_hash(Image.fromarray(frame))
                hashes.append(frame_hash)
            
            # Générer la signature audio
            audio_signature = get_audio_signature(file_path) if video.audio else None
            
            return {
                "duration": duration,
                "resolution": resolution,
                "fps": fps,
                "hashes": hashes,
                "audio_signature": audio_signature
            }
    except Exception as e:
        console.print(f"[bold red]Erreur lors de l'analyse de {file_path} : {e}[/bold red]")
        return None

def get_audio_signature(file_path: str) -> np.ndarray:
    """Génère une signature audio pour un fichier vidéo, retourne un vecteur de caractéristiques."""
    try:
        y, sr = librosa.load(file_path, sr=22050, mono=True, duration=30)  # Charger les 30 premières secondes
        return librosa.feature.mfcc(y=y, sr=sr).mean(axis=1)  # MFCC moyen pour signature
    except Exception as e:
        console.print(f"[bold red]Erreur lors de la génération de la signature audio pour {file_path} : {e}[/bold red]")
        return None
    



def find_duplicates_in_folder(directory: str, threshold: float, timecode: float = 60.0, reset_analysis: bool = False):
    """
    Recherche et gère les doublons de vidéos avec barre de progression, gestion des erreurs et enregistrement des métadonnées.
    
    :param directory: Chemin du dossier à analyser pour les doublons.
    :param threshold: Seuil de similarité pour considérer deux vidéos comme doublons.
    :param timecode: Timecode de départ pour les captures d'images en secondes, incrémenté de 60s par défaut.
    :param reset_analysis: Permet de réinitialiser l'analyse des doublons.
    """
    remember_directory(directory, "duplicates")
    ignored_duplicates = load_ignored_duplicates()
    metadata_cache = load_json_data().get("video_metadata", {})

    if reset_analysis:
        metadata_cache = {}
        ignored_duplicates = {}
        console.print("[bold red]Réinitialisation des données d'analyse précédentes.[/bold red]")

    video_files = [f for f in Path(directory).rglob('*') if f.is_file() and f.suffix.lower() in get_video_formats()]
    video_metadata = {}

    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Analyse des vidéos", total=len(video_files))

        for video_file in video_files:
            video_path_str = str(video_file)
            if video_path_str in metadata_cache:
                console.print(f"[bold green]Utilisation du cache pour : {video_file}[/bold green]")
                video_metadata[video_path_str] = metadata_cache[video_path_str]
            else:
                console.print(f"Traitement de : [bold cyan]{video_file}[/bold cyan]")
                metadata = get_video_infos(video_path_str)
                if metadata is not None:
                    metadata["hashes"] = [str(h) for h in metadata["hashes"]]
                    video_metadata[video_path_str] = metadata
                    metadata_cache[video_path_str] = metadata
                else:
                    console.print(f"[bold red]Impossible de lire les métadonnées pour {video_file}, fichier ignoré.[/bold red]")
            progress.update(task, advance=1)

    save_json_data({"video_metadata": metadata_cache})

    potential_duplicates = []
    visited = set()

    for video1_path, meta1 in video_metadata.items():
        if video1_path in visited or (meta1["duration"], meta1["hashes"]) in ignored_duplicates.get(directory, []):
            continue
        duplicates = [video1_path]
        for video2_path, meta2 in video_metadata.items():
            if video1_path != video2_path and video2_path not in visited:
                score = similarity_score(meta1, meta2, threshold)
                if score:
                    duplicates.append(video2_path)
                    visited.add(video2_path)
        if len(duplicates) > 1:
            potential_duplicates.append(duplicates)

    space_saved = 0
    total_duplicates = len(potential_duplicates)  # Nombre total de groupes de doublons trouvés

    for idx, duplicates in enumerate(potential_duplicates, start=1):
        console.print(f"\n[bold yellow]Doublons détectés ({idx}/{total_duplicates}) :[/bold yellow]")  # Indicateur de progression
        for i, path in enumerate(duplicates, start=1):
            metadata = video_metadata[path]
            file_size = Path(path).stat().st_size / (1024 * 1024)
            file_size_str = f"{file_size:.2f} MB" if file_size < 1024 else f"{file_size / 1024:.2f} GB"
            console.print(f"{i}. {path} - Durée: {metadata['duration']}s - Taille: {file_size_str}")

        choice = prompt(
            "Entrez le numéro du fichier à conserver (1, 2, ...), s (skip), i (ignore), q (quitter), v (voir autres images), ou y (afficher images) : "
        ).lower()

        if choice == "y":
            show_images(duplicates, timecode)
            choice = prompt(
                "Entrez le numéro du fichier à conserver (1, 2, ...), s (skip), i (ignore), q (quitter), v (voir autres images) : "
            ).lower()

        if choice.isdigit() and 1 <= int(choice) <= len(duplicates):
            to_keep = duplicates[int(choice) - 1]
            for path in duplicates:
                if path != to_keep:
                    file_size = Path(path).stat().st_size
                    send2trash(path)
                    space_saved += file_size
                    console.print(f"[bold red]Fichier déplacé dans la corbeille : {path}[/bold red]")
        
        elif choice == "s":
            console.print("[bold yellow]Aucune action prise pour ce groupe.[/bold yellow]")
        
        elif choice == "i":
            # Ajout direct de `duration` et de `hashes` dans `ignored_duplicates`
            ignored_duplicates.setdefault(directory, []).append(
                (video_metadata[duplicates[0]]["duration"], video_metadata[duplicates[0]]["hashes"])
            )
            console.print("[bold yellow]Groupe ignoré.[/bold yellow]")

        elif choice == "q":
            console.print("[bold yellow]Retour au menu principal...[/bold yellow]")
            break

        elif choice == "v":
            timecode += 60  # Augmenter le timecode de 60s pour voir d'autres images
            show_images(duplicates, timecode)

        else:
            console.print("[bold red]Choix invalide. Veuillez réessayer.[/bold red]")

    save_ignored_duplicates(ignored_duplicates)

    space_saved_mb = space_saved / (1024 * 1024)
    console.print(f"[bold green]Espace total libéré : {space_saved_mb:.2f} Mo[/bold green]")

def show_images(duplicates, timecode):
    """Affiche des images de chaque vidéo à un timestamp spécifique pour comparaison visuelle."""
    for path in duplicates:
        console.print(f"Affichage d'une image pour : [bold cyan]{path}[/bold cyan] au temps {timecode}s")
        display_image_from_video(path, timecode)

