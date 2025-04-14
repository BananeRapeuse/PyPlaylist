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

# Liste des formats audio supportés
SUPPORTED_AUDIO_FORMATS = [
    ".mp3", ".aac", ".ogg", ".oga", ".flac", ".wav", ".alac", 
    ".opus", ".wma", ".m4a", ".aiff", ".pcm", ".ape", ".tta", 
    ".dsf", ".dff", ".mpc", ".amr"
]

import subprocess
import tkinter as tk
from tkinter import simpledialog, messagebox, filedialog
from PIL import Image, ImageTk
import mpv
import threading
import time
import random
# Importer pypresence pour Discord Rich Presence
try:
    from pypresence import Presence
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False
    print("Module pypresence non trouvé. L'intégration Discord ne sera pas disponible.")

# Création des dossiers si manquants
os.makedirs(PLAYLISTS_DIR, exist_ok=True)
os.makedirs(THUMBNAIL_DIR, exist_ok=True)

# ID d'application Discord (vous devrez créer votre propre application Discord)
# Remplacez cette valeur par votre propre ID client Discord
DISCORD_CLIENT_ID = "1361395271183106248"

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
        
        # On crée d'abord le bouton de thème avant d'appeler load_playlists
        self.theme_button = None
        
        # Drapeau pour contrôler l'auto-play
        self.skip_next_auto_play = False
        
        # Initialiser le lecteur MPV avec un gestionnaire d'événements pour la fin du fichier
        self.player = mpv.MPV(input_default_bindings=True, input_vo_keyboard=True)
        
        # Ajouter un écouteur d'événement pour détecter la fin du fichier
        @self.player.event_callback('end-file')
        def on_end_file(event):
            if not self.skip_next_auto_play:
                # Assurer que nous sommes dans le thread principal
                self.root.after(100, self.auto_play_next)
            else:
                # Réinitialiser le drapeau après l'avoir utilisé
                self.skip_next_auto_play = False
        
        self.current_playlist_path = None
        self.music_list = []
        self.current_index = 0
        self.is_paused = False
        self.progress_label = None
        self.current_song_label = None
        self.current_music_path = None
        
        # Initialisation de Discord Rich Presence
        self.discord_rpc = None
        self.init_discord()
        
        # Variable pour stocker le statut Discord actuel
        self.current_discord_status = None
        
        # Charger les playlists
        self.load_playlists()
        
        # S'assurer que le statut Discord est effacé à la fermeture
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def init_discord(self):
        """Initialise la connexion avec Discord Rich Presence"""
        if not DISCORD_AVAILABLE:
            return
            
        try:
            self.discord_rpc = Presence(DISCORD_CLIENT_ID)
            self.discord_rpc.connect()
            print("Connecté à Discord Rich Presence")
        except Exception as e:
            print(f"Erreur lors de la connexion à Discord: {e}")
            self.discord_rpc = None

    def update_discord_presence(self, song_name=None, playlist_name=None, is_paused=False):
        """Met à jour le statut Discord Rich Presence"""
        if not self.discord_rpc:
            return
            
        try:
            if song_name:
                # Enlever l'extension si présente
                file_name, file_ext = os.path.splitext(song_name)
                if file_ext.lower() in SUPPORTED_AUDIO_FORMATS:
                    song_name = file_name
                    
                state = f"En pause" if is_paused else f"Écoute"
                details = f"PyPlaylist | {song_name}"
                
                if playlist_name:
                    state += f" - Playlist: {playlist_name}"
                
                # Mise à jour du statut Discord
                self.discord_rpc.update(
                    state=state,
                    details=details,
                    large_image="music",  # Clé d'une image téléchargée dans votre application Discord
                    large_text="PyPlaylist",
                    start=int(time.time()) if not is_paused else None  # Temps écoulé si pas en pause
                )
                self.current_discord_status = song_name
            else:
                # Effacer le statut quand aucune musique n'est jouée
                self.discord_rpc.clear()
                self.current_discord_status = None
        except Exception as e:
            print(f"Erreur lors de la mise à jour du statut Discord: {e}")

    def load_thumbnail(self, playlist_name):
        path = os.path.join(THUMBNAIL_DIR, f"{playlist_name}.png")
        if not os.path.exists(path):
            path = DEFAULT_THUMBNAIL
        img = Image.open(path).resize((160, 160))
        return ImageTk.PhotoImage(img)

    def load_playlists(self):
        # Sauvegarde le bouton de thème s'il existe déjà
        keep_theme_button = self.theme_button
        
        # Supprimer tous les widgets existants
        for widget in self.playlist_frame.winfo_children():
            widget.destroy()

        header = tk.Label(self.playlist_frame, text="🎵 Vos Playlists", font=("Arial", 18), bg=self.bg_color, fg=self.text_color)
        header.pack(pady=20)
        
        # Recréer le bouton de thème
        self.theme_button = tk.Button(self.playlist_frame, text="Changer de thème", command=self.toggle_theme)
        self.theme_button.pack(pady=10)

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
        menu.add_command(label="Ajouter des musiques", command=lambda: self.add_music_to_playlist(playlist_name))
        menu.add_command(label="Changer la miniature", command=lambda: self.change_thumbnail(playlist_name))
        menu.add_command(label="Supprimer la playlist", command=lambda: self.delete_playlist(playlist_name))
        menu.tk_popup(event.x_root, event.y_root)

    def add_music_to_playlist(self, playlist_name):
        playlist_path = os.path.join(PLAYLISTS_DIR, playlist_name)
        
        # Construire le filtre pour la boîte de dialogue de sélection de fichiers
        filetypes = []
        for ext in SUPPORTED_AUDIO_FORMATS:
            desc = f"{ext.upper()[1:]} Audio"
            filetypes.append((desc, f"*{ext}"))
        
        # Ajouter une option "Tous les fichiers audio"
        all_formats = " ".join(f"*{ext}" for ext in SUPPORTED_AUDIO_FORMATS)
        filetypes.insert(0, ("Tous les fichiers audio", all_formats))
        
        # Ouvrir la boîte de dialogue pour sélectionner les fichiers
        files = filedialog.askopenfilenames(
            title="Ajouter des musiques à la playlist",
            filetypes=filetypes
        )
        
        if not files:
            return
        
        # Copier les fichiers sélectionnés dans le dossier de la playlist
        for file_path in files:
            file_name = os.path.basename(file_path)
            dest_path = os.path.join(playlist_path, file_name)
            
            if os.path.exists(dest_path):
                if not messagebox.askyesno("Fichier existant", 
                    f"Le fichier {file_name} existe déjà dans la playlist.\nVoulez-vous le remplacer?"):
                    continue
            
            try:
                import shutil
                shutil.copy2(file_path, dest_path)
            except Exception as e:
                messagebox.showerror("Erreur", f"Impossible d'ajouter {file_name}: {e}")
        
        # Si la playlist est actuellement ouverte, mettre à jour la liste
        if hasattr(self, 'current_playlist_path') and self.current_playlist_path == playlist_path:
            self.update_music_list()

    def update_music_list(self):
        if not hasattr(self, 'music_listbox'):
            return
            
        # Sauvegarder la sélection actuelle
        current_selection = self.music_listbox.curselection()
        
        # Vider et reconstruire la liste
        self.music_listbox.delete(0, tk.END)
        self.music_list = []
        
        # Obtenir tous les fichiers audio dans le dossier
        for file in os.listdir(self.current_playlist_path):
            ext = os.path.splitext(file)[1].lower()
            if ext in SUPPORTED_AUDIO_FORMATS:
                self.music_list.append(file)
        
        # Trier la liste alphabétiquement
        self.music_list.sort()
        
        # Remplir la listbox
        for music in self.music_list:
            self.music_listbox.insert(tk.END, music)
        
        # Restaurer la sélection si possible
        if current_selection and current_selection[0] < len(self.music_list):
            self.music_listbox.selection_set(current_selection[0])

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

        # Ajout de la case à cocher pour l'intégration Discord
        if DISCORD_AVAILABLE:
            self.discord_var = tk.IntVar(value=1)  # Activé par défaut
            discord_check = tk.Checkbutton(self.music_frame, text="Afficher sur Discord", 
                                          variable=self.discord_var, bg=self.bg_color, fg=self.text_color,
                                          activebackground=self.bg_color)
            discord_check.pack(pady=5)

        self.music_listbox = tk.Listbox(self.music_frame, font=("Arial", 12), selectbackground="#d0d0d0")
        self.music_listbox.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self.current_playlist_path = os.path.join(PLAYLISTS_DIR, playlist_name)
        self.music_list = []
        
        # Récupérer tous les fichiers audio reconnus
        for file in os.listdir(self.current_playlist_path):
            ext = os.path.splitext(file)[1].lower()
            if ext in SUPPORTED_AUDIO_FORMATS:
                self.music_list.append(file)
        
        # Trier la liste
        self.music_list.sort()

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

        # Lancer la musique
        self.player.stop()
        self.player.play(path)
        self.current_music_path = path
        
        song_name = os.path.basename(path)
        playlist_name = os.path.basename(self.current_playlist_path)
        
        self.current_song_label.config(text=song_name)
        self.is_paused = False
        self.pause_btn.config(text="⏸")
        
        # Mise à jour du statut Discord si activé
        if hasattr(self, 'discord_var') and self.discord_var.get() == 1 and DISCORD_AVAILABLE:
            self.update_discord_presence(song_name, playlist_name, is_paused=False)
        
        # Mise à jour de la progression dans un thread
        self.update_progress()
        
        # Sélectionner visuellement la piste courante dans la liste
        self.music_listbox.selection_clear(0, tk.END)
        self.music_listbox.selection_set(self.current_index)
        self.music_listbox.see(self.current_index)

    def auto_play_next(self):
        """Cette méthode est appelée automatiquement lorsqu'une chanson se termine"""
        if not self.music_list:
            return
            
        self.current_index += 1
        if self.current_index >= len(self.music_list):
            self.current_index = 0
            
        next_song = self.music_list[self.current_index]
        next_path = os.path.join(self.current_playlist_path, next_song)
        self.play_music(next_path)

    def play_next(self):
        """Cette méthode est appelée lorsque l'utilisateur clique sur le bouton suivant"""
        if not self.music_list:
            return
           
        # Activer le drapeau pour empêcher l'auto-play
        self.skip_next_auto_play = True
        
        # Passer à l'index suivant
        self.current_index += 1
        if self.current_index >= len(self.music_list):
            self.current_index = 0
            
        next_song = self.music_list[self.current_index]
        next_path = os.path.join(self.current_playlist_path, next_song)
        
        # Jouer le nouveau morceau
        self.play_music(next_path)

    def play_previous(self):
        if not self.music_list:
            return
            
        # Activer le drapeau pour empêcher l'auto-play
        self.skip_next_auto_play = True
        
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
            
            # Mettre à jour le statut Discord pour indiquer la pause
            if hasattr(self, 'discord_var') and self.discord_var.get() == 1 and DISCORD_AVAILABLE and self.current_music_path:
                song_name = os.path.basename(self.current_music_path)
                playlist_name = os.path.basename(self.current_playlist_path)
                self.update_discord_presence(song_name, playlist_name, is_paused=self.is_paused)

    def shuffle_play(self):
        if not self.music_list:
            return
            
        # Activer le drapeau pour empêcher l'auto-play
        self.skip_next_auto_play = True
        
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
        # Arrêter la musique et effacer le statut Discord
        self.player.stop()
        if DISCORD_AVAILABLE and self.discord_rpc:
            self.update_discord_presence(None)
            
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
        
        # Mettre à jour le thème en rechargeant les playlists
        self.load_playlists()
        
    def on_close(self):
        """Méthode appelée lors de la fermeture de l'application"""
        # Effacer le statut Discord avant de fermer
        if DISCORD_AVAILABLE and self.discord_rpc:
            try:
                self.discord_rpc.clear()
                self.discord_rpc.close()
            except:
                pass
                
        self.root.destroy()


if __name__ == "__main__":
    # Vérifier si pypresence est installé, sinon proposer de l'installer
    if not DISCORD_AVAILABLE:
        try:
            response = messagebox.askyesno(
                "Module manquant", 
                "Le module 'pypresence' est nécessaire pour l'intégration Discord.\nVoulez-vous l'installer maintenant?"
            )
            if response:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "pypresence"])
                messagebox.showinfo("Installation réussie", "Le module a été installé. Veuillez redémarrer l'application.")
                sys.exit(0)
        except Exception as e:
            messagebox.showerror("Erreur d'installation", f"Impossible d'installer le module: {e}")
    
    root = tk.Tk()
    app = PyPlaylistApp(root)
    root.mainloop()