from rich.table import Table
from prompt_toolkit import prompt
from prompt_toolkit.completion import PathCompleter
from config_manager import *
from duplicate_manager import *
from ffmpeg_utils import *
from file_utils import *
from video_utils import *
from rich.console import Console
from pathlib import Path
import os
from regex_manager import *

console = Console()
DEFAULT_IGNORE_KEYWORD = "cvt"  # Mot-clé par défaut pour ignorer les fichiers pendant la conversion

def edit_video_formats():
    """Permet de modifier la liste des formats vidéo dans la configuration."""
    current_formats = get_video_formats()
    console.print(f"Formats vidéo actuels : {', '.join(current_formats)}")
    new_formats = prompt("Entrez les nouveaux formats vidéo séparés par des virgules (ex: .mp4, .mkv) : ")
    
    # Transforme la saisie utilisateur en liste et met à jour la configuration
    updated_formats = [fmt.strip().lower() for fmt in new_formats.split(",") if fmt.strip()]
    set_video_formats(updated_formats)
    console.print(f"[bold green]Formats vidéo mis à jour : {', '.join(updated_formats)}[/bold green]")

def select_file(prompt_text: str, default: str = "") -> str:
    """Utilise PathCompleter pour sélectionner un fichier avec complétion automatique."""
    completer = PathCompleter(only_directories=False)
    while True:
        file_path = prompt(f"{prompt_text} (par défaut: [{default}]): ", completer=completer) or default
        if os.path.isfile(file_path):
            return file_path
        else:
            console.print(":x: [bold red]Le chemin du fichier n'est pas valide, veuillez réessayer.[/bold red]")

def select_directory(prompt_text: str, function: str) -> str:
    """Demande un chemin de dossier pour une fonction spécifique avec le dernier dossier utilisé par défaut."""
    default_directory = get_last_directory(function)
    completer = PathCompleter(only_directories=True)
    directory = prompt(f"{prompt_text} (par défaut: [{default_directory}]): ", completer=completer) or default_directory
    if os.path.isdir(directory):
        remember_directory(directory, function)
        return directory
    else:
        console.print(":x: [bold red]Le chemin n'est pas valide, veuillez réessayer.[/bold red]")
        return select_directory(prompt_text, function)

def rename_videos_in_directory(directory: str):
    """Renomme les vidéos d'un répertoire en fonction du titre dans les métadonnées."""
    video_files = [f for f in Path(directory).rglob('*') if f.is_file() and f.suffix.lower() in get_video_formats()]
    for file_path in video_files:
        metadata = get_video_metadata(str(file_path))
        if metadata:
            title = metadata.get('title')
            if title:
                new_name = f"{title}{file_path.suffix}"
                new_path = file_path.with_name(new_name)
                console.print(f"\n[bold cyan]Vidéo : {file_path}[/bold cyan]")
                console.print(f"Titre : {title}")
                console.print(f"Nouveau nom proposé : {new_name}")
                rename_choice = prompt("Renommer ce fichier ? (o pour oui, n pour ignorer) : ").lower()
                if rename_choice == "o":
                    try:
                        file_path.rename(new_path)
                        console.print(f"[bold green]Fichier renommé avec succès : {new_path}[/bold green]")
                    except Exception as e:
                        console.print(f"[bold red]Erreur lors du renommage de {file_path} : {e}[/bold red]")
                else:
                    console.print("[bold yellow]Renommage ignoré pour ce fichier.[/bold yellow]")
            else:
                console.print(f"[bold yellow]Pas de titre disponible pour : {file_path}[/bold yellow]")


def convert_videos_in_folder():
    """Convertit toutes les vidéos dans un dossier avec des options supplémentaires."""
    source = select_directory("Entrez le chemin du dossier contenant les vidéos à convertir", "conversion_folder")
    keyword = prompt("Mot-clé pour ignorer certains fichiers (par défaut: cvt): ", default="cvt")
    
    # Nouvelle option pour la taille minimale et suppression du fichier plus grand
    min_size_mb = float(prompt("Taille minimale en Mo pour les fichiers à convertir : ", default="1024"))
    delete_larger_original = prompt(
        "Voulez-vous supprimer le fichier le plus grand après la conversion ? (o/n): "
    ).strip().lower() == 'o'
    
    process_files_in_folder(
        directory=source,
        formats=get_video_formats(),
        min_size_mb=min_size_mb,
        delete_larger_original=delete_larger_original,
        keyword=keyword
    )

def display_menu():
    """Affiche le menu principal et gère la sélection de l'utilisateur."""
    while True:
        console.print("\n[bold yellow]=== Gestionnaire de Vidéos ===[/bold yellow]")
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Option", style="dim")
        table.add_column("Description")
        table.add_row("1", "Convertir une vidéo")
        table.add_row("2", "Convertir toutes les vidéos dans un dossier")
        table.add_row("3", "Rechercher des doublons dans un dossier")
        table.add_row("4", "Copier uniquement le contenu d'un sous-dossier sans son dossier racine")
        table.add_row("5", "Copier uniquement la structure des dossiers sans les fichiers")
        table.add_row("6", "Modifier les formats de fichiers vidéo")
        table.add_row("7", "Renommer toutes les vidéos dans une arborescence")
        table.add_row("8", "Gérer et appliquer les expressions régulières")
        table.add_row("9", "Gérer les mots pour traitement des noms de fichiers")
        table.add_row("10", "Appliquer la suppression ou l'ajout d'espace aux noms de fichiers")
        table.add_row("11", "Quitter")
        console.print(table)

        choice = prompt("Choisissez une option [1-11]: ")

        if choice == "1":
            source = select_file("Entrez le chemin de la vidéo à convertir")
            output_format = prompt("Entrez le format de sortie (ex: mp4, mkv) [par défaut: mp4]: ", default="mp4")
            convert_file_action(source, output_format)
        
        elif choice == "2":
            convert_videos_in_folder()

        elif choice == "3":
            source = select_directory("Entrez le chemin du dossier à analyser pour les doublons", "duplicates")
            reset_analysis = prompt("Ignorer les données précédentes et réinitialiser l'analyse ? (o/n): ").lower() == 'o'
            threshold = float(prompt("Entrez le seuil de similarité (ex: 0.85 pour 85%) [par défaut: 0.85]: ", default="0.85"))
            find_duplicates_in_folder(source, threshold, reset_analysis=reset_analysis)

        elif choice == "4":
            source = select_directory("Entrez le chemin du sous-dossier à copier sans son dossier racine", "copy_subfolder")
            destination = select_directory("Entrez le dossier de destination", "copy_subfolder_dest")

            # Demander confirmation pour la suppression après la copie
            delete_after_copy = prompt("Voulez-vous supprimer les fichiers sources après la copie ? (o/n): ",default="o").lower() == 'o'
            
            # Copier les fichiers sans inclure le dossier racine
            copy_folder_contents(source, destination, False, delete_after_copy)

        elif choice == "5":
            source = select_directory("Entrez le chemin du dossier pour copier sa structure uniquement", "copy_structure")
            destination = select_directory("Entrez le dossier de destination pour la structure", "copy_structure_dest")
            copy_folder_structure(source, destination)

        elif choice == "6":
            edit_video_formats()

        elif choice == "7":
            directory = select_directory("Entrez le chemin de l'arborescence à analyser", "rename_videos")
            rename_videos_in_directory(directory)
        
        elif choice == "8":
            directory = select_directory("Entrez le dossier pour appliquer les expressions régulières", "regex_application")
            manage_regex_patterns_and_analyze(directory)

        elif choice == "9":
            manage_words_to_remove()

        elif choice == "10":
            directory = select_directory("Entrez le dossier où appliquer la suppression des mots", "apply_words")
            auto_mode = prompt("Souhaitez-vous activer le mode automatique pour appliquer les actions sur les mots trouvés ? (o/n): ", default="o").lower() == 'o'
            apply_words_to_files(directory, auto_mode)

        elif choice == "11":
            console.print("[bold green]Au revoir ![/bold green]")
            break
        else:
            console.print("[bold red]Option invalide. Veuillez choisir une option valide.[/bold red]")
