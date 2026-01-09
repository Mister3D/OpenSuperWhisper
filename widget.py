"""
Module du widget flottant (Overlay) Tkinter - Design minimaliste et élégant.
"""
import tkinter as tk
from tkinter import Canvas
import math
import threading
from typing import Optional, Callable
from datetime import datetime, timedelta
try:
    from PIL import Image, ImageDraw, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
try:
    import darkdetect
    HAS_DARKDETECT = True
except ImportError:
    HAS_DARKDETECT = False


class FloatingWidget:
    """Widget flottant toujours au-dessus des autres fenêtres - Design minimaliste."""
    
    MIN_SIZE = 48  # Taille minimale
    EXTENDED_WIDTH = 240
    EXTENDED_HEIGHT = 80
    
    def __init__(self, position: tuple = (50, 50), visible: bool = True):
        """
        Initialise le widget flottant.
        
        Args:
            position: Position initiale (x, y)
            visible: Si le widget doit être visible en mode minimal
        """
        self.root = tk.Tk()
        self.root.title("OpenSuperWhisper Widget")
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', 0.95)
        
        # Détecter le thème système
        self._detect_theme()
        
        # Variables d'état
        self.is_minimal = True
        self.is_recording = False
        self.status = "ok"
        self.visible = visible
        self.position = position
        self._blink_state = False
        self._blink_timer = None
        
        # Variables pour le déplacement
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.is_dragging = False
        self.has_moved = False  # Pour détecter si on a vraiment déplacé le widget
        
        # Variables pour l'enregistrement
        self.recording_start_time = None
        self.audio_levels = []
        self.max_audio_levels = 50
        
        # Thread pour surveiller les changements de thème
        self._theme_monitor_thread = None
        self._theme_monitor_running = False
        self._start_theme_monitor()
        
        # Canvas
        self.canvas = Canvas(
            self.root,
            width=self.MIN_SIZE,
            height=self.MIN_SIZE,
            bg=self._get_bg_color(),
            highlightthickness=0
        )
        self.canvas.pack()
        
        # Bindings
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        
        # Callbacks
        self.on_position_changed: Optional[Callable[[int, int], None]] = None
        self.on_click: Optional[Callable[[], None]] = None
        
        # Mise à jour
        self._update_display()
    
    def _detect_theme(self):
        """Détecte le thème du système."""
        if HAS_DARKDETECT:
            try:
                self.is_dark_theme = darkdetect.isDark()
            except:
                self.is_dark_theme = True
        else:
            self.is_dark_theme = True
    
    def _get_bg_color(self):
        """Retourne la couleur de fond selon le thème."""
        # Utiliser une couleur transparente pour le fond
        return '#000001'  # Couleur presque noire pour la transparence
    
    def _get_border_color(self):
        """Retourne la couleur de bordure."""
        return '#3A3A3A' if self.is_dark_theme else '#E0E0E0'
    
    def _get_text_color(self):
        """Retourne la couleur du texte."""
        return '#FFFFFF' if self.is_dark_theme else '#000000'
    
    def _get_circle_colors(self):
        """Retourne les couleurs du cercle selon le thème."""
        if self.is_dark_theme:
            return {
                'fill': '#FFFFFF',  # Blanc en mode sombre
                'outline': '#E0E0E0'  # Bordure gris clair
            }
        else:
            return {
                'fill': '#1E1E1E',  # Noir en mode clair
                'outline': '#3A3A3A'  # Bordure gris foncé
            }
    
    def _get_status_color(self):
        """Retourne la couleur selon le statut."""
        if self.status == "ok":
            return '#10B981'  # Vert moderne
        elif self.status == "error":
            return '#EF4444'  # Rouge moderne
        elif self.status == "loading":
            return '#F59E0B' if self._blink_state else '#F97316'  # Orange
        return '#10B981'
    
    def _on_click(self, event):
        """Gère le clic sur le widget."""
        if self.is_minimal:
            self.drag_start_x = event.x
            self.drag_start_y = event.y
            self.is_dragging = True
            self.has_moved = False  # Réinitialiser le flag de déplacement
            self._click_time = event.time
            self._click_x = event.x
            self._click_y = event.y
            self._initial_x = self.root.winfo_x()
            self._initial_y = self.root.winfo_y()
    
    def _on_drag(self, event):
        """Gère le glisser du widget."""
        if self.is_dragging and self.is_minimal:
            x = self.root.winfo_x() + event.x - self.drag_start_x
            y = self.root.winfo_y() + event.y - self.drag_start_y
            self.set_position(x, y)
            # Marquer qu'on a déplacé le widget
            if abs(x - self._initial_x) > 3 or abs(y - self._initial_y) > 3:
                self.has_moved = True
    
    def _on_release(self, event):
        """Gère le relâchement du clic."""
        if self.is_dragging and self.is_minimal:
            # Si on n'a pas déplacé le widget (ou très peu), c'est un clic
            if not self.has_moved:
                if self.on_click:
                    self.on_click()
        self.is_dragging = False
        self.has_moved = False
    
    def set_position(self, x: int, y: int):
        """Définit la position du widget."""
        self.position = (x, y)
        self.root.geometry(f"+{x}+{y}")
        if self.on_position_changed:
            self.on_position_changed(x, y)
    
    def set_status(self, status: str):
        """Définit le statut du widget."""
        old_status = self.status
        self.status = status
        
        if status == "loading":
            if old_status != "loading":
                self._blink_state = True
                self._start_blinking()
        else:
            self._stop_blinking()
        
        self.root.after(0, self._update_display)
    
    def _start_blinking(self):
        """Démarre le clignotement."""
        if self.status == "loading":
            self._blink_state = not self._blink_state
            self._update_display()
            self._blink_timer = self.root.after(800, self._start_blinking)
    
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
        """Met à jour le niveau audio."""
        if self.is_recording:
            self.root.after(0, self._update_audio_level_thread_safe, level)
    
    def _update_audio_level_thread_safe(self, level: float):
        """Met à jour le niveau audio de manière thread-safe."""
        self.audio_levels.append(level)
        if len(self.audio_levels) > self.max_audio_levels:
            self.audio_levels.pop(0)
    
    def set_visible(self, visible: bool):
        """Définit la visibilité du widget."""
        print(f"[Widget] set_visible appelé: visible={visible}, is_recording={self.is_recording}, self.visible={self.visible}")
        self.visible = visible
        
        if visible:
            print("[Widget] Affichage du widget")
            try:
                self.root.deiconify()
                self.root.lift()
                self.root.update()
                print(f"[Widget] Widget affiché (existe: {self.root.winfo_exists()})")
            except Exception as e:
                print(f"[Widget] Erreur lors de l'affichage: {e}")
        elif not self.is_recording:
            print("[Widget] Masquage du widget")
            try:
                self.root.withdraw()
                self.root.update()
                print(f"[Widget] Widget masqué (existe: {self.root.winfo_exists()})")
            except Exception as e:
                print(f"[Widget] Erreur lors du masquage: {e}")
        else:
            print("[Widget] Widget en cours d'enregistrement, ne peut pas être masqué")
    
    def _update_display(self):
        """Met à jour l'affichage du widget."""
        self.canvas.delete("all")
        
        if self.is_minimal:
            # Mode minimal : cercle simple
            self.root.geometry(f"{self.MIN_SIZE}x{self.MIN_SIZE}+{self.position[0]}+{self.position[1]}")
            
            # Configurer la transparence pour que seul le cercle soit visible
            bg_color = self._get_bg_color()
            self.canvas.config(width=self.MIN_SIZE, height=self.MIN_SIZE, bg=bg_color)
            self.root.attributes('-transparentcolor', bg_color)
            
            center = self.MIN_SIZE // 2
            radius = 10
            status_color = self._get_status_color()
            circle_colors = self._get_circle_colors()
            
            # Cercle de fond (adapté au thème)
            self.canvas.create_oval(
                center - radius,
                center - radius,
                center + radius,
                center + radius,
                fill=circle_colors['fill'],
                outline=circle_colors['outline'],
                width=1
            )
            
            # Point de statut
            dot_radius = 4  # Réduit de 5 à 4 pour garder les proportions
            self.canvas.create_oval(
                center - dot_radius,
                center - dot_radius,
                center + dot_radius,
                center + dot_radius,
                fill=status_color,
                outline='',
                width=0
            )
        else:
            # Mode étendu : barre horizontale minimaliste
            self.root.geometry(f"{self.EXTENDED_WIDTH}x{self.EXTENDED_HEIGHT}+{self.position[0]}+{self.position[1]}")
            
            # Configurer la transparence
            bg_color = self._get_bg_color()
            self.canvas.config(width=self.EXTENDED_WIDTH, height=self.EXTENDED_HEIGHT, bg=bg_color)
            self.root.attributes('-transparentcolor', bg_color)
            
            border_color = self._get_border_color()
            text_color = self._get_text_color()
            status_color = self._get_status_color()
            
            # Fond adapté au thème
            bg_fill = '#1E1E1E' if self.is_dark_theme else '#FFFFFF'
            bg_outline = '#3A3A3A' if self.is_dark_theme else '#E0E0E0'
            
            self.canvas.create_rectangle(
                0, 0,
                self.EXTENDED_WIDTH, self.EXTENDED_HEIGHT,
                fill=bg_fill,
                outline=bg_outline,
                width=1
            )
            
            # Indicateur de statut (barre verticale à gauche)
            indicator_width = 3
            self.canvas.create_rectangle(
                0, 0,
                indicator_width, self.EXTENDED_HEIGHT,
                fill=status_color,
                outline='',
                width=0
            )
            
            # Timer
            if self.recording_start_time:
                elapsed = datetime.now() - self.recording_start_time
                total_seconds = int(elapsed.total_seconds())
                minutes = total_seconds // 60
                seconds = total_seconds % 60
                time_str = f"{minutes:02d}:{seconds:02d}"
                
                self.canvas.create_text(
                    15,
                    self.EXTENDED_HEIGHT // 2,
                    text=time_str,
                    fill=text_color,
                    font=('Segoe UI', 11),
                    anchor='w'
                )
            
            # Waveform minimaliste
            if self.audio_levels:
                self._draw_waveform_minimal()
    
    def _draw_waveform_minimal(self):
        """Dessine un waveform minimaliste."""
        if not self.audio_levels:
            return
        
        center_y = self.EXTENDED_HEIGHT // 2
        max_height = 20
        waveform_start_x = 70
        waveform_width = self.EXTENDED_WIDTH - waveform_start_x - 10
        
        # Couleur du waveform
        waveform_color = self._get_status_color()
        
        # Dessiner les barres
        bar_width = max(1, waveform_width // len(self.audio_levels))
        spacing = 1
        
        for i, level in enumerate(self.audio_levels):
            x = waveform_start_x + i * (bar_width + spacing)
            height = level * max_height
            
            if height > 0.5:
                self.canvas.create_rectangle(
                    x, center_y - height,
                    x + bar_width - spacing, center_y + height,
                    fill=waveform_color,
                    outline='',
                    width=0
                )
    
    def _update_timer(self):
        """Met à jour le timer et l'affichage."""
        if self.is_recording:
            self._update_display()
        self.root.after(100, self._update_timer)
    
    def show(self):
        """Affiche le widget."""
        self.root.deiconify()
    
    def hide(self):
        """Cache le widget (sauf pendant l'enregistrement)."""
        if not self.is_recording:
            self.root.withdraw()
    
    def _start_theme_monitor(self):
        """Démarre un thread pour surveiller les changements de thème système."""
        if not HAS_DARKDETECT:
            return
        
        self._theme_monitor_running = True
        
        def monitor_theme():
            """Thread qui surveille les changements de thème."""
            last_theme = self.is_dark_theme
            import time
            
            while self._theme_monitor_running:
                try:
                    if HAS_DARKDETECT:
                        is_dark = darkdetect.isDark()
                        
                        # Si le thème a changé, mettre à jour l'interface
                        if is_dark != last_theme:
                            print(f"[Widget] Changement de thème détecté: {last_theme} -> {is_dark}")
                            self.root.after(0, lambda: self._update_theme(is_dark))
                            last_theme = is_dark
                    
                    # Vérifier toutes les 2 secondes
                    time.sleep(2)
                except Exception as e:
                    print(f"[Widget] Erreur lors de la surveillance du thème: {e}")
                    time.sleep(2)
        
        self._theme_monitor_thread = threading.Thread(target=monitor_theme, daemon=True)
        self._theme_monitor_thread.start()
    
    def _update_theme(self, is_dark):
        """Met à jour le thème du widget."""
        if is_dark == self.is_dark_theme:
            return  # Pas de changement
        
        print(f"[Widget] Mise à jour du thème vers: {'dark' if is_dark else 'light'}")
        self.is_dark_theme = is_dark
        self._update_display()
    
    def run(self):
        """Lance la boucle principale du widget."""
        pass
    
    def destroy(self):
        """Détruit le widget."""
        # Arrêter le monitoring du thème
        self._theme_monitor_running = False
        try:
            self.root.quit()
        except:
            pass
        try:
            self.root.destroy()
        except:
            pass
