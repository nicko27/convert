import pytest
from pathlib import Path
from ffmpeg_utils import get_video_metadata, convert_file_action, repair_video
import os

@pytest.fixture
def sample_video(tmp_path):
    """Crée un fichier vidéo de test."""
    video_path = tmp_path / "test.mp4"
    # TODO: Créer un fichier vidéo de test minimal
    return str(video_path)

def test_get_video_metadata(sample_video):
    """Test la fonction get_video_metadata."""
    metadata = get_video_metadata(sample_video)
    assert isinstance(metadata, dict)
    assert "duration" in metadata
    assert "resolution" in metadata
    assert "fps" in metadata

def test_convert_file_action(sample_video):
    """Test la fonction de conversion."""
    success, output_path = convert_file_action(
        sample_video,
        "mp4",
        delete_larger_original=False
    )
    assert success
    assert Path(output_path).exists()
    assert Path(output_path).suffix == ".mp4"

def test_repair_video(sample_video):
    """Test la fonction de réparation."""
    success, repaired_path = repair_video(sample_video)
    assert success
    assert Path(repaired_path).exists()

def test_invalid_file():
    """Test avec un fichier invalide."""
    with pytest.raises(FileNotFoundError):
        get_video_metadata("invalid_file.mp4")

def test_corrupted_file(tmp_path):
    """Test avec un fichier corrompu."""
    corrupted_file = tmp_path / "corrupted.mp4"
    corrupted_file.write_bytes(b"corrupted data")
    with pytest.raises(ValueError):
        get_video_metadata(str(corrupted_file))
