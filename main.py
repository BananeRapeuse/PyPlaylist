import os
import subprocess
import tkinter as tk
from tkinter import simpledialog, messagebox, filedialog
from PIL import Image, ImageTk

# Chemins
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLAYLISTS_DIR = os.path.join(BASE_DIR, "playlists")
MPV_PATH = os.path.join(BASE_DIR, "mpv", "mpv.exe")
THUMBNAIL_DIR = os.path.join(BASE_DIR, "contents", "PNGs", "thumbnails")
DEFAULT_THUMBNAIL = os.path.join(BASE_DIR, "contents", "PNGs", "blank_t.png")

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

        self.thumbnail_cache = {}
        self.playlist_frame = tk.Frame(root, bg="white")
        self.playlist_frame.pack(fill=tk.BOTH, expand=True)
        self.load_playlists()

    def load_thumbnail(self, playlist_name):
        path = os.path.join(THUMBNAIL_DIR, f"{playlist_name}.png")
        if not os.path.exists(path):
            path = DEFAULT_THUMBNAIL
        img = Image.open(path).resize((160, 160))
        return ImageTk.PhotoImage(img)

    def load_playlists(self):
        for widget in self.playlist_frame.winfo_children():
            widget.destroy()

        header = tk.Label(self.playlist_frame, text="🎵 Vos Playlists", font=("Arial", 18), bg="white")
        header.pack(pady=20)

        grid_frame = tk.Frame(self.playlist_frame, bg="white")
        grid_frame.pack(pady=10)

        playlists = [d for d in os.listdir(PLAYLISTS_DIR) if os.path.isdir(os.path.join(PLAYLISTS_DIR, d))]

        columns = 4
        for i, playlist in enumerate(playlists):
            row = i // columns
            col = i % columns

            frame = tk.Frame(grid_frame, bg="white", padx=15, pady=15)
            frame.grid(row=row, column=col)

            img = self.load_thumbnail(playlist)
            self.thumbnail_cache[playlist] = img  # éviter que l'image soit garbage collected

            btn = tk.Button(frame, image=img, bd=0, bg="white", activebackground="white",
                            command=lambda name=playlist: self.open_playlist(name))
            btn.pack()
            btn.bind("<Button-3>", lambda e, name=playlist: self.show_context_menu(e, name))

            label = tk.Label(frame, text=playlist, font=("Arial", 12), bg="white")
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
            # copier blank par défaut
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
        self.music_frame = tk.Frame(self.root, bg="white")
        self.music_frame.pack(fill=tk.BOTH, expand=True)

        back_btn = tk.Button(self.music_frame, text="← Retour", command=self.back_to_playlists,
                             bg="white", font=("Arial", 12))
        back_btn.pack(anchor="w", padx=10, pady=10)

        label = tk.Label(self.music_frame, text=f"Playlist : {playlist_name}", font=("Arial", 16), bg="white")
        label.pack()

        music_listbox = tk.Listbox(self.music_frame, font=("Arial", 12), selectbackground="#d0d0d0")
        music_listbox.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        playlist_path = os.path.join(PLAYLISTS_DIR, playlist_name)
        musics = [f for f in os.listdir(playlist_path) if f.endswith(".mp3")]

        for music in musics:
            music_listbox.insert(tk.END, music)

        def play_selected(event):
            selection = music_listbox.curselection()
            if selection:
                song = music_listbox.get(selection[0])
                full_path = os.path.join(playlist_path, song)
                subprocess.run([MPV_PATH, full_path])

        music_listbox.bind("<<ListboxSelect>>", play_selected)

    def back_to_playlists(self):
        self.music_frame.pack_forget()
        self.playlist_frame.pack(fill=tk.BOTH, expand=True)
        self.load_playlists()

if __name__ == "__main__":
    root = tk.Tk()
    app = PyPlaylistApp(root)
    root.mainloop()
