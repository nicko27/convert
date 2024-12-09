import pytest
from pathlib import Path
import numpy as np
from video_utils import (
    get_video_info,
    analyze_video_quality,
    get_video_segments,
    extract_frames,
    get_video_hash,
    get_audio_signature
)
from moviepy.editor import VideoFileClip

@pytest.fixture
def sample_video(tmp_path):
    """Crée une vidéo de test."""
    video_path = tmp_path / "test.mp4"
    # Créer une vidéo synthétique pour les tests
    duration = 5.0
    fps = 30
    frames = []
    for t in np.linspace(0, duration, int(duration * fps)):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        # Ajouter un motif qui change avec le temps
        frame[:, :, 0] = int(255 * (t / duration))  # Rouge variant avec le temps
        frames.append(frame)
    
    clip = VideoFileClip(frames, fps=fps)
    clip.write_videofile(str(video_path))
    return str(video_path)

def test_get_video_info(sample_video):
    """Test la fonction get_video_info."""
    info = get_video_info(sample_video)
    assert info is not None
    assert 'duration' in info
    assert 'resolution' in info
    assert 'fps' in info
    assert 'size' in info
    assert 'has_audio' in info
    assert 'quality_metrics' in info

def test_analyze_video_quality(sample_video):
    """Test la fonction analyze_video_quality."""
    with VideoFileClip(sample_video) as video:
        metrics = analyze_video_quality(video)
    
    assert isinstance(metrics, dict)
    assert 'sharpness' in metrics
    assert 'noise_level' in metrics
    assert 'brightness' in metrics
    assert 'contrast' in metrics
    assert 'saturation' in metrics
    
    # Vérifier que les valeurs sont normalisées
    for value in metrics.values():
        assert 0 <= value <= 1

def test_get_video_segments(sample_video):
    """Test la fonction get_video_segments."""
    segments = get_video_segments(sample_video)
    assert isinstance(segments, list)
    assert len(segments) > 0
    
    for segment in segments:
        assert 'start_time' in segment
        assert 'end_time' in segment
        assert 'duration' in segment
        assert 'avg_brightness' in segment
        assert 'motion_level' in segment
        
        assert segment['start_time'] >= 0
        assert segment['end_time'] > segment['start_time']
        assert segment['duration'] == segment['end_time'] - segment['start_time']

def test_extract_frames(sample_video):
    """Test la fonction extract_frames."""
    # Test avec timestamps spécifiques
    timestamps = [0.0, 1.0, 2.0]
    frames = extract_frames(sample_video, timestamps=timestamps)
    assert len(frames) == len(timestamps)
    
    # Test avec nombre de frames
    num_frames = 5
    frames = extract_frames(sample_video, num_frames=num_frames)
    assert len(frames) == num_frames

def test_get_video_hash(sample_video):
    """Test la fonction get_video_hash."""
    hash1 = get_video_hash(sample_video)
    assert isinstance(hash1, str)
    assert len(hash1) > 0
    
    # Le même timecode devrait donner le même hash
    hash2 = get_video_hash(sample_video)
    assert hash1 == hash2

def test_get_audio_signature(sample_video):
    """Test la fonction get_audio_signature."""
    signature = get_audio_signature(sample_video)
    if signature is not None:
        assert isinstance(signature, np.ndarray)
        assert len(signature.shape) == 1  # Vecteur 1D

def test_invalid_video():
    """Test avec un fichier vidéo invalide."""
    with pytest.raises(FileNotFoundError):
        get_video_info("invalid_video.mp4")

def test_corrupted_video(tmp_path):
    """Test avec un fichier vidéo corrompu."""
    corrupted_file = tmp_path / "corrupted.mp4"
    corrupted_file.write_bytes(b"corrupted data")
    
    info = get_video_info(str(corrupted_file))
    assert info is None
