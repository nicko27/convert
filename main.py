from rich.console import Console
from menu import display_menu

console = Console()

def main():
    console.print("[bold green]Bienvenue dans le gestionnaire de vidéos ![/bold green]")
    display_menu()

if __name__ == "__main__":
    main()
