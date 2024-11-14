from moviepy.editor import VideoFileClip
from PIL import Image
import imagehash
import librosa
import numpy as np
import os
from rich.console import Console

console = Console()

from scipy.spatial.distance import hamming
import numpy as np

def similarity_score(video1: dict, video2: dict, threshold: float) -> bool:
    """Calcule un score de similarité entre deux vidéos basé sur plusieurs critères."""
    if not video1 or not video2:
        return False

    # Comparaison de durée
    duration_similarity = 1 - abs(video1["duration"] - video2["duration"]) / max(video1["duration"], video2["duration"])

    # Comparaison de résolution
    resolution_similarity = 1 if video1["resolution"] == video2["resolution"] else 0

    # Comparaison des hash de frames avec la distance de Hamming
    hash_similarities = [
        1 - hamming(h1.hash.flatten(), h2.hash.flatten())
        for h1, h2 in zip(video1["hashes"], video2["hashes"])
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


def get_audio_signature(file_path: str) -> np.ndarray:
    """Génère une signature audio pour un fichier vidéo, retourne un vecteur de caractéristiques."""
    try:
        y, sr = librosa.load(file_path, sr=22050, mono=True, duration=30)  # Charger les 30 premières secondes
        return librosa.feature.mfcc(y=y, sr=sr).mean(axis=1)  # MFCC moyen pour signature
    except Exception as e:
        console.print(f"[bold red]Erreur lors de la génération de la signature audio pour {file_path} : {e}[/bold red]")
        return None

def get_video_duration(file_path: str) -> float:
    """Retourne la durée d'une vidéo en secondes."""
    try:
        with VideoFileClip(file_path) as video:
            return video.duration
    except Exception as e:
        console.print(f"[bold red]Erreur lors de l'obtention de la durée pour {file_path} : {e}[/bold red]")
        return 0

def get_video_hash(file_path: str, timecode: float = 10.0) -> str:
    """Génère un hash d'image pour une frame de la vidéo au timecode donné."""
    try:
        with VideoFileClip(file_path) as video:
            frame = video.get_frame(timecode)
            image = Image.fromarray(frame)
            return str(imagehash.average_hash(image))
    except Exception as e:
        console.print(f"[bold red]Erreur lors de la génération du hash pour {file_path} : {e}[/bold red]")
        return ""

def display_image_from_video(file_path: str, timecode: float = 10.0) -> None:
    """Affiche une image de la vidéo à un timecode donné."""
    try:
        with VideoFileClip(file_path) as video:
            frame = video.get_frame(timecode)
            image = Image.fromarray(frame)
            image.show()
    except Exception as e:
        console.print(f"[bold red]Erreur lors de l'affichage de l'image pour {file_path} : {e}[/bold red]")
