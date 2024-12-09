from moviepy.editor import VideoFileClip
from PIL import Image
import imagehash
import librosa
import numpy as np
import os
from rich.console import Console
from scipy.spatial.distance import hamming
from typing import Optional, Tuple, List, Dict
import tempfile
from ui_manager import ui

console = Console()

def get_video_info(file_path: str) -> Optional[Dict]:
    """
    Récupère les informations détaillées d'une vidéo.
    
    Args:
        file_path (str): Chemin du fichier vidéo
        
    Returns:
        Optional[Dict]: Dictionnaire contenant les informations de la vidéo ou None en cas d'erreur
    """
    try:
        with VideoFileClip(file_path) as video:
            info = {
                'duration': video.duration,
                'resolution': (video.w, video.h),
                'fps': video.fps,
                'size': os.path.getsize(file_path),
                'has_audio': video.audio is not None,
                'frame_count': int(video.duration * video.fps),
                'bitrate': os.path.getsize(file_path) * 8 / video.duration if video.duration > 0 else 0,
                'aspect_ratio': video.w / video.h if video.h > 0 else 0
            }
            
            # Extraire les informations du codec
            try:
                codec_info = video.reader.infos
                info.update({
                    'video_codec': codec_info.get('codec_name'),
                    'audio_codec': codec_info.get('audio_codec_name'),
                    'video_bitrate': codec_info.get('video_bitrate'),
                    'audio_bitrate': codec_info.get('audio_bitrate'),
                    'pixel_format': codec_info.get('pix_fmt')
                })
            except:
                pass
            
            # Analyser la qualité vidéo
            if video.duration > 0:
                info['quality_metrics'] = analyze_video_quality(video)
            
            return info
    except Exception as e:
        ui.show_error(f"Erreur lors de l'analyse de {os.path.basename(file_path)}: {str(e)}")
        return None

def analyze_video_quality(video: VideoFileClip) -> Dict:
    """
    Analyse la qualité d'une vidéo.
    
    Args:
        video: Instance de VideoFileClip
        
    Returns:
        Dict: Métriques de qualité
    """
    metrics = {
        'sharpness': 0.0,
        'noise_level': 0.0,
        'brightness': 0.0,
        'contrast': 0.0,
        'saturation': 0.0
    }
    
    try:
        # Échantillonner quelques frames pour l'analyse
        sample_times = [
            video.duration * p for p in [0.1, 0.3, 0.5, 0.7, 0.9]
        ]
        
        for t in sample_times:
            frame = video.get_frame(t)
            
            # Convertir en niveaux de gris pour certaines métriques
            gray = np.mean(frame, axis=2)
            
            # Mesurer la netteté (variation locale)
            dx = np.diff(gray, axis=1)
            dy = np.diff(gray, axis=0)
            metrics['sharpness'] += np.mean(np.sqrt(dx[:-1]**2 + dy[:,:-1]**2))
            
            # Mesurer le niveau de bruit
            noise = np.std(gray - np.mean(gray))
            metrics['noise_level'] += noise
            
            # Mesurer la luminosité et le contraste
            metrics['brightness'] += np.mean(gray)
            metrics['contrast'] += np.std(gray)
            
            # Mesurer la saturation
            saturation = np.mean(np.std(frame, axis=2))
            metrics['saturation'] += saturation
        
        # Moyenner les métriques
        for key in metrics:
            metrics[key] /= len(sample_times)
        
        # Normaliser les valeurs entre 0 et 1
        max_values = {
            'sharpness': 100,
            'noise_level': 50,
            'brightness': 255,
            'contrast': 128,
            'saturation': 255
        }
        
        for key, max_val in max_values.items():
            metrics[key] = min(1.0, metrics[key] / max_val)
        
        return metrics
    except Exception as e:
        ui.show_warning(f"Erreur lors de l'analyse de qualité: {e}")
        return metrics

def get_video_segments(file_path: str, min_segment_duration: float = 1.0) -> List[Dict]:
    """
    Détecte les segments vidéo basés sur les changements de scène.
    
    Args:
        file_path: Chemin du fichier vidéo
        min_segment_duration: Durée minimale d'un segment en secondes
        
    Returns:
        List[Dict]: Liste des segments détectés avec leurs caractéristiques
    """
    segments = []
    try:
        with VideoFileClip(file_path) as video:
            duration = video.duration
            current_time = 0.0
            last_frame = None
            
            while current_time < duration:
                frame = video.get_frame(current_time)
                
                if last_frame is not None:
                    # Calculer la différence entre les frames
                    diff = np.mean(np.abs(frame - last_frame))
                    
                    # Si différence significative, nouveau segment
                    if diff > 50 and current_time - segments[-1]['end_time'] >= min_segment_duration:
                        segments[-1]['end_time'] = current_time
                        segments.append({
                            'start_time': current_time,
                            'end_time': duration,
                            'duration': None,
                            'avg_brightness': np.mean(frame),
                            'motion_level': diff
                        })
                else:
                    # Premier segment
                    segments.append({
                        'start_time': 0.0,
                        'end_time': duration,
                        'duration': None,
                        'avg_brightness': np.mean(frame),
                        'motion_level': 0.0
                    })
                
                last_frame = frame
                current_time += 1.0  # Analyser chaque seconde
            
            # Calculer les durées finales
            for segment in segments:
                segment['duration'] = segment['end_time'] - segment['start_time']
            
            return segments
            
    except Exception as e:
        ui.show_error(f"Erreur lors de la détection des segments: {e}")
        return []

def extract_frames(file_path: str, timestamps: List[float] = None, num_frames: int = 5) -> List[Image.Image]:
    """
    Extrait des frames d'une vidéo à des timestamps spécifiques ou uniformément répartis.
    
    Args:
        file_path (str): Chemin du fichier vidéo
        timestamps (List[float], optional): Liste des timestamps en secondes
        num_frames (int, optional): Nombre de frames à extraire si timestamps n'est pas fourni
        
    Returns:
        List[Image.Image]: Liste des frames extraites
    """
    try:
        with VideoFileClip(file_path) as video:
            if timestamps is None:
                # Répartir uniformément les frames sur la durée de la vidéo
                timestamps = [i * video.duration / (num_frames - 1) for i in range(num_frames)]
            
            frames = []
            for t in timestamps:
                if 0 <= t <= video.duration:
                    frame = video.get_frame(t)
                    frames.append(Image.fromarray(frame))
            
            return frames
    except Exception as e:
        ui.show_error(f"Erreur lors de l'extraction des frames de {os.path.basename(file_path)}: {str(e)}")
        return []

def get_video_hash(file_path: str, timecode: float = 10.0) -> str:
    """
    Génère un hash d'image pour une frame de la vidéo au timecode donné.
    
    Args:
        file_path (str): Chemin du fichier vidéo
        timecode (float): Timestamp pour l'extraction de la frame
        
    Returns:
        str: Hash de la frame ou chaîne vide en cas d'erreur
    """
    try:
        with VideoFileClip(file_path) as video:
            # Vérifier que le timecode est valide
            if timecode < 0 or timecode > video.duration:
                timecode = min(10.0, video.duration / 2)
            
            frame = video.get_frame(timecode)
            image = Image.fromarray(frame)
            return str(imagehash.average_hash(image))
    except Exception as e:
        ui.show_error(f"Erreur lors de la génération du hash pour {os.path.basename(file_path)}: {str(e)}")
        return ""

def get_audio_signature(file_path: str, duration: float = 30.0) -> Optional[np.ndarray]:
    """
    Génère une signature audio pour un fichier vidéo.
    
    Args:
        file_path (str): Chemin du fichier vidéo
        duration (float): Durée en secondes de l'audio à analyser
        
    Returns:
        Optional[np.ndarray]: Vecteur de caractéristiques audio ou None en cas d'erreur
    """
    try:
        y, sr = librosa.load(file_path, sr=22050, mono=True, duration=duration)
        mfcc = librosa.feature.mfcc(y=y, sr=sr)
        chroma = librosa.feature.chroma_stft(y=y, sr=sr)
        
        # Combiner plusieurs caractéristiques audio
        features = np.concatenate([
            mfcc.mean(axis=1),
            chroma.mean(axis=1),
            librosa.feature.spectral_centroid(y=y, sr=sr).mean(axis=1),
            librosa.feature.spectral_rolloff(y=y, sr=sr).mean(axis=1)
        ])
        
        # Normaliser les caractéristiques
        return features / np.linalg.norm(features)
    except Exception as e:
        ui.show_error(f"Erreur lors de la génération de la signature audio pour {os.path.basename(file_path)}: {str(e)}")
        return None

def display_image_from_video(file_path: str, timecode: float = 10.0) -> None:
    """
    Affiche une image de la vidéo à un timecode donné.
    
    Args:
        file_path (str): Chemin du fichier vidéo
        timecode (float): Timestamp pour l'extraction de la frame
    """
    try:
        with VideoFileClip(file_path) as video:
            # Vérifier que le timecode est valide
            if timecode < 0 or timecode > video.duration:
                timecode = min(10.0, video.duration / 2)
                ui.show_warning(f"Timecode ajusté à {timecode:.1f}s")
            
            frame = video.get_frame(timecode)
            image = Image.fromarray(frame)
            
            # Sauvegarder l'image dans un fichier temporaire
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                image.save(tmp.name)
                ui.show_info(f"Image sauvegardée : {tmp.name}")
                image.show()
    except Exception as e:
        ui.show_error(f"Erreur lors de l'affichage de l'image pour {os.path.basename(file_path)}: {str(e)}")

def extract_audio(file_path: str, output_path: str = None) -> Optional[str]:
    """
    Extrait l'audio d'une vidéo.
    
    Args:
        file_path (str): Chemin du fichier vidéo
        output_path (str, optional): Chemin de sortie pour le fichier audio
        
    Returns:
        Optional[str]: Chemin du fichier audio extrait ou None en cas d'erreur
    """
    try:
        with VideoFileClip(file_path) as video:
            if video.audio is None:
                ui.show_warning(f"Pas de piste audio dans {os.path.basename(file_path)}")
                return None
            
            if output_path is None:
                output_path = os.path.splitext(file_path)[0] + '.mp3'
            
            video.audio.write_audiofile(output_path)
            ui.show_success(f"Audio extrait vers : {output_path}")
            return output_path
    except Exception as e:
        ui.show_error(f"Erreur lors de l'extraction audio de {os.path.basename(file_path)}: {str(e)}")
        return None

def similarity_score(video1: dict, video2: dict, threshold: float) -> float:
    """
    Calcule un score de similarité entre deux vidéos basé sur plusieurs critères.
    
    Args:
        video1 (dict): Informations de la première vidéo
        video2 (dict): Informations de la deuxième vidéo
        threshold (float): Seuil de similarité
        
    Returns:
        float: Score de similarité entre 0 et 1
    """
    if not video1 or not video2:
        return 0.0

    # Comparaison de durée
    duration_similarity = 1 - abs(video1["duration"] - video2["duration"]) / max(video1["duration"], video2["duration"])

    # Comparaison de résolution
    resolution_similarity = 1 if video1["resolution"] == video2["resolution"] else 0

    # Comparaison des hash de frames
    try:
        hash_similarities = []
        for h1, h2 in zip(video1["hashes"], video2["hashes"]):
            if isinstance(h1, str):
                h1 = imagehash.hex_to_hash(h1)
            if isinstance(h2, str):
                h2 = imagehash.hex_to_hash(h2)
            hash_similarities.append(1 - hamming(h1.hash.flatten(), h2.hash.flatten()))
        hash_similarity = sum(hash_similarities) / len(hash_similarities)
    except Exception as e:
        ui.show_warning(f"Erreur lors de la comparaison des hashes: {str(e)}")
        hash_similarity = 0

    # Comparaison audio
    if video1.get("audio_signature") is not None and video2.get("audio_signature") is not None:
        try:
            audio_similarity = np.dot(video1["audio_signature"], video2["audio_signature"])
        except Exception as e:
            ui.show_warning(f"Erreur lors de la comparaison audio: {str(e)}")
            audio_similarity = 0
    else:
        audio_similarity = 0

    # Calcul du score global avec pondération
    weights = {
        'duration': 0.35,
        'resolution': 0.15,
        'hash': 0.35,
        'audio': 0.15
    }
    
    overall_score = (
        weights['duration'] * duration_similarity +
        weights['resolution'] * resolution_similarity +
        weights['hash'] * hash_similarity +
        weights['audio'] * audio_similarity
    )
    
    return overall_score

def get_video_duration(file_path: str) -> float:
    """Retourne la durée d'une vidéo en secondes."""
    try:
        with VideoFileClip(file_path) as video:
            return video.duration
    except Exception as e:
        console.print(f"[bold red]Erreur lors de l'obtention de la durée pour {file_path} : {e}[/bold red]")
        return 0
