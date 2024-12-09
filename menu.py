from rich.table import Table
from prompt_toolkit import prompt
from prompt_toolkit.completion import PathCompleter
from config_manager import config
from duplicate_manager import *
from ffmpeg_utils import *
from file_utils import file_manager
from video_utils import *
from rich.console import Console
from pathlib import Path
import os
from regex_manager import *
from layout import Layout
from ui import ui

console = Console()
DEFAULT_IGNORE_KEYWORD = "cvt"  # Mot-clé par défaut pour ignorer les fichiers pendant la conversion

def edit_video_formats():
    """Permet de modifier la liste des formats vidéo dans la configuration."""
    current_formats = config.get_video_formats()
    console.print(f"Formats vidéo actuels : {', '.join(current_formats)}")
    new_formats = prompt("Entrez les nouveaux formats vidéo séparés par des virgules (ex: .mp4, .mkv) : ")
    
    # Transforme la saisie utilisateur en liste et met à jour la configuration
    updated_formats = [fmt.strip().lower() for fmt in new_formats.split(",") if fmt.strip()]
    config.set_video_formats(updated_formats)
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
    default_directory = config.get_last_directory(function)
    completer = PathCompleter(only_directories=True)
    directory = prompt(f"{prompt_text} (par défaut: [{default_directory}]): ", completer=completer) or default_directory
    if os.path.isdir(directory):
        config.remember_directory(directory, function)
        return directory
    else:
        console.print(":x: [bold red]Le chemin n'est pas valide, veuillez réessayer.[/bold red]")
        return select_directory(prompt_text, function)

def rename_videos_in_directory(directory: str):
    """Renomme les vidéos d'un répertoire en fonction du titre dans les métadonnées."""
    video_files = [f for f in Path(directory).rglob('*') if f.is_file() and f.suffix.lower() in config.get_video_formats()]
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
        formats=config.get_video_formats(),
        min_size_mb=min_size_mb,
        delete_larger_original=delete_larger_original,
        keyword=keyword
    )

def display_menu():
    """Affiche le menu principal et gère la sélection de l'utilisateur."""
    while True:
        console.print("\n[bold yellow]=== Gestionnaire de Vidéos ===[/bold yellow]")
        
        # Créer un layout pour une meilleure organisation
        layout = Layout()
        layout.split_column(
            Layout(name="header"),
            Layout(name="menu"),
            Layout(name="footer")
        )
        
        # En-tête avec statistiques
        header = Table.grid(padding=1)
        stats = file_manager.get_operation_stats()
        header.add_row(
            f"[cyan]Opérations totales:[/] {stats['total_operations']}",
            f"[green]Taux de succès:[/] {stats['success_rate']:.1f}%",
            f"[yellow]Taille traitée:[/] {ui.format_size(stats['total_size_processed'])}"
        )
        layout["header"].update(Panel(header, title="Statistiques", border_style="blue"))
        
        # Menu principal
        menu_table = Table(show_header=True, header_style="bold magenta", expand=True)
        menu_table.add_column("Option", style="dim", width=8)
        menu_table.add_column("Description", width=40)
        menu_table.add_column("Détails", width=30)
        
        menu_items = [
            ("1", "Convertir une vidéo", "Conversion individuelle avec options"),
            ("2", "Convertir un dossier", "Traitement par lot avec filtres"),
            ("3", "Rechercher des doublons", "Analyse multi-critères"),
            ("4", "Copier sous-dossier", "Sans dossier racine"),
            ("5", "Copier structure", "Dossiers uniquement"),
            ("6", "Formats vidéo", "Gérer les extensions"),
            ("7", "Renommer vidéos", "Par métadonnées"),
            ("8", "Expressions régulières", "Gestion avancée"),
            ("9", "Mots-clés", "Traitement des noms"),
            ("10", "Appliquer regex", "Aux noms de fichiers"),
            ("11", "Quitter", "Sortir du programme")
        ]
        
        for option, desc, details in menu_items:
            menu_table.add_row(option, desc, f"[dim]{details}[/]")
        
        layout["menu"].update(Panel(menu_table, title="Menu Principal", border_style="magenta"))
        
        # Pied de page avec aide
        footer = Table.grid(padding=1)
        footer.add_row(
            "[dim]Utilisez les numéros pour sélectionner une option[/]",
            "[dim]Pressez Ctrl+C pour annuler une opération[/]"
        )
        layout["footer"].update(Panel(footer, title="Aide", border_style="green"))
        
        # Afficher le layout
        console.print(layout)
        
        # Gérer la sélection
        try:
            choice = prompt("\nChoisissez une option [1-11]: ")
            
            if choice == "1":
                convert_single_video()
            elif choice == "2":
                convert_folder()
            elif choice == "3":
                search_duplicates()
            elif choice == "4":
                copy_subfolder()
            elif choice == "5":
                copy_structure()
            elif choice == "6":
                edit_video_formats()
            elif choice == "7":
                rename_videos()
            elif choice == "8":
                manage_regex()
            elif choice == "9":
                manage_keywords()
            elif choice == "10":
                apply_regex()
            elif choice == "11":
                if confirm_exit():
                    break
            else:
                console.print("[bold red]Option invalide. Veuillez réessayer.[/]")
                
        except KeyboardInterrupt:
            if confirm_exit():
                break
        except Exception as e:
            console.print(f"[bold red]Erreur: {str(e)}[/]")
            if confirm_continue():
                continue
            break

def confirm_exit() -> bool:
    """Demande confirmation avant de quitter."""
    return prompt("Voulez-vous vraiment quitter ? (o/n): ").lower() == 'o'

def confirm_continue() -> bool:
    """Demande si l'utilisateur veut continuer après une erreur."""
    return prompt("Voulez-vous continuer ? (o/n): ").lower() == 'o'

def convert_single_video():
    """Interface améliorée pour la conversion d'une seule vidéo."""
    ui.show_header("Conversion de Vidéo", "Conversion d'un fichier unique avec options avancées")
    
    source = select_file("Entrez le chemin de la vidéo à convertir")
    if not source:
        return
    
    # Afficher les informations de la vidéo
    info = get_video_info(source)
    if info:
        display_video_info(info)
    
    # Options de conversion
    output_format = prompt("Format de sortie (ex: mp4, mkv) [mp4]: ", default="mp4")
    quality = prompt("Qualité (1-31, plus bas = meilleure qualité) [23]: ", default="23")
    try:
        quality = int(quality)
        if not 1 <= quality <= 31:
            raise ValueError()
    except ValueError:
        ui.show_error("Qualité invalide, utilisation de la valeur par défaut (23)")
        quality = 23
    
    # Options avancées
    if prompt("Voulez-vous configurer les options avancées ? (o/n): ").lower() == 'o':
        bitrate = prompt("Débit binaire (ex: 800k, 2M) [auto]: ")
        resolution = prompt("Résolution (ex: 1920x1080) [originale]: ")
        audio_bitrate = prompt("Débit audio (ex: 128k) [original]: ")
    else:
        bitrate = None
        resolution = None
        audio_bitrate = None
    
    # Confirmation
    if not prompt("Voulez-vous lancer la conversion ? (o/n): ").lower() == 'o':
        return
    
    # Lancer la conversion
    success = convert_file_action(
        source,
        output_format,
        crf=quality,
        bitrate=bitrate,
        resolution=resolution,
        audio_bitrate=audio_bitrate
    )
    
    if success:
        ui.show_success("Conversion terminée avec succès !")
    else:
        ui.show_error("La conversion a échoué")

def display_video_info(info: Dict):
    """Affiche les informations d'une vidéo de manière formatée."""
    table = Table(title="Informations de la Vidéo", show_header=False, title_style="bold cyan")
    table.add_column("Propriété", style="green")
    table.add_column("Valeur", style="yellow")
    
    info_map = {
        "Durée": f"{info['duration']:.2f}s",
        "Résolution": f"{info['resolution'][0]}x{info['resolution'][1]}",
        "Images/s": f"{info['fps']:.2f}",
        "Taille": ui.format_size(info['size']),
        "Audio": "Oui" if info['has_audio'] else "Non"
    }
    
    for prop, val in info_map.items():
        table.add_row(prop, str(val))
    
    if 'quality_metrics' in info:
        table.add_section()
        table.add_row("Qualité", "")
        for metric, value in info['quality_metrics'].items():
            table.add_row(f"  {metric.title()}", f"{value:.2%}")
    
    console.print(table)
