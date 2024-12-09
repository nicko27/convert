import re
import os
from pathlib import Path
from rich.console import Console
from prompt_toolkit import prompt
from config_manager import load_json_data, save_json_data
import json
from datetime import datetime
from rich.table import Table

console = Console()

class RegexPattern:
    """Classe pour gérer un pattern regex avec ses paramètres."""
    def __init__(self, pattern: str, action: str = 'd', replace_with: str = " ",
                 position: str = 'p', allow_mid_word: str = 'n', priority: int = 1,
                 description: str = "", enabled: bool = True):
        self.pattern = pattern
        self.action = action
        self.replace_with = replace_with
        self.position = position
        self.allow_mid_word = allow_mid_word
        self.priority = priority
        self.description = description
        self.enabled = enabled
        self.usage_count = 0
        self.last_used = None

    def to_dict(self):
        """Convertit l'objet en dictionnaire pour la sauvegarde."""
        return {
            "pattern": self.pattern,
            "action": self.action,
            "replace_with": self.replace_with,
            "position": self.position,
            "allow_mid_word": self.allow_mid_word,
            "priority": self.priority,
            "description": self.description,
            "enabled": self.enabled,
            "usage_count": self.usage_count,
            "last_used": self.last_used
        }

    @classmethod
    def from_dict(cls, data: dict):
        """Crée un objet RegexPattern à partir d'un dictionnaire."""
        pattern = cls(
            pattern=data["pattern"],
            action=data.get("action", "d"),
            replace_with=data.get("replace_with", " "),
            position=data.get("position", "p"),
            allow_mid_word=data.get("allow_mid_word", "n"),
            priority=data.get("priority", 1),
            description=data.get("description", ""),
            enabled=data.get("enabled", True)
        )
        pattern.usage_count = data.get("usage_count", 0)
        pattern.last_used = data.get("last_used")
        return pattern

    def get_compiled_pattern(self) -> str:
        """Retourne le pattern compilé selon la position et les conditions de mot."""
        if self.position == "d":
            return rf"^{self.pattern}"
        elif self.position == "f":
            return rf"{self.pattern}$"
        else:
            return rf"\b{self.pattern}\b" if self.allow_mid_word == "n" else self.pattern

    def apply_to_text(self, text: str) -> tuple[str, bool]:
        """Applique le pattern au texte et retourne le résultat et si une modification a été faite."""
        if not self.enabled:
            return text, False

        compiled_pattern = self.get_compiled_pattern()
        original_text = text

        if self.action == "d":
            text = re.sub(compiled_pattern, "", text, flags=re.IGNORECASE)
        elif self.action == "r":
            text = re.sub(compiled_pattern, self.replace_with, text, flags=re.IGNORECASE)
        elif self.action == "s":
            text = re.sub(compiled_pattern, f"{self.pattern} ", text, flags=re.IGNORECASE)

        was_modified = text != original_text
        if was_modified:
            self.usage_count += 1
            self.last_used = datetime.now().isoformat()

        return text.strip(), was_modified

def manage_regex_patterns_and_analyze(directory: str):
    """Gère les expressions régulières avec des fonctionnalités améliorées."""
    data = load_json_data()
    patterns = [RegexPattern.from_dict(p) if isinstance(p, dict) else 
               RegexPattern(p) for p in data.get("regex_patterns", [])]

    while True:
        console.print("\n[bold cyan]Gestion des expressions régulières :[/bold cyan]")
        console.print("1. Ajouter une expression régulière")
        console.print("2. Supprimer une expression régulière")
        console.print("3. Modifier une expression régulière")
        console.print("4. Appliquer les expressions régulières")
        console.print("5. Voir les statistiques d'utilisation")
        console.print("6. Tester une expression sur un texte")
        console.print("7. Activer/Désactiver des expressions")
        console.print("8. Gérer les priorités")
        console.print("9. Exporter/Importer des patterns")
        console.print("10. Quitter")

        choice = prompt("\nChoisissez une option : ")

        if choice == "1":
            pattern = RegexPattern(
                pattern=prompt("Expression régulière : "),
                action=prompt("Action (d/r/s) : ", default="d"),
                replace_with=prompt("Remplacement : ") if prompt("Action (d/r/s) : ", default="d") == "r" else " ",
                position=prompt("Position (d/f/p) : ", default="p"),
                allow_mid_word=prompt("Milieu de mot (o/n) : ", default="n"),
                priority=int(prompt("Priorité (1-10) : ", default="1")),
                description=prompt("Description : ")
            )
            patterns.append(pattern)
            console.print("[green]Pattern ajouté avec succès ![/green]")

        elif choice == "5":
            show_pattern_statistics(patterns)

        elif choice == "6":
            test_text = prompt("Entrez le texte à tester : ")
            test_patterns_on_text(patterns, test_text)

        elif choice == "7":
            manage_pattern_status(patterns)

        elif choice == "8":
            manage_pattern_priorities(patterns)

        elif choice == "9":
            export_import_patterns(patterns)

        elif choice == "10":
            break

        else:
            console.print("[bold red]Choix invalide. Veuillez réessayer.[/bold red]")

    save_patterns(patterns)

def show_pattern_statistics(patterns: list[RegexPattern]):
    """Affiche les statistiques d'utilisation des patterns."""
    console.print("\n[bold cyan]Statistiques d'utilisation :[/bold cyan]")
    
    sorted_patterns = sorted(patterns, key=lambda p: p.usage_count, reverse=True)
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Pattern")
    table.add_column("Utilisations")
    table.add_column("Dernière utilisation")
    table.add_column("Statut")
    
    for p in sorted_patterns:
        last_used = "Jamais" if not p.last_used else p.last_used.split('T')[0]
        status = "[green]Actif[/green]" if p.enabled else "[red]Inactif[/red]"
        table.add_row(p.pattern, str(p.usage_count), last_used, status)
    
    console.print(table)

def test_patterns_on_text(patterns: list[RegexPattern], test_text: str):
    """Teste l'application des patterns sur un texte donné."""
    console.print("\n[bold cyan]Test des patterns :[/bold cyan]")
    
    current_text = test_text
    for p in sorted(patterns, key=lambda x: x.priority, reverse=True):
        if not p.enabled:
            continue
            
        modified_text, was_modified = p.apply_to_text(current_text)
        if was_modified:
            console.print(f"\nPattern : [yellow]{p.pattern}[/yellow]")
            console.print(f"Avant  : [red]{current_text}[/red]")
            console.print(f"Après  : [green]{modified_text}[/green]")
            current_text = modified_text

def manage_pattern_status(patterns: list[RegexPattern]):
    """Gère l'activation/désactivation des patterns."""
    while True:
        console.print("\n[bold cyan]Statut des patterns :[/bold cyan]")
        for i, p in enumerate(patterns, 1):
            status = "[green]Actif[/green]" if p.enabled else "[red]Inactif[/red]"
            console.print(f"{i}. {p.pattern} - {status}")
        
        choice = prompt("\nNuméro du pattern à modifier (q pour quitter) : ")
        if choice.lower() == 'q':
            break
            
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(patterns):
                patterns[idx].enabled = not patterns[idx].enabled
                status = "activé" if patterns[idx].enabled else "désactivé"
                console.print(f"[green]Pattern {patterns[idx].pattern} {status}[/green]")
        except ValueError:
            console.print("[red]Entrée invalide[/red]")

def manage_pattern_priorities(patterns: list[RegexPattern]):
    """Gère les priorités des patterns."""
    while True:
        console.print("\n[bold cyan]Priorités des patterns :[/bold cyan]")
        for i, p in enumerate(patterns, 1):
            console.print(f"{i}. {p.pattern} - Priorité : {p.priority}")
        
        choice = prompt("\nNuméro du pattern à modifier (q pour quitter) : ")
        if choice.lower() == 'q':
            break
            
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(patterns):
                new_priority = int(prompt(f"Nouvelle priorité pour {patterns[idx].pattern} (1-10) : "))
                if 1 <= new_priority <= 10:
                    patterns[idx].priority = new_priority
                    console.print("[green]Priorité mise à jour[/green]")
                else:
                    console.print("[red]La priorité doit être entre 1 et 10[/red]")
        except ValueError:
            console.print("[red]Entrée invalide[/red]")

def export_import_patterns(patterns: list[RegexPattern]):
    """Gère l'export et l'import des patterns."""
    while True:
        console.print("\n[bold cyan]Export/Import des patterns :[/bold cyan]")
        console.print("1. Exporter les patterns")
        console.print("2. Importer des patterns")
        console.print("3. Retour")
        
        choice = prompt("\nChoisissez une option : ")
        
        if choice == "1":
            export_file = prompt("Nom du fichier d'export : ")
            patterns_data = [p.to_dict() for p in patterns]
            with open(export_file, 'w') as f:
                json.dump(patterns_data, f, indent=2)
            console.print(f"[green]Patterns exportés vers {export_file}[/green]")
            
        elif choice == "2":
            import_file = prompt("Nom du fichier à importer : ")
            try:
                with open(import_file, 'r') as f:
                    imported_data = json.load(f)
                imported_patterns = [RegexPattern.from_dict(p) for p in imported_data]
                
                mode = prompt("Mode d'import (f pour fusionner, r pour remplacer) : ").lower()
                if mode == 'f':
                    patterns.extend(imported_patterns)
                elif mode == 'r':
                    patterns.clear()
                    patterns.extend(imported_patterns)
                    
                console.print("[green]Patterns importés avec succès[/green]")
            except Exception as e:
                console.print(f"[red]Erreur lors de l'import : {e}[/red]")
                
        elif choice == "3":
            break

def save_patterns(patterns: list[RegexPattern]):
    data = load_json_data()
    data["regex_patterns"] = [p.to_dict() for p in patterns]
    save_json_data(data)

def apply_regex_to_files(directory: str, patterns: list[RegexPattern], auto_mode: bool):
    """
    Applique les expressions régulières fournies pour modifier les noms de fichiers dans le répertoire.
    Sélectionne la regex qui réduit le plus la longueur du nom et continue jusqu'à ce qu'il n'y ait plus de réduction.
    
    :param directory: Le répertoire dans lequel appliquer les regex.
    :param patterns: Liste de RegexPattern.
    :param auto_mode: Si True, applique les modifications automatiquement sans confirmation.
    """
    files = [f for f in Path(directory).rglob('*') if f.is_file() and not any(p.startswith('.') for p in f.parts)]
    
    for file in files:
        original_name = file.stem
        modified_name = original_name

        while True:
            best_match = None
            max_reduction = 0

            # Try each pattern and calculate reduction in length
            for pattern in patterns:
                if not pattern.enabled:
                    continue

                modified_text, was_modified = pattern.apply_to_text(modified_name)
                reduction = len(modified_name) - len(modified_text)

                # Choose the pattern that maximizes reduction
                if reduction > max_reduction:
                    max_reduction = reduction
                    best_match = modified_text

            # If a reduction was made, apply it
            if best_match and len(best_match) > 0:
                modified_name = best_match
            else:
                break

        # Final cleanup of extra spaces
        modified_name = re.sub(r"\s{2,}", " ", modified_name).strip()

        # Check for a different final name and propose modification
        final_name = modified_name + file.suffix
        if final_name != original_name + file.suffix and modified_name:
            if auto_mode:
                rename_file(file, final_name)
            else:
                console.print(f"Nom original : {original_name}{file.suffix}")
                console.print(f"Nom proposé : {final_name}")
                choice = prompt("Accepter la modification ? (o/n) : ").lower()
                if choice == "o":
                    rename_file(file, final_name)

def manage_words_to_remove():
    """Permet de gérer les mots à supprimer ou modifier dans les noms de fichiers."""
    data = load_json_data()
    words_to_remove = data.get("words_to_remove", [])

    console.print("Configuration actuelle des mots à traiter dans les noms de fichiers :")
    for idx, item in enumerate(words_to_remove, start=1):
        word = item.get("word", "")
        action = item.get("action", "d")
        position = item.get("position", "p")  # "p" par défaut
        allow_mid_word = item.get("allow_mid_word", "o")  # "f" par défaut
        replace_with = item.get("replace_with", " ") if action == "r" else ""
        
        console.print(f"{idx}. Mot : {word} - Action : {action} - Position : {position} - "
                      f"Autorisé en milieu de mot : {allow_mid_word} - Remplacer par : {replace_with}")

    while True:
        action = prompt("Tapez 'a' pour ajouter un mot, 'm' pour modifier, 's' pour supprimer, ou 'q' pour quitter : ").lower()
        
        if action == 'a':
            word = prompt("Entrez le mot à ajouter : ")
            replace_action = prompt("Entrez l'action ('d' pour supprimer, 'r' pour remplacer, 's' pour ajouter un espace) : ",default="d").lower()
            position = prompt("Entrez la position ('d' pour début, 'f' pour fin, 'p' pour partout) : ",default="p").lower()
            allow_mid_word = prompt("Autoriser en milieu de mot ? (n pour oui, n pour non) : ",default="o").lower()
            replace_with = prompt("Entrez le mot de remplacement (laisser vide pour un espace) : ") if replace_action == "r" else ""

            words_to_remove.append({
                "word": word,
                "action": replace_action,
                "position": position,
                "allow_mid_word": allow_mid_word,
                "replace_with": replace_with or " "
            })

        elif action == 'm':
            idx = int(prompt("Entrez le numéro du mot à modifier : ")) - 1
            if 0 <= idx < len(words_to_remove):
                replace_action = prompt("Entrez l'action ('d' pour supprimer, 'r' pour remplacer, 's' pour ajouter un espace) : ",default="d").lower()
                position = prompt("Entrez la position ('d' pour début, 'f' pour fin, 'p' pour partout) : ",default="p").lower()
                allow_mid_word = prompt("Autoriser en milieu de mot ? (o pour oui, n pour non) : ",default="o").lower()
                replace_with = prompt("Entrez le mot de remplacement (laisser vide pour un espace) : ") if replace_action == "r" else ""

                words_to_remove[idx].update({
                    "action": replace_action,
                    "position": position,
                    "allow_mid_word": allow_mid_word,
                    "replace_with": replace_with or " "
                })

        elif action == 's':
            idx = int(prompt("Entrez le numéro du mot à supprimer : ")) - 1
            if 0 <= idx < len(words_to_remove):
                del words_to_remove[idx]

        elif action == 'q':
            break

        else:
            console.print("[bold red]Option invalide. Veuillez réessayer.[/bold red]")

    data = load_json_data()
    data["words_to_remove"] = words_to_remove
    save_json_data(data)
    console.print("[bold green]Liste mise à jour et enregistrée avec succès.[/bold green]")


def is_hidden_or_system(file_path: Path) -> bool:
    """
    Vérifie si le fichier ou le dossier est caché, système, ou commence par un point.
    :param file_path: Le chemin du fichier ou dossier.
    :return: True si le fichier ou dossier est caché, système ou commence par un point, sinon False.
    """
    # Ignore hidden files and directories (e.g., dot files or system hidden attributes on Windows)
    return any(part.startswith('.') for part in file_path.parts) or is_system_file(file_path)

def is_system_file(file_path: Path) -> bool:
    """
    Vérifie si le fichier est un fichier système (fonction spécifique à Windows, sinon retourne False).
    :param file_path: Le chemin du fichier.
    :return: True si le fichier est un fichier système (sous Windows), sinon False.
    """
    if os.name == 'nt':  # Windows-specific system file check
        try:
            import ctypes
            FILE_ATTRIBUTE_SYSTEM = 0x4
            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(file_path))
            return attrs != -1 and (attrs & FILE_ATTRIBUTE_SYSTEM)
        except (ImportError, AttributeError):
            return False
    return False

def apply_words_to_files(directory: str, auto_mode: bool):
    """
    Applique les mots définis dans `words_to_remove` sur les noms de fichiers d'un répertoire,
    en ignorant les fichiers dans les dossiers cachés, systèmes, ou commençant par un point.
    :param directory: Le chemin du répertoire où appliquer les changements.
    :param auto_mode: Si True, applique les actions automatiquement sans confirmation.
    """
    data = load_json_data()
    words_to_remove = sorted(data.get("words_to_remove", []), key=lambda x: len(x.get("word", "")), reverse=True)

    # Filtre les fichiers à ignorer dans des dossiers cachés ou systèmes
    files = [f for f in Path(directory).rglob('*') if f.is_file() and not is_hidden_or_system(f)]

    for file in files:
        original_name = file.stem
        modified_name = original_name

        # Appliquer les mots dans words_to_remove tant que des changements sont effectués
        changes_made = True
        while changes_made:
            changes_made = False
            for item in words_to_remove:
                word = item.get("word", "").lower()
                action = item.get("action", "d")
                replace_with = item.get("replace_with", " ") if action == "r" else ""
                position = item.get("position", "p")  # "d" pour début, "f" pour fin, "p" pour partout
                allow_mid_word = item.get("allow_mid_word", "n") == "o"

                # Définir le pattern en fonction de la position et de allow_mid_word, en ignorant la casse
                if position == "d":
                    pattern = rf"(?i)^{re.escape(word)}"
                elif position == "f":
                    pattern = rf"(?i){re.escape(word)}$"
                else:
                    pattern = rf"(?i)\b{re.escape(word)}\b" if not allow_mid_word else rf"(?i){re.escape(word)}"

                # Applique l'action de suppression, ajout d'espace, ou remplacement
                new_name = re.sub(pattern, replace_with, modified_name).strip()

                if new_name != modified_name:
                    changes_made = True
                    modified_name = new_name

        # Supprime les espaces supplémentaires (plus de deux) dans le nom de fichier final
        modified_name = re.sub(r"\s{2,}", " ", modified_name)

        # Si le nom final diffère du nom original, proposer la modification
        if modified_name != original_name and len(modified_name)>0:
            final_name = modified_name + file.suffix
            if auto_mode:
                rename_file(file, final_name)
            else:
                console.print(f"Nom original : {file}")
                console.print(f"Nom proposé : {final_name}")
                choice = prompt("Accepter la modification ? (o/n) : ",default="o").lower()
                if choice == "o":
                    rename_file(file, final_name)

def rename_file(file: Path, new_name: str):
    """Renomme le fichier avec le nouveau nom."""
    new_path = file.with_name(new_name)
    try:
        file.rename(new_path)
        console.print(f"[bold green]Fichier renommé :[/bold green] {file} -> {new_path}")
    except Exception as e:
        console.print(f"[bold red]Erreur lors du renommage : {e}[/bold red]")
