
import os
import shutil
from send2trash import send2trash
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
from config_manager import get_video_formats

console = Console()

import os
import shutil
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
from config_manager import get_video_formats  # Assurez-vous que get_video_formats est correctement importé

console = Console()

def copy_folder_contents(source_folder: str, destination_folder: str, include_root: bool = False,delete_after_copy: bool = False):
    """
    Copie les fichiers vidéo du dossier source vers le dossier de destination, en recréant la structure de sous-dossiers.
    Affiche une barre de progression pour indiquer l'avancement de la copie.
    
    :param source_folder: Chemin du dossier source contenant les fichiers à copier.
    :param destination_folder: Chemin du dossier de destination où les fichiers seront copiés.
    :param delete_after_copy: Si True, supprime les fichiers source après la copie.
    :param include_root: Si True, recrée le dossier racine source dans la destination.
    """
    video_formats = get_video_formats()  # Obtenez les formats de fichiers vidéo pris en charge
    files_to_copy = [f for f in Path(source_folder).rglob('*') if f.is_file() and f.suffix.lower() in video_formats]
    total_files = len(files_to_copy)

    if total_files == 0:
        console.print("[bold yellow]Aucun fichier vidéo à copier dans le dossier source.[/bold yellow]")
        return

    # Ajuster le chemin de base en fonction de l'option include_root
    if include_root:
        base_destination = Path(destination_folder) / Path(source_folder).name
    else:
        base_destination = Path(destination_folder)

    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Copie des fichiers", total=total_files)

        for file_path in files_to_copy:
            # Construire le chemin de destination en fonction de l'option include_root
            relative_path = file_path.relative_to(source_folder)
            destination_path = base_destination / relative_path.parent

            # Créer tous les dossiers intermédiaires si nécessaire
            destination_path.mkdir(parents=True, exist_ok=True)

            # Copier le fichier vers le chemin de destination
            if not os.path.isfile(destination_path / file_path.name):
                shutil.copy2(file_path, destination_path / file_path.name)

                # Supprimer le fichier source si l'option est activée
                if delete_after_copy:
                    file_path.unlink()
                    console.print(f"[bold red]Fichier source supprimé : {file_path}[/bold red]")
            else:
                console.print(f"[bold red]Il y a déja un fichier portant le même nom dans la destination, fichier non copié[/bold red]")
            # Mettre à jour la barre de progression
            progress.update(task, advance=1)

    console.print("[bold green]Copie terminée ![/bold green]")


def copy_file(source_file: str, destination_folder: str) -> None:
    """Copie un fichier vers un dossier spécifié."""
    try:
        destination_path = Path(destination_folder) / Path(source_file).name
        shutil.copy2(source_file, destination_path)
        console.print(f":white_check_mark: Fichier copié vers [bold green]{destination_path}[/bold green]")
    except Exception as e:
        console.print(f":x: Erreur lors de la copie du fichier : {e}", style="bold red")

def copy_folder_with_files(source_folder: str, destination_folder: str, delete_source: bool = False) -> None:
    """Copie un dossier entier avec tous ses fichiers, et supprime la source si demandé."""
    try:
        destination_path = Path(destination_folder) / Path(source_folder).name
        shutil.copytree(source_folder, destination_path, dirs_exist_ok=True)
        console.print(f":white_check_mark: Dossier copié vers [bold green]{destination_path}[/bold green]")

        if delete_source:
            shutil.rmtree(source_folder)
            console.print(f"[bold red]Source supprimée : {source_folder}[/bold red]")

    except Exception as e:
        console.print(f":x: Erreur lors de la copie du dossier : {e}", style="bold red")

def copy_folder_structure(source_folder: str, destination_folder: str) -> None:
    """Copie seulement la structure du dossier sans les fichiers."""
    try:
        for root, dirs, _ in os.walk(source_folder):
            for dir_name in dirs:
                dir_path = Path(root) / dir_name
                relative_path = dir_path.relative_to(source_folder)
                destination_path = Path(destination_folder) / relative_path
                destination_path.mkdir(parents=True, exist_ok=True)
        console.print(f":white_check_mark: Structure de dossier copiée vers [bold green]{destination_folder}[/bold green]")
    except Exception as e:
        console.print(f":x: Erreur lors de la copie de la structure du dossier : {e}", style="bold red")
