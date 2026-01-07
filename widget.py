"""
Module du widget flottant (Overlay) Tkinter.
"""
import tkinter as tk
from tkinter import Canvas
import math
import threading
from typing import Optional, Callable
from datetime import datetime, timedelta


class FloatingWidget:
    """Widget flottant toujours au-dessus des autres fenêtres."""
    
    MIN_SIZE = 20  # Taille minimale en pixels
    EXTENDED_WIDTH = 200
    EXTENDED_HEIGHT = 100
    
    def __init__(self, position: tuple = (50, 50), visible: bool = True):
        """
        Initialise le widget flottant.
        
        Args:
            position: Position initiale (x, y)
            visible: Si le widget doit être visible en mode minimal
        """
        self.root = tk.Tk()
        self.root.title("OpenSuperWhisper Widget")
        self.root.overrideredirect(True)  # Supprimer la barre de titre
        self.root.attributes('-topmost', True)  # Toujours au-dessus
        self.root.attributes('-alpha', 0.9)  # Légère transparence
        
        # Rendre la fenêtre circulaire (sur Windows)
        self._make_circular_window()
        
        # Variables d'état
        self.is_minimal = True
        self.is_recording = False
        self.status = "ok"  # "ok", "error", ou "loading"
        self.visible = visible
        self.position = position
        self._blink_state = False  # Pour le clignotement
        self._blink_timer = None  # Timer pour le clignotement
        
        # Variables pour le déplacement
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.is_dragging = False
        
        # Variables pour l'enregistrement
        self.recording_start_time = None
        self.audio_levels = []  # Pour le waveform
        self.max_audio_levels = 50  # Nombre de points pour le waveform
        
        # Canvas
        self.canvas = Canvas(
            self.root,
            width=self.MIN_SIZE,
            height=self.MIN_SIZE,
            bg='#2C2C2C',
            highlightthickness=0
        )
        self.canvas.pack()
        
        # Bindings pour le déplacement
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        
        # Callback pour la position
        self.on_position_changed: Optional[Callable[[int, int], None]] = None
        # Callback pour ouvrir la configuration au clic
        self.on_click: Optional[Callable[[], None]] = None
        
        # Mise à jour de l'affichage
        self._update_display()
        
        # Le timer sera démarré depuis main.py dans le thread principal
    
    def _make_circular_window(self):
        """Rend la fenêtre circulaire sur Windows."""
        try:
            import win32gui
            import win32ui
            
            # Cette méthode sera appelée après que la fenêtre soit créée
            # On va la rappeler après le premier update
            self._apply_circular_shape = True
        except ImportError:
            # Si win32 n'est pas disponible, on utilisera juste la transparence
            self._apply_circular_shape = False
    
    def _apply_circular_shape_now(self):
        """Applique la forme circulaire à la fenêtre."""
        if not getattr(self, '_apply_circular_shape', False):
            return
        
        try:
            import win32gui
            import win32ui
            
            # Attendre que la fenêtre soit créée
            self.root.update_idletasks()
            hwnd = self.root.winfo_id()
            
            # Créer une région circulaire
            rgn = win32ui.CreateEllipticRgn(0, 0, self.MIN_SIZE, self.MIN_SIZE)
            win32gui.SetWindowRgn(hwnd, rgn, True)
        except (ImportError, Exception):
            pass
    
    def _on_click(self, event):
        """Gère le clic sur le widget."""
        if self.is_minimal:
            self.drag_start_x = event.x
            self.drag_start_y = event.y
            self.is_dragging = True
            # Programmer un callback pour détecter un simple clic (pas un drag)
            self._click_time = event.time
            self._click_x = event.x
            self._click_y = event.y
    
    def _on_drag(self, event):
        """Gère le glisser du widget."""
        if self.is_dragging and self.is_minimal:
            x = self.root.winfo_x() + event.x - self.drag_start_x
            y = self.root.winfo_y() + event.y - self.drag_start_y
            self.set_position(x, y)
    
    def _on_release(self, event):
        """Gère le relâchement du clic."""
        if self.is_dragging and self.is_minimal:
            # Vérifier si c'était un simple clic (pas un drag)
            # Si la position n'a pas beaucoup changé, c'est un clic
            if (abs(event.x - self._click_x) < 5 and 
                abs(event.y - self._click_y) < 5 and
                hasattr(self, '_click_time')):
                # C'était un simple clic, ouvrir la configuration
                if self.on_click:
                    self.on_click()
        self.is_dragging = False
    
    def set_position(self, x: int, y: int):
        """Définit la position du widget."""
        self.position = (x, y)
        self.root.geometry(f"+{x}+{y}")
        if self.on_position_changed:
            self.on_position_changed(x, y)
    
    def set_status(self, status: str):
        """
        Définit le statut du widget.
        
        Args:
            status: "ok" (vert), "error" (rouge), ou "loading" (orange clignotant)
        """
        old_status = self.status
        self.status = status
        
        # Gérer le clignotement pour le statut "loading"
        if status == "loading":
            if old_status != "loading":
                # Démarrer le clignotement
                self._blink_state = True
                self._start_blinking()
        else:
            # Arrêter le clignotement
            self._stop_blinking()
        
        self.root.after(0, self._update_display)
    
    def _start_blinking(self):
        """Démarre le clignotement du point orange."""
        if self.status == "loading":
            self._blink_state = not self._blink_state
            self._update_display()
            # Programmer le prochain clignotement (500ms)
            self._blink_timer = self.root.after(500, self._start_blinking)
    
    def _stop_blinking(self):
        """Arrête le clignotement."""
        if self._blink_timer:
            self.root.after_cancel(self._blink_timer)
            self._blink_timer = None
        self._blink_state = False
    
    def start_recording(self):
        """Démarre l'affichage de l'enregistrement."""
        self.root.after(0, self._start_recording_thread_safe)
    
    def _start_recording_thread_safe(self):
        """Démarre l'enregistrement de manière thread-safe."""
        self.is_recording = True
        self.is_minimal = False
        self.recording_start_time = datetime.now()
        self.audio_levels = []
        self._update_display()
    
    def stop_recording(self):
        """Arrête l'affichage de l'enregistrement."""
        self.root.after(0, self._stop_recording_thread_safe)
    
    def _stop_recording_thread_safe(self):
        """Arrête l'enregistrement de manière thread-safe."""
        self.is_recording = False
        self.is_minimal = True
        self.recording_start_time = None
        self.audio_levels = []
        self._update_display()
    
    def update_audio_level(self, level: float):
        """
        Met à jour le niveau audio pour le waveform.
        
        Args:
            level: Niveau audio entre 0.0 et 1.0
        """
        if self.is_recording:
            # Utiliser after pour s'assurer que la mise à jour se fait dans le bon thread
            self.root.after(0, self._update_audio_level_thread_safe, level)
    
    def _update_audio_level_thread_safe(self, level: float):
        """Met à jour le niveau audio de manière thread-safe."""
        self.audio_levels.append(level)
        if len(self.audio_levels) > self.max_audio_levels:
            self.audio_levels.pop(0)
    
    def set_visible(self, visible: bool):
        """Définit la visibilité du widget (sauf pendant l'enregistrement)."""
        print(f"[Widget] set_visible appelé: visible={visible}, is_recording={self.is_recording}, self.visible={self.visible}")
        self.visible = visible
        
        # Toujours mettre à jour, même si en enregistrement (mais ne pas masquer pendant l'enregistrement)
        if visible:
            print("[Widget] Affichage du widget")
            try:
                self.root.deiconify()
                self.root.lift()  # S'assurer qu'il est au-dessus
                self.root.update()  # Forcer la mise à jour
                print(f"[Widget] Widget affiché (existe: {self.root.winfo_exists()})")
            except Exception as e:
                print(f"[Widget] Erreur lors de l'affichage: {e}")
        elif not self.is_recording:
            # Seulement masquer si on n'est pas en train d'enregistrer
            print("[Widget] Masquage du widget")
            try:
                self.root.withdraw()
                self.root.update()  # Forcer la mise à jour
                print(f"[Widget] Widget masqué (existe: {self.root.winfo_exists()})")
            except Exception as e:
                print(f"[Widget] Erreur lors du masquage: {e}")
        else:
            print("[Widget] Widget en cours d'enregistrement, ne peut pas être masqué")
    
    def _update_display(self):
        """Met à jour l'affichage du widget."""
        self.canvas.delete("all")
        
        if self.is_minimal:
            # Mode minimal : cercle de 20x20 pixels
            self.root.geometry(f"{self.MIN_SIZE}x{self.MIN_SIZE}+{self.position[0]}+{self.position[1]}")
            self.canvas.config(width=self.MIN_SIZE, height=self.MIN_SIZE)
            
            # Fond transparent pour rendre la fenêtre circulaire
            self.root.attributes('-transparentcolor', '#2C2C2C')
            self.canvas.config(bg='#2C2C2C')
            
            # Appliquer la forme circulaire si possible
            self._apply_circular_shape_now()
            
            # Fond circulaire noir avec bord blanc
            self.canvas.create_oval(
                0, 0, self.MIN_SIZE - 1, self.MIN_SIZE - 1,
                fill='#1E1E1E',
                outline='#FFFFFF',
                width=2
            )
            
            # Point de statut au centre
            if self.status == "ok":
                color = '#00FF00'
            elif self.status == "error":
                color = '#FF0000'
            elif self.status == "loading":
                # Orange clignotant
                color = '#FFA500' if self._blink_state else '#FF8C00'
            else:
                color = '#00FF00'
            
            self.canvas.create_oval(
                self.MIN_SIZE // 2 - 4,
                self.MIN_SIZE // 2 - 4,
                self.MIN_SIZE // 2 + 4,
                self.MIN_SIZE // 2 + 4,
                fill=color,
                outline=color
            )
        else:
            # Mode étendu : widget avec waveform et timer
            self.root.geometry(f"{self.EXTENDED_WIDTH}x{self.EXTENDED_HEIGHT}+{self.position[0]}+{self.position[1]}")
            self.canvas.config(width=self.EXTENDED_WIDTH, height=self.EXTENDED_HEIGHT)
            
            # Fond
            self.canvas.create_rectangle(
                0, 0, self.EXTENDED_WIDTH, self.EXTENDED_HEIGHT,
                fill='#2C2C2C',
                outline='#404040',
                width=2
            )
            
            # Point de statut en haut à gauche
            if self.status == "ok":
                color = '#00FF00'
            elif self.status == "error":
                color = '#FF0000'
            elif self.status == "loading":
                # Orange clignotant
                color = '#FFA500' if self._blink_state else '#FF8C00'
            else:
                color = '#00FF00'
            self.canvas.create_oval(5, 5, 15, 15, fill=color, outline=color)
            
            # Timer
            if self.recording_start_time:
                elapsed = datetime.now() - self.recording_start_time
                total_seconds = int(elapsed.total_seconds())
                minutes = total_seconds // 60
                seconds = total_seconds % 60
                time_str = f"{minutes:02d}:{seconds:02d}"
                self.canvas.create_text(
                    self.EXTENDED_WIDTH // 2,
                    20,
                    text=time_str,
                    fill='#FFFFFF',
                    font=('Arial', 12, 'bold')
                )
            
            # Waveform
            if self.audio_levels:
                self._draw_waveform()
    
    def _draw_waveform(self):
        """Dessine le waveform."""
        if not self.audio_levels:
            return
        
        center_y = self.EXTENDED_HEIGHT // 2 + 20
        max_height = 30
        
        # Dessiner le waveform
        points = []
        for i, level in enumerate(self.audio_levels):
            x = 10 + (i * (self.EXTENDED_WIDTH - 20) / len(self.audio_levels))
            height = level * max_height
            points.append((x, center_y - height))
            points.append((x, center_y + height))
        
        if len(points) >= 4:
            # Dessiner les barres du waveform
            for i in range(0, len(points) - 2, 2):
                x = points[i][0]
                y1 = points[i][1]
                y2 = points[i + 1][1]
                self.canvas.create_line(
                    x, y1, x, y2,
                    fill='#00FF00',
                    width=2
                )
    
    def _update_timer(self):
        """Met à jour le timer et l'affichage."""
        if self.is_recording:
            self._update_display()
        self.root.after(100, self._update_timer)  # Mise à jour toutes les 100ms
    
    def show(self):
        """Affiche le widget."""
        self.root.deiconify()
    
    def hide(self):
        """Cache le widget (sauf pendant l'enregistrement)."""
        if not self.is_recording:
            self.root.withdraw()
    
    def run(self):
        """Lance la boucle principale du widget."""
        # Cette méthode n'est plus utilisée car mainloop() est appelé directement
        # dans le thread principal depuis main.py
        pass
    
    def destroy(self):
        """Détruit le widget."""
        try:
            self.root.quit()
        except:
            pass
        try:
            self.root.destroy()
        except:
            pass

