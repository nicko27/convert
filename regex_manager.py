import re
import os
from pathlib import Path
from rich.console import Console
from prompt_toolkit import prompt
from config_manager import load_json_data, save_json_data

console = Console()

def manage_regex_patterns_and_analyze(directory: str):
    """
    Gère les expressions régulières pour ajouter, supprimer, modifier, ou analyser les fichiers immédiatement
    avec une expression sélectionnée.
    """
    data = load_json_data()
    regex_patterns = data.get("regex_patterns", [])

    # Ensure regex_patterns is a list of dictionaries
    regex_patterns = [
        pattern if isinstance(pattern, dict) else {"pattern": pattern, "action": "d", "replace_with": " ", "position": "p", "allow_mid_word": "n"}
        for pattern in regex_patterns
    ]

    while True:
        console.print("[bold cyan]Gestion des expressions régulières :[/bold cyan]")
        console.print("1. Ajouter une expression régulière")
        console.print("2. Supprimer une expression régulière")
        console.print("3. Modifier une expression régulière")
        console.print("4. Appliquer toutes les expressions régulières sur les fichiers")
        console.print("5. Quitter")

        choice = prompt("Choisissez une option : ")

        if choice == "1":
            new_pattern = prompt("Entrez la nouvelle expression régulière : ")
            action = prompt("Entrez l'action ('d' pour supprimer, 'r' pour remplacer, 's' pour ajouter un espace) : ", default="d").lower()
            replace_with = prompt("Entrez le mot de remplacement (laisser vide pour un espace) : ") if action == "r" else ""
            position = prompt("Entrez la position ('d' pour début, 'f' pour fin, 'p' pour partout) : ", default="p").lower()
            allow_mid_word = prompt("Autoriser en milieu de mot ? (o pour oui, n pour non) : ", default="n").lower()

            regex_patterns.append({
                "pattern": new_pattern,
                "action": action,
                "replace_with": replace_with or " ",
                "position": position,
                "allow_mid_word": allow_mid_word
            })
            console.print("[bold green]Expression ajoutée ![/bold green]")

        elif choice == "2":
            for i, pattern_info in enumerate(regex_patterns, start=1):
                console.print(f"{i}. {pattern_info['pattern']}")
            idx = int(prompt("Entrez le numéro de l'expression à supprimer : ")) - 1
            if 0 <= idx < len(regex_patterns):
                console.print(f"[bold red]Expression supprimée :[/bold red] {regex_patterns[idx]['pattern']}")
                regex_patterns.pop(idx)

        elif choice == "3":
            for i, pattern_info in enumerate(regex_patterns, start=1):
                console.print(f"{i}. {pattern_info['pattern']}")
            idx = int(prompt("Entrez le numéro de l'expression à modifier : ")) - 1
            if 0 <= idx < len(regex_patterns):
                updated_pattern = prompt("Entrez la nouvelle expression : ")
                action = prompt("Entrez l'action ('d' pour supprimer, 'r' pour remplacer, 's' pour ajouter un espace) : ", default="d").lower()
                replace_with = prompt("Entrez le mot de remplacement (laisser vide pour un espace) : ") if action == "r" else ""
                position = prompt("Entrez la position ('d' pour début, 'f' pour fin, 'p' pour partout) : ", default="p").lower()
                allow_mid_word = prompt("Autoriser en milieu de mot ? (o pour oui, n pour non) : ", default="n").lower()

                regex_patterns[idx].update({
                    "pattern": updated_pattern,
                    "action": action,
                    "replace_with": replace_with or " ",
                    "position": position,
                    "allow_mid_word": allow_mid_word
                })
                console.print("[bold green]Expression modifiée ![/bold green]")

        elif choice == "4":
            auto_mode = prompt("Souhaitez-vous activer le mode automatique pour appliquer les actions sur les mots trouvés ? (o/n): ", default="o").lower() == 'o'
            apply_regex_to_files(directory, regex_patterns,auto_mode)

        elif choice == "5":
            break

        else:
            console.print("[bold red]Choix invalide. Veuillez réessayer.[/bold red]")

    data=load_json_data()
    data["regex_patterns"] = regex_patterns
    save_json_data(data)

def apply_regex_to_files(directory: str, regex_patterns: list, auto_mode: bool):
    """
    Applique les expressions régulières fournies pour modifier les noms de fichiers dans le répertoire.
    Sélectionne la regex qui réduit le plus la longueur du nom et continue jusqu'à ce qu'il n'y ait plus de réduction.
    
    :param directory: Le répertoire dans lequel appliquer les regex.
    :param regex_patterns: Liste de dictionnaires de regex avec action et paramètres.
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
            for pattern_info in regex_patterns:
                pattern = pattern_info.get("pattern", "")
                action = pattern_info.get("action", "d")
                replace_with = pattern_info.get("replace_with", " ")
                position = pattern_info.get("position", "p")
                allow_mid_word = pattern_info.get("allow_mid_word", "n") == "o"

                # Define the regex based on position and word boundary conditions
                if position == "d":
                    regex = rf"^{pattern}"
                elif position == "f":
                    regex = rf"{pattern}$"
                else:
                    regex = rf"\b{pattern}\b" if not allow_mid_word else pattern

                # Apply the pattern to see the effect
                if action == "d":
                    test_name = re.sub(regex, "", modified_name, flags=re.IGNORECASE).strip()
                elif action == "r":
                    test_name = re.sub(regex, replace_with, modified_name, flags=re.IGNORECASE).strip()
                elif action == "s":
                    test_name = re.sub(regex, f"{pattern} ", modified_name, flags=re.IGNORECASE).strip()
                
                reduction = len(modified_name) - len(test_name)

                # Choose the pattern that maximizes reduction
                if reduction > max_reduction:
                    max_reduction = reduction
                    best_match = (pattern_info, test_name)

            # If a reduction was made, apply it
            if best_match and len(best_match[1]) > 0:
                modified_name = best_match[1]
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
