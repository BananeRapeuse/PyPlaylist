import os
import sys

# Chemins
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
dll_path = os.path.join(BASE_DIR, "mpv")
os.environ["PATH"] = dll_path + os.pathsep + os.environ["PATH"]
PLAYLISTS_DIR = os.path.join(BASE_DIR, "playlists")
MPV_PATH = os.path.join(BASE_DIR, "mpv", "mpv.exe")
THUMBNAIL_DIR = os.path.join(BASE_DIR, "contents", "PNGs", "thumbnails")
DEFAULT_THUMBNAIL = os.path.join(BASE_DIR, "contents", "PNGs", "blank_t.png")

import subprocess
import tkinter as tk
from tkinter import simpledialog, messagebox, filedialog
from PIL import Image, ImageTk
import mpv
import threading
import time
import random

# Création des dossiers si manquants
os.makedirs(PLAYLISTS_DIR, exist_ok=True)
os.makedirs(THUMBNAIL_DIR, exist_ok=True)

def get_window_size(sw, sh):
    if sw <= 1920:
        return 1280, 720
    elif sw <= 2560:
        return 1920, 1080
    elif sw <= 3840:
        return 2560, 1440
    elif sw <= 7680:
        return 3840, 2160
    else:
        return 7680, 4320

class PyPlaylistApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PyPlaylist 🎵")
        self.root.configure(bg="white")

        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        ww, wh = get_window_size(sw, sh)
        self.root.geometry(f"{ww}x{wh}")
        self.root.minsize(720, 480)

        # Variables pour le thème
        self.current_theme = "light"  # Thème par défaut
        self.bg_color = "white"
        self.text_color = "black"

        self.thumbnail_cache = {}
        self.playlist_frame = tk.Frame(root, bg=self.bg_color)
        self.playlist_frame.pack(fill=tk.BOTH, expand=True)
        self.load_playlists()

        self.player = mpv.MPV(input_default_bindings=True, input_vo_keyboard=True)
        self.current_playlist_path = None
        self.music_list = []
        self.current_index = 0
        self.is_paused = False
        self.progress_label = None
        self.current_song_label = None
        self.current_music_path = None

        # Ajout du bouton pour changer le thème
        self.theme_button = tk.Button(self.playlist_frame, text="Changer de thème", command=self.toggle_theme)
        self.theme_button.pack(pady=10)

    def load_thumbnail(self, playlist_name):
        path = os.path.join(THUMBNAIL_DIR, f"{playlist_name}.png")
        if not os.path.exists(path):
            path = DEFAULT_THUMBNAIL
        img = Image.open(path).resize((160, 160))
        return ImageTk.PhotoImage(img)

    def load_playlists(self):
        for widget in self.playlist_frame.winfo_children():
            widget.destroy()

        header = tk.Label(self.playlist_frame, text="🎵 Vos Playlists", font=("Arial", 18), bg=self.bg_color, fg=self.text_color)
        header.pack(pady=20)

        grid_frame = tk.Frame(self.playlist_frame, bg=self.bg_color)
        grid_frame.pack(pady=10)

        playlists = [d for d in os.listdir(PLAYLISTS_DIR) if os.path.isdir(os.path.join(PLAYLISTS_DIR, d))]

        columns = 4
        for i, playlist in enumerate(playlists):
            row = i // columns
            col = i % columns

            frame = tk.Frame(grid_frame, bg=self.bg_color, padx=15, pady=15)
            frame.grid(row=row, column=col)

            img = self.load_thumbnail(playlist)
            self.thumbnail_cache[playlist] = img

            btn = tk.Button(frame, image=img, bd=0, bg=self.bg_color, activebackground=self.bg_color,
                            command=lambda name=playlist: self.open_playlist(name))
            btn.pack()
            btn.bind("<Button-3>", lambda e, name=playlist: self.show_context_menu(e, name))

            label = tk.Label(frame, text=playlist, font=("Arial", 12), bg=self.bg_color, fg=self.text_color)
            label.pack()

        add_btn = tk.Button(self.playlist_frame, text="+ Nouvelle Playlist", font=("Arial", 14),
                            command=self.create_playlist, bg="#e0e0e0")
        add_btn.pack(pady=20)

    def create_playlist(self):
        name = simpledialog.askstring("Nouvelle Playlist", "Nom de la playlist :")
        if not name:
            return
        playlist_path = os.path.join(PLAYLISTS_DIR, name)
        if os.path.exists(playlist_path):
            messagebox.showerror("Erreur", "Cette playlist existe déjà.")
            return
        os.makedirs(playlist_path)

        img_path = filedialog.askopenfilename(title="Choisir une miniature (512x512 PNG)", filetypes=[("PNG", "*.png")])
        if img_path:
            try:
                with Image.open(img_path) as img:
                    if img.size != (512, 512):
                        raise ValueError("L'image doit faire 512x512")
                    dest = os.path.join(THUMBNAIL_DIR, f"{name}.png")
                    img.save(dest)
            except Exception as e:
                messagebox.showwarning("Miniature invalide", f"Erreur miniature : {e}\nUtilisation de la miniature par défaut.")
        else:
            default = os.path.join(THUMBNAIL_DIR, f"{name}.png")
            Image.open(DEFAULT_THUMBNAIL).save(default)

        self.load_playlists()

    def show_context_menu(self, event, playlist_name):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Changer la miniature", command=lambda: self.change_thumbnail(playlist_name))
        menu.add_command(label="Supprimer la playlist", command=lambda: self.delete_playlist(playlist_name))
        menu.tk_popup(event.x_root, event.y_root)

    def change_thumbnail(self, playlist_name):
        path = filedialog.askopenfilename(title="Nouvelle miniature (512x512 PNG)", filetypes=[("PNG", "*.png")])
        if path:
            try:
                with Image.open(path) as img:
                    if img.size != (512, 512):
                        raise ValueError("L'image doit faire 512x512 pixels")
                    dest = os.path.join(THUMBNAIL_DIR, f"{playlist_name}.png")
                    img.save(dest)
                    self.load_playlists()
            except Exception as e:
                messagebox.showerror("Erreur miniature", f"Impossible de changer l'image : {e}")

    def delete_playlist(self, playlist_name):
        if messagebox.askyesno("Supprimer", f"Supprimer la playlist '{playlist_name}' ?"):
            import shutil
            shutil.rmtree(os.path.join(PLAYLISTS_DIR, playlist_name), ignore_errors=True)
            thumb = os.path.join(THUMBNAIL_DIR, f"{playlist_name}.png")
            if os.path.exists(thumb):
                os.remove(thumb)
            self.load_playlists()

    def open_playlist(self, playlist_name):
        self.playlist_frame.pack_forget()
        self.music_frame = tk.Frame(self.root, bg=self.bg_color)
        self.music_frame.pack(fill=tk.BOTH, expand=True)

        back_btn = tk.Button(self.music_frame, text="← Retour", command=self.back_to_playlists,
                             bg=self.bg_color, font=("Arial", 12))
        back_btn.pack(anchor="w", padx=10, pady=10)

        label = tk.Label(self.music_frame, text=f"Playlist : {playlist_name}", font=("Arial", 16), bg=self.bg_color, fg=self.text_color)
        label.pack()

        self.current_song_label = tk.Label(self.music_frame, text="", font=("Arial", 12), bg=self.bg_color, fg=self.text_color)
        self.current_song_label.pack(pady=5)

        self.progress_label = tk.Label(self.music_frame, text="00:00 / 00:00", font=("Arial", 10), bg=self.bg_color, fg=self.text_color)
        self.progress_label.pack(pady=2)

        controls = tk.Frame(self.music_frame, bg=self.bg_color)
        controls.pack(pady=5)
        tk.Button(controls, text="⏮", command=self.play_previous).pack(side=tk.LEFT, padx=5)
        self.pause_btn = tk.Button(controls, text="⏸", command=self.toggle_pause)
        self.pause_btn.pack(side=tk.LEFT, padx=5)
        tk.Button(controls, text="⏭", command=self.play_next).pack(side=tk.LEFT, padx=5)
        tk.Button(controls, text="🔀", command=self.shuffle_play).pack(side=tk.LEFT, padx=5)

        # Ajouter un contrôleur de volume
        volume_frame = tk.Frame(self.music_frame, bg=self.bg_color)
        volume_frame.pack(pady=10)

        volume_label = tk.Label(volume_frame, text="Volume", bg=self.bg_color, fg=self.text_color)
        volume_label.pack(side=tk.LEFT, padx=5)

        self.volume_scale = tk.Scale(volume_frame, from_=0, to_=100, orient=tk.HORIZONTAL, bg=self.bg_color, command=self.set_volume)
        self.volume_scale.set(50)  # Volume initial à 50%
        self.volume_scale.pack(side=tk.LEFT)

        self.music_listbox = tk.Listbox(self.music_frame, font=("Arial", 12), selectbackground="#d0d0d0")
        self.music_listbox.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self.current_playlist_path = os.path.join(PLAYLISTS_DIR, playlist_name)
        self.music_list = [f for f in os.listdir(self.current_playlist_path) if f.endswith(".mp3")]

        for music in self.music_list:
            self.music_listbox.insert(tk.END, music)

        self.music_listbox.bind("<<ListboxSelect>>", self.on_select_music)

    def set_volume(self, volume):
        """Met à jour le volume du lecteur mpv."""
        volume = int(volume)
        self.player.volume = volume

    def on_select_music(self, event):
        selection = self.music_listbox.curselection()
        if selection:
            self.current_index = selection[0]
            song = self.music_list[self.current_index]
            full_path = os.path.join(self.current_playlist_path, song)
            self.play_music(full_path)

    def play_music(self, path):
        if not os.path.exists(path):
            messagebox.showerror("Erreur", "Fichier introuvable.")
            return

        # Lancer la musique sans observer l'événement end-file
        self.player.stop()
        self.player.play(path)
        self.current_music_path = path

        self.current_song_label.config(text=os.path.basename(path))
        self.is_paused = False
        self.pause_btn.config(text="⏸")
        
        # Mise à jour de la progression dans un thread
        self.update_progress()

    def play_next(self):
        if self.music_list:
            self.current_index += 1
            if self.current_index >= len(self.music_list):
                self.current_index = 0
            next_song = self.music_list[self.current_index]
            next_path = os.path.join(self.current_playlist_path, next_song)
            self.play_music(next_path)

    def play_previous(self):
        if self.music_list:
            self.current_index -= 1
            if self.current_index < 0:
                self.current_index = len(self.music_list) - 1
            prev_song = self.music_list[self.current_index]
            prev_path = os.path.join(self.current_playlist_path, prev_song)
            self.play_music(prev_path)

    def toggle_pause(self):
        if self.player:
            self.is_paused = not self.is_paused
            self.player.pause = self.is_paused
            self.pause_btn.config(text="▶" if self.is_paused else "⏸")

    def shuffle_play(self):
        if self.music_list:
            self.current_index = random.randint(0, len(self.music_list) - 1)
            song = self.music_list[self.current_index]
            full_path = os.path.join(self.current_playlist_path, song)
            self.play_music(full_path)

    def update_progress(self):
        """Met à jour la progression du temps de manière synchrone avec l'interface graphique."""
        def update():
            current = self.player.playback_time
            duration = self.player.duration
            if current is not None and duration is not None:
                self.progress_label.config(text=f"{self.format_time(int(current))} / {self.format_time(int(duration))}")
            self.root.after(1000, update)  # Mettre à jour chaque seconde

        update()

    def format_time(self, seconds):
        m, s = divmod(seconds, 60)
        return f"{int(m):02}:{int(s):02}"

    def back_to_playlists(self):
        self.music_frame.pack_forget()
        self.playlist_frame.pack(fill=tk.BOTH, expand=True)
        self.load_playlists()

    def toggle_theme(self):
        """Bascule entre le thème clair et sombre."""
        if self.current_theme == "light":
            self.current_theme = "dark"
        else:
            self.current_theme = "light"

        self.update_theme()

    def update_theme(self):
        """Met à jour les couleurs de l'interface en fonction du thème."""
        if self.current_theme == "light":
            self.bg_color = "white"
            self.text_color = "black"
        elif self.current_theme == "dark":
            self.bg_color = "#1c1c18"
            self.text_color = "white"

        # Mise à jour du fond de la fenêtre principale
        self.root.configure(bg=self.bg_color)

        # Mise à jour des couleurs dans toutes les parties de l'application
        self.playlist_frame.configure(bg=self.bg_color)
        self.load_playlists()


if __name__ == "__main__":
    root = tk.Tk()
    app = PyPlaylistApp(root)
    root.mainloop()
