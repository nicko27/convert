from setuptools import setup, find_packages

setup(
    name="video-converter",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "ffmpeg-python>=0.2.0",
        "moviepy>=1.0.3",
        "Pillow>=9.0.0",
        "rich>=10.0.0",
        "send2trash>=1.8.0",
        "imagehash>=4.3.0",
        "pytest>=7.0.0",
        "mypy>=0.950",
        "types-Pillow>=9.0.0",
        "prompt_toolkit>=3.0.0",
        "ffmpeg-progress-yield>=0.7.0",
        "typing-extensions>=4.0.0",
    ],
)
