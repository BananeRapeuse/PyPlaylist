import os
import sys

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
dll_path = os.path.join(BASE_DIR, "mpv")
os.environ["PATH"] = dll_path + os.pathsep + os.environ["PATH"]
PLAYLISTS_DIR = os.path.join(BASE_DIR, "playlists")
MPV_PATH = os.path.join(BASE_DIR, "mpv", "mpv.exe")
THUMBNAIL_DIR = os.path.join(BASE_DIR, "contents", "PNGs", "thumbnails")
DEFAULT_THUMBNAIL = os.path.join(BASE_DIR, "contents", "PNGs", "blank_t.png")

# List of supported audio formats
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
# Import pypresence for Discord Rich Presence
try:
    from pypresence import Presence
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False
    print("Module pypresence not found. Discord integration will not be available.")

# Create directories if missing
os.makedirs(PLAYLISTS_DIR, exist_ok=True)
os.makedirs(THUMBNAIL_DIR, exist_ok=True)

# Discord application ID (you need to create your own Discord application)
# Replace this value with your own Discord client ID
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

        # Theme variables
        self.current_theme = "light"  # Default theme
        self.bg_color = "white"
        self.text_color = "black"

        self.thumbnail_cache = {}
        self.playlist_frame = tk.Frame(root, bg=self.bg_color)
        self.playlist_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create theme button first before calling load_playlists
        self.theme_button = None
        
        # Flag to control auto-play
        self.skip_next_auto_play = False
        
        # Initialize MPV player with event handlers for end of file
        self.player = mpv.MPV(input_default_bindings=True, input_vo_keyboard=True)
        
        # Add event listener to detect end of file
        @self.player.event_callback('end-file')
        def on_end_file(event):
            if not self.skip_next_auto_play:
                # Ensure we're in the main thread
                self.root.after(100, self.auto_play_next)
            else:
                # Reset the flag after using it
                self.skip_next_auto_play = False
        
        self.current_playlist_path = None
        self.music_list = []
        self.current_index = 0
        self.is_paused = False
        self.progress_label = None
        self.current_song_label = None
        self.current_music_path = None
        
        # Initialize Discord Rich Presence
        self.discord_rpc = None
        self.init_discord()
        
        # Variable to store current Discord status
        self.current_discord_status = None
        
        # Load playlists
        self.load_playlists()
        
        # Make sure Discord status is cleared on close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def init_discord(self):
        """Initialize connection with Discord Rich Presence"""
        if not DISCORD_AVAILABLE:
            return
            
        try:
            self.discord_rpc = Presence(DISCORD_CLIENT_ID)
            self.discord_rpc.connect()
            print("Connected to Discord Rich Presence")
        except Exception as e:
            print(f"Error connecting to Discord: {e}")
            self.discord_rpc = None

    def update_discord_presence(self, song_name=None, playlist_name=None, is_paused=False):
        """Update Discord Rich Presence status"""
        if not self.discord_rpc:
            return
            
        try:
            if song_name:
                # Remove file extension if present
                file_name, file_ext = os.path.splitext(song_name)
                if file_ext.lower() in SUPPORTED_AUDIO_FORMATS:
                    song_name = file_name
                    
                state = f"Paused" if is_paused else f"Listening"
                details = f"PyPlaylist | {song_name}"
                
                if playlist_name:
                    state += f" - Playlist: {playlist_name}"
                
                # Update Discord status
                self.discord_rpc.update(
                    state=state,
                    details=details,
                    large_image="music",  # Key of an image uploaded to your Discord application
                    large_text="PyPlaylist",
                    start=int(time.time()) if not is_paused else None  # Elapsed time if not paused
                )
                self.current_discord_status = song_name
            else:
                # Clear status when no music is playing
                self.discord_rpc.clear()
                self.current_discord_status = None
        except Exception as e:
            print(f"Error updating Discord status: {e}")

    def load_thumbnail(self, playlist_name):
        path = os.path.join(THUMBNAIL_DIR, f"{playlist_name}.png")
        if not os.path.exists(path):
            path = DEFAULT_THUMBNAIL
        img = Image.open(path).resize((160, 160))
        return ImageTk.PhotoImage(img)

    def load_playlists(self):
        # Save theme button if it already exists
        keep_theme_button = self.theme_button
        
        # Remove all existing widgets
        for widget in self.playlist_frame.winfo_children():
            widget.destroy()

        header = tk.Label(self.playlist_frame, text="🎵 Your Playlists", font=("Arial", 18), bg=self.bg_color, fg=self.text_color)
        header.pack(pady=20)
        
        # Recreate theme button
        self.theme_button = tk.Button(self.playlist_frame, text="Change Theme", command=self.toggle_theme)
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

        add_btn = tk.Button(self.playlist_frame, text="+ New Playlist", font=("Arial", 14),
                            command=self.create_playlist, bg="#e0e0e0")
        add_btn.pack(pady=20)

    def create_playlist(self):
        name = simpledialog.askstring("New Playlist", "Playlist name:")
        if not name:
            return
        playlist_path = os.path.join(PLAYLISTS_DIR, name)
        if os.path.exists(playlist_path):
            messagebox.showerror("Error", "This playlist already exists.")
            return
        os.makedirs(playlist_path)

        img_path = filedialog.askopenfilename(title="Choose a thumbnail (512x512 PNG)", filetypes=[("PNG", "*.png")])
        if img_path:
            try:
                with Image.open(img_path) as img:
                    if img.size != (512, 512):
                        raise ValueError("Image must be 512x512")
                    dest = os.path.join(THUMBNAIL_DIR, f"{name}.png")
                    img.save(dest)
            except Exception as e:
                messagebox.showwarning("Invalid Thumbnail", f"Thumbnail error: {e}\nUsing default thumbnail.")
        else:
            default = os.path.join(THUMBNAIL_DIR, f"{name}.png")
            Image.open(DEFAULT_THUMBNAIL).save(default)

        self.load_playlists()

    def show_context_menu(self, event, playlist_name):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Add Music", command=lambda: self.add_music_to_playlist(playlist_name))
        menu.add_command(label="Change Thumbnail", command=lambda: self.change_thumbnail(playlist_name))
        menu.add_command(label="Delete Playlist", command=lambda: self.delete_playlist(playlist_name))
        menu.tk_popup(event.x_root, event.y_root)

    def add_music_to_playlist(self, playlist_name):
        playlist_path = os.path.join(PLAYLISTS_DIR, playlist_name)
        
        # Build filter for file selection dialog
        filetypes = []
        for ext in SUPPORTED_AUDIO_FORMATS:
            desc = f"{ext.upper()[1:]} Audio"
            filetypes.append((desc, f"*{ext}"))
        
        # Add "All audio files" option
        all_formats = " ".join(f"*{ext}" for ext in SUPPORTED_AUDIO_FORMATS)
        filetypes.insert(0, ("All audio files", all_formats))
        
        # Open dialog to select files
        files = filedialog.askopenfilenames(
            title="Add music to playlist",
            filetypes=filetypes
        )
        
        if not files:
            return
        
        # Copy selected files to playlist folder
        for file_path in files:
            file_name = os.path.basename(file_path)
            dest_path = os.path.join(playlist_path, file_name)
            
            if os.path.exists(dest_path):
                if not messagebox.askyesno("File exists", 
                    f"The file {file_name} already exists in the playlist.\nDo you want to replace it?"):
                    continue
            
            try:
                import shutil
                shutil.copy2(file_path, dest_path)
            except Exception as e:
                messagebox.showerror("Error", f"Unable to add {file_name}: {e}")
        
        # If playlist is currently open, update the list
        if hasattr(self, 'current_playlist_path') and self.current_playlist_path == playlist_path:
            self.update_music_list()

    def update_music_list(self):
        if not hasattr(self, 'music_listbox'):
            return
            
        # Save current selection
        current_selection = self.music_listbox.curselection()
        
        # Clear and rebuild the list
        self.music_listbox.delete(0, tk.END)
        self.music_list = []
        
        # Get all audio files in directory
        for file in os.listdir(self.current_playlist_path):
            ext = os.path.splitext(file)[1].lower()
            if ext in SUPPORTED_AUDIO_FORMATS:
                self.music_list.append(file)
        
        # Sort list alphabetically
        self.music_list.sort()
        
        # Fill listbox
        for music in self.music_list:
            self.music_listbox.insert(tk.END, music)
        
        # Restore selection if possible
        if current_selection and current_selection[0] < len(self.music_list):
            self.music_listbox.selection_set(current_selection[0])

    def change_thumbnail(self, playlist_name):
        path = filedialog.askopenfilename(title="New thumbnail (512x512 PNG)", filetypes=[("PNG", "*.png")])
        if path:
            try:
                with Image.open(path) as img:
                    if img.size != (512, 512):
                        raise ValueError("Image must be 512x512 pixels")
                    dest = os.path.join(THUMBNAIL_DIR, f"{playlist_name}.png")
                    img.save(dest)
                    self.load_playlists()
            except Exception as e:
                messagebox.showerror("Thumbnail error", f"Unable to change image: {e}")

    def delete_playlist(self, playlist_name):
        if messagebox.askyesno("Delete", f"Delete playlist '{playlist_name}'?"):
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

        back_btn = tk.Button(self.music_frame, text="← Back", command=self.back_to_playlists,
                             bg=self.bg_color, font=("Arial", 12))
        back_btn.pack(anchor="w", padx=10, pady=10)

        label = tk.Label(self.music_frame, text=f"Playlist: {playlist_name}", font=("Arial", 16), bg=self.bg_color, fg=self.text_color)
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

        # Add volume controller
        volume_frame = tk.Frame(self.music_frame, bg=self.bg_color)
        volume_frame.pack(pady=10)

        volume_label = tk.Label(volume_frame, text="Volume", bg=self.bg_color, fg=self.text_color)
        volume_label.pack(side=tk.LEFT, padx=5)

        self.volume_scale = tk.Scale(volume_frame, from_=0, to_=100, orient=tk.HORIZONTAL, bg=self.bg_color, command=self.set_volume)
        self.volume_scale.set(50)  # Initial volume 50%
        self.volume_scale.pack(side=tk.LEFT)

        # Add checkbox for Discord integration
        if DISCORD_AVAILABLE:
            self.discord_var = tk.IntVar(value=1)  # Enabled by default
            discord_check = tk.Checkbutton(self.music_frame, text="Show on Discord", 
                                          variable=self.discord_var, bg=self.bg_color, fg=self.text_color,
                                          activebackground=self.bg_color)
            discord_check.pack(pady=5)

        self.music_listbox = tk.Listbox(self.music_frame, font=("Arial", 12), selectbackground="#d0d0d0")
        self.music_listbox.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self.current_playlist_path = os.path.join(PLAYLISTS_DIR, playlist_name)
        self.music_list = []
        
        # Get all recognized audio files
        for file in os.listdir(self.current_playlist_path):
            ext = os.path.splitext(file)[1].lower()
            if ext in SUPPORTED_AUDIO_FORMATS:
                self.music_list.append(file)
        
        # Sort the list
        self.music_list.sort()

        for music in self.music_list:
            self.music_listbox.insert(tk.END, music)

        self.music_listbox.bind("<<ListboxSelect>>", self.on_select_music)

    def set_volume(self, volume):
        """Update mpv player volume."""
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
            messagebox.showerror("Error", "File not found.")
            return

        # Start music
        self.player.stop()
        self.player.play(path)
        self.current_music_path = path
        
        song_name = os.path.basename(path)
        playlist_name = os.path.basename(self.current_playlist_path)
        
        self.current_song_label.config(text=song_name)
        self.is_paused = False
        self.pause_btn.config(text="⏸")
        
        # Update Discord status if enabled
        if hasattr(self, 'discord_var') and self.discord_var.get() == 1 and DISCORD_AVAILABLE:
            self.update_discord_presence(song_name, playlist_name, is_paused=False)
        
        # Update progress in a thread
        self.update_progress()
        
        # Visually select current track in list
        self.music_listbox.selection_clear(0, tk.END)
        self.music_listbox.selection_set(self.current_index)
        self.music_listbox.see(self.current_index)

    def auto_play_next(self):
        """This method is called automatically when a song ends"""
        if not self.music_list:
            return
            
        self.current_index += 1
        if self.current_index >= len(self.music_list):
            self.current_index = 0
            
        next_song = self.music_list[self.current_index]
        next_path = os.path.join(self.current_playlist_path, next_song)
        self.play_music(next_path)

    def play_next(self):
        """This method is called when user clicks the next button"""
        if not self.music_list:
            return
           
        # Activate flag to prevent auto-play
        self.skip_next_auto_play = True
        
        # Move to next index
        self.current_index += 1
        if self.current_index >= len(self.music_list):
            self.current_index = 0
            
        next_song = self.music_list[self.current_index]
        next_path = os.path.join(self.current_playlist_path, next_song)
        
        # Play new track
        self.play_music(next_path)

    def play_previous(self):
        if not self.music_list:
            return
            
        # Activate flag to prevent auto-play
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
            
            # Update Discord status to indicate pause
            if hasattr(self, 'discord_var') and self.discord_var.get() == 1 and DISCORD_AVAILABLE and self.current_music_path:
                song_name = os.path.basename(self.current_music_path)
                playlist_name = os.path.basename(self.current_playlist_path)
                self.update_discord_presence(song_name, playlist_name, is_paused=self.is_paused)

    def shuffle_play(self):
        if not self.music_list:
            return
            
        # Activate flag to prevent auto-play
        self.skip_next_auto_play = True
        
        self.current_index = random.randint(0, len(self.music_list) - 1)
        song = self.music_list[self.current_index]
        full_path = os.path.join(self.current_playlist_path, song)
        self.play_music(full_path)

    def update_progress(self):
        """Update time progress synchronously with GUI."""
        def update():
            current = self.player.playback_time
            duration = self.player.duration
            if current is not None and duration is not None:
                self.progress_label.config(text=f"{self.format_time(int(current))} / {self.format_time(int(duration))}")
            self.root.after(1000, update)  # Update every second

        update()

    def format_time(self, seconds):
        m, s = divmod(seconds, 60)
        return f"{int(m):02}:{int(s):02}"

    def back_to_playlists(self):
        # Stop music and clear Discord status
        self.player.stop()
        if DISCORD_AVAILABLE and self.discord_rpc:
            self.update_discord_presence(None)
            
        self.music_frame.pack_forget()
        self.playlist_frame.pack(fill=tk.BOTH, expand=True)
        self.load_playlists()

    def toggle_theme(self):
        """Toggle between light and dark theme."""
        if self.current_theme == "light":
            self.current_theme = "dark"
        else:
            self.current_theme = "light"

        self.update_theme()

    def update_theme(self):
        """Update interface colors based on theme."""
        if self.current_theme == "light":
            self.bg_color = "white"
            self.text_color = "black"
        elif self.current_theme == "dark":
            self.bg_color = "#1c1c18"
            self.text_color = "white"

        # Update main window background
        self.root.configure(bg=self.bg_color)

        # Update colors in all parts of the application
        self.playlist_frame.configure(bg=self.bg_color)
        
        # Update theme by reloading playlists
        self.load_playlists()
        
    def on_close(self):
        """Method called when closing the application"""
        # Clear Discord status before closing
        if DISCORD_AVAILABLE and self.discord_rpc:
            try:
                self.discord_rpc.clear()
                self.discord_rpc.close()
            except:
                pass
                
        self.root.destroy()


if __name__ == "__main__":
    # Check if pypresence is installed, otherwise offer to install it
    if not DISCORD_AVAILABLE:
        try:
            response = messagebox.askyesno(
                "Missing module", 
                "The 'pypresence' module is necessary for Discord integration.\nDo you want to install it now?"
            )
            if response:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "pypresence"])
                messagebox.showinfo("Installation successful", "The module has been installed. Please restart the application.")
                sys.exit(0)
        except Exception as e:
            messagebox.showerror("Installation error", f"Unable to install the module: {e}")
    
    root = tk.Tk()
    app = PyPlaylistApp(root)
    root.mainloop()