from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
from rich.prompt import Prompt, Confirm
from rich.layout import Layout
from rich.live import Live
from rich.tree import Tree
from rich.markdown import Markdown
from rich.syntax import Syntax
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable
import os
import json
import contextlib

class Theme:
    """Gestionnaire de thèmes pour l'interface utilisateur."""
    
    DEFAULT = {
        'primary': 'blue',
        'secondary': 'cyan',
        'success': 'green',
        'warning': 'yellow',
        'error': 'red',
        'info': 'white',
        'muted': 'grey70',
        'highlight': 'magenta',
        'code': 'yellow',
        'link': 'blue underline'
    }
    
    DARK = {
        'primary': 'purple',
        'secondary': 'blue',
        'success': 'green',
        'warning': 'yellow',
        'error': 'red',
        'info': 'grey',
        'muted': 'grey50',
        'highlight': 'pink',
        'code': 'orange1',
        'link': 'cyan underline'
    }
    
    @classmethod
    def get_theme(cls, name: str) -> dict:
        """Récupère un thème par son nom."""
        return getattr(cls, name.upper(), cls.DEFAULT)

class UIManager:
    """Gestionnaire d'interface utilisateur avancé."""
    
    def __init__(self):
        """Initialise le gestionnaire d'interface."""
        self.console = Console()
        self.status = self._init_status()
        self.notifications = []
        self.current_theme = Theme.get_theme('default')
        self._progress_bars = {}
        self._active_layout = None
        self._callbacks = {
            'on_error': [],
            'on_success': [],
            'on_warning': [],
            'on_progress': []
        }
    
    def _init_status(self) -> dict:
        """Initialise l'état du gestionnaire."""
        return {
            'last_operation': None,
            'files_processed': 0,
            'errors': 0,
            'warnings': 0,
            'space_saved': 0,
            'start_time': None,
            'last_update': None
        }
    
    def set_theme(self, theme_name: str) -> None:
        """Change le thème de l'interface."""
        self.current_theme = Theme.get_theme(theme_name)
        self.show_info(f"Thème changé pour : {theme_name}")
    
    def register_callback(self, event: str, callback: Callable) -> None:
        """Enregistre une fonction de rappel pour un événement."""
        if event in self._callbacks:
            self._callbacks[event].append(callback)
    
    def _trigger_callbacks(self, event: str, *args, **kwargs) -> None:
        """Déclenche les callbacks pour un événement."""
        for callback in self._callbacks.get(event, []):
            try:
                callback(*args, **kwargs)
            except Exception as e:
                self.show_error(f"Erreur dans le callback {callback.__name__}: {str(e)}")
    
    @contextlib.contextmanager
    def create_layout(self, title: str = None) -> Layout:
        """Crée un layout temporaire pour organiser l'affichage."""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )
        
        if title:
            layout["header"].update(Panel(
                f"[bold {self.current_theme['primary']}]{title}[/bold {self.current_theme['primary']}]",
                border_style=self.current_theme['secondary']
            ))
        
        self._active_layout = layout
        with Live(layout, console=self.console, refresh_per_second=4):
            yield layout
        self._active_layout = None
    
    def format_size(self, size_bytes: float) -> str:
        """Formate une taille en bytes en une chaîne lisible."""
        for unit in ['o', 'Ko', 'Mo', 'Go', 'To']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} Po"
    
    def format_duration(self, seconds: float) -> str:
        """Formate une durée en secondes en une chaîne lisible."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60
        if hours > 0:
            return f"{hours}h {minutes}m {seconds:.1f}s"
        elif minutes > 0:
            return f"{minutes}m {seconds:.1f}s"
        return f"{seconds:.1f}s"
    
    def show_header(self, title: str, subtitle: str = None):
        """Affiche un en-tête stylisé avec sous-titre optionnel."""
        width = self.console.width - 4
        self.console.print()
        self.console.print(f"[bold {self.current_theme['primary']}]{'═' * width}[/]")
        self.console.print(f"[bold {self.current_theme['primary']}]{title.center(width)}[/]")
        if subtitle:
            self.console.print(f"[{self.current_theme['secondary']}]{subtitle.center(width)}[/]")
        self.console.print(f"[bold {self.current_theme['primary']}]{'═' * width}[/]")
        self.console.print()
    
    def show_status_bar(self):
        """Affiche la barre d'état avec les informations actuelles."""
        if not self.status['start_time']:
            return
            
        elapsed = datetime.now() - self.status['start_time']
        status_text = [
            f"[{self.current_theme['primary']}]Opération[/] : {self.status['last_operation']}",
            f"[{self.current_theme['info']}]Fichiers[/] : {self.status['files_processed']}",
            f"[{self.current_theme['error']}]Erreurs[/] : {self.status['errors']}",
            f"[{self.current_theme['warning']}]Avertissements[/] : {self.status['warnings']}",
            f"[{self.current_theme['success']}]Espace économisé[/] : {self.format_size(self.status['space_saved'])}",
            f"[{self.current_theme['muted']}]Temps écoulé[/] : {self.format_duration(elapsed.total_seconds())}"
        ]
        
        panel = Panel(
            "\n".join(status_text),
            title="État du système",
            border_style=self.current_theme['primary'],
            padding=(1, 2)
        )
        
        if self._active_layout:
            self._active_layout["footer"].update(panel)
        else:
            self.console.print(panel)
    
    def update_status(self, **kwargs):
        """Met à jour le statut avec les nouvelles valeurs."""
        self.status.update(kwargs)
        self.status['last_update'] = datetime.now()
        self.show_status_bar()
        self._trigger_callbacks('on_progress', self.status)
    
    @contextlib.contextmanager
    def show_progress(self, total: int, description: str = "Progression") -> Progress:
        """Crée et gère une barre de progression stylisée."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn(f"[{self.current_theme['primary']}]" + "{task.description}"),
            BarColumn(complete_style=self.current_theme['primary']),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=self.console
        )
        
        task_id = progress.add_task(description, total=total)
        
        try:
            with progress:
                yield progress, task_id
        finally:
            if not progress.finished:
                progress.update(task_id, completed=total)
    
    def show_tree(self, data: Dict[str, Any], title: str = None) -> None:
        """Affiche une structure de données sous forme d'arbre."""
        def build_tree(tree: Tree, data: Dict[str, Any]) -> None:
            for key, value in data.items():
                if isinstance(value, dict):
                    branch = tree.add(f"[{self.current_theme['primary']}]{key}[/]")
                    build_tree(branch, value)
                else:
                    tree.add(f"[{self.current_theme['muted']}]{key}:[/] {value}")
        
        tree = Tree(
            f"[bold {self.current_theme['primary']}]{title or 'Structure'}[/]",
            guide_style=self.current_theme['secondary']
        )
        build_tree(tree, data)
        self.console.print(tree)
    
    def show_code(self, code: str, language: str = "python") -> None:
        """Affiche du code avec coloration syntaxique."""
        syntax = Syntax(code, language, theme="monokai", line_numbers=True)
        self.console.print(syntax)
    
    def show_markdown(self, text: str) -> None:
        """Affiche du texte formaté en Markdown."""
        markdown = Markdown(text)
        self.console.print(markdown)
    
    def show_error(self, message: str):
        """Affiche un message d'erreur."""
        self.console.print(f"[bold {self.current_theme['error']}]✗ Erreur : {message}[/]")
        self._trigger_callbacks('on_error', message)
    
    def show_warning(self, message: str):
        """Affiche un avertissement."""
        self.console.print(f"[bold {self.current_theme['warning']}]⚠ Attention : {message}[/]")
        self._trigger_callbacks('on_warning', message)
    
    def show_info(self, message: str):
        """Affiche un message d'information."""
        self.console.print(f"[{self.current_theme['info']}]ℹ {message}[/]")
    
    def show_success(self, message: str):
        """Affiche un message de succès."""
        self.console.print(f"[bold {self.current_theme['success']}]✓ {message}[/]")
        self._trigger_callbacks('on_success', message)
    
    def confirm_action(self, message: str, default: bool = False) -> bool:
        """Demande une confirmation à l'utilisateur."""
        styled_message = f"[{self.current_theme['primary']}]{message}[/]"
        return Confirm.ask(styled_message, default=default)
    
    def prompt_input(self, message: str, default: str = None, password: bool = False) -> str:
        """Demande une entrée à l'utilisateur."""
        styled_message = f"[{self.current_theme['primary']}]{message}[/]"
        return Prompt.ask(styled_message, default=default, password=password)
    
    def show_file_comparison(self, original: dict, converted: dict):
        """Affiche une comparaison entre deux versions d'un fichier."""
        table = Table(
            show_header=True,
            header_style=f"bold {self.current_theme['primary']}",
            border_style=self.current_theme['secondary'],
            padding=(0, 2)
        )
        
        table.add_column("Propriété", style=self.current_theme['muted'])
        table.add_column("Original", style=self.current_theme['info'])
        table.add_column("Converti", style=self.current_theme['info'])
        table.add_column("Différence", style=self.current_theme['highlight'])

        def format_diff(orig_val: Any, conv_val: Any) -> str:
            if isinstance(orig_val, (int, float)) and isinstance(conv_val, (int, float)):
                diff = conv_val - orig_val
                if diff > 0:
                    return f"[{self.current_theme['error']}]+{diff}[/]"
                elif diff < 0:
                    return f"[{self.current_theme['success']}]{diff}[/]"
            return ""

        comparisons = [
            ("Taille", self.format_size(original.get('size', 0)), 
             self.format_size(converted.get('size', 0)),
             format_diff(original.get('size', 0), converted.get('size', 0))),
            ("Durée", self.format_duration(original.get('duration', 0)),
             self.format_duration(converted.get('duration', 0)),
             format_diff(original.get('duration', 0), converted.get('duration', 0))),
            ("Résolution", original.get('resolution', 'N/A'),
             converted.get('resolution', 'N/A'), ""),
            ("FPS", str(original.get('fps', 'N/A')),
             str(converted.get('fps', 'N/A')),
             format_diff(original.get('fps', 0), converted.get('fps', 0))),
            ("Bitrate", original.get('bitrate', 'N/A'),
             converted.get('bitrate', 'N/A'), ""),
            ("Codec", original.get('codec', 'N/A'),
             converted.get('codec', 'N/A'), "")
        ]

        for prop, orig, conv, diff in comparisons:
            table.add_row(prop, orig, conv, diff)

        self.console.print(f"\n[bold {self.current_theme['secondary']}]Comparaison des fichiers[/]")
        self.console.print(table)

        if 'size' in original and 'size' in converted:
            saved = original['size'] - converted['size']
            if saved > 0:
                percent = (saved / original['size']) * 100
                self.show_success(
                    f"Espace économisé : {self.format_size(saved)} ({percent:.1f}%)"
                )
    
    def show_operation_summary(self):
        """Affiche un résumé de l'opération en cours."""
        if not self.status['start_time']:
            return

        elapsed = datetime.now() - self.status['start_time']
        success_rate = ((self.status['files_processed'] - self.status['errors']) / 
                       self.status['files_processed'] * 100) if self.status['files_processed'] > 0 else 0

        summary = {
            'Opération': self.status['last_operation'],
            'Durée totale': self.format_duration(elapsed.total_seconds()),
            'Statistiques': {
                'Fichiers traités': self.status['files_processed'],
                'Succès': f"{success_rate:.1f}%",
                'Erreurs': self.status['errors'],
                'Avertissements': self.status['warnings']
            },
            'Performances': {
                'Espace économisé': self.format_size(self.status['space_saved']),
                'Moyenne par fichier': self.format_size(
                    self.status['space_saved'] / self.status['files_processed']
                    if self.status['files_processed'] > 0 else 0
                )
            }
        }

        self.show_tree(summary, "Résumé de l'opération")

# Instance globale du gestionnaire d'interface
ui = UIManager()
