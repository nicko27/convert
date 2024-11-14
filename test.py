import tkinter as tk
from tkinter import ttk, messagebox
from typing import List

# Simulations de fonctions de configuration
def get_video_formats() -> List[str]:
    return [".mp4", ".mkv", ".avi"]

def set_video_formats(formats: List[str]) -> None:
    messagebox.showinfo("Mise à jour", f"Formats vidéo mis à jour : {', '.join(formats)}")

def get_ignore_keyword() -> str:
    return "cvt"

def set_ignore_keyword(keyword: str) -> None:
    messagebox.showinfo("Mise à jour", f"Mot-clé d'ignorance mis à jour : {keyword}")

class VideoConfigApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Configuration de l'application")

        # Configurer la taille minimale de la fenêtre
        self.root.geometry("400x200")
        
        # S'assurer que la fenêtre principale s'adapte
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Menu principal
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")

        # Configurer le main_frame pour qu'il prenne tout l'espace
        main_frame.columnconfigure(0, weight=1)

        # Bouton pour modifier les formats vidéo
        video_format_button = ttk.Button(main_frame, text="Modifier les formats vidéo", command=self.open_video_format_window)
        video_format_button.grid(row=0, column=0, pady=5, padx=5, sticky="ew")

        # Bouton pour définir le mot-clé d'ignorance
        ignore_keyword_button = ttk.Button(main_frame, text="Définir le mot-clé d'ignorance", command=self.open_ignore_keyword_window)
        ignore_keyword_button.grid(row=1, column=0, pady=5, padx=5, sticky="ew")

    def open_video_format_window(self):
        """Ouvre une fenêtre pour modifier les formats vidéo."""
        window = tk.Toplevel(self.root)
        window.title("Formats vidéo")
        window.geometry("350x150")  # Taille de la sous-fenêtre
        
        current_formats_label = ttk.Label(window, text="Formats vidéo actuels :")
        current_formats_label.grid(row=0, column=0, sticky=tk.W)
        
        current_formats_text = tk.StringVar(value=", ".join(get_video_formats()))
        current_formats_entry = ttk.Entry(window, textvariable=current_formats_text, state="readonly")
        current_formats_entry.grid(row=0, column=1, sticky=(tk.W, tk.E))

        new_formats_label = ttk.Label(window, text="Nouveaux formats (séparés par des virgules) :")
        new_formats_label.grid(row=1, column=0, sticky=tk.W)
        
        new_formats_entry = ttk.Entry(window, width=30)
        new_formats_entry.grid(row=1, column=1, sticky=(tk.W, tk.E))

        update_button = ttk.Button(window, text="Mettre à jour", command=lambda: self.update_video_formats(new_formats_entry.get()))
        update_button.grid(row=2, column=1, sticky=tk.E)

    def update_video_formats(self, new_formats):
        updated_formats = [fmt.strip().lower() for fmt in new_formats.split(",") if fmt.strip()]
        set_video_formats(updated_formats)

    def open_ignore_keyword_window(self):
        """Ouvre une fenêtre pour modifier le mot-clé d'ignorance."""
        window = tk.Toplevel(self.root)
        window.title("Mot-clé d'ignorance")
        window.geometry("350x150")  # Taille de la sous-fenêtre

        current_keyword_label = ttk.Label(window, text="Mot-clé actuel d'ignorance :")
        current_keyword_label.grid(row=0, column=0, sticky=tk.W)
        
        current_keyword_text = tk.StringVar(value=get_ignore_keyword())
        current_keyword_entry = ttk.Entry(window, textvariable=current_keyword_text, state="readonly")
        current_keyword_entry.grid(row=0, column=1, sticky=(tk.W, tk.E))

        new_keyword_label = ttk.Label(window, text="Nouveau mot-clé :")
        new_keyword_label.grid(row=1, column=0, sticky=tk.W)
        
        new_keyword_entry = ttk.Entry(window, width=30)
        new_keyword_entry.grid(row=1, column=1, sticky=(tk.W, tk.E))

        update_button = ttk.Button(window, text="Mettre à jour", command=lambda: self.update_ignore_keyword(new_keyword_entry.get()))
        update_button.grid(row=2, column=1, sticky=tk.E)

    def update_ignore_keyword(self, new_keyword):
        set_ignore_keyword(new_keyword)

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoConfigApp(root)
    root.mainloop()
