"""
Module System Tray (zone de notification).
"""
import pystray
from PIL import Image, ImageDraw
import threading
from typing import Optional, Callable


class SystemTray:
    """Gestionnaire du System Tray."""
    
    def __init__(self, on_config_clicked: Optional[Callable] = None, on_quit_clicked: Optional[Callable] = None):
        """
        Initialise le System Tray.
        
        Args:
            on_config_clicked: Callback appelé quand "Configuration" est cliqué
            on_quit_clicked: Callback appelé quand "Quitter" est cliqué
        """
        self.on_config_clicked = on_config_clicked
        self.on_quit_clicked = on_quit_clicked
        self.icon = None
        self.status = "idle"  # "idle", "recording", "processing", "error"
        self._create_icon()
    
    def _create_icon(self):
        """Crée l'icône du System Tray."""
        # Créer une image simple pour l'icône
        image = Image.new('RGB', (64, 64), color='#2C2C2C')
        draw = ImageDraw.Draw(image)
        
        # Dessiner un cercle avec un point au centre
        draw.ellipse([10, 10, 54, 54], fill='#1E1E1E', outline='#404040', width=2)
        draw.ellipse([28, 28, 36, 36], fill='#00FF00')
        
        # Créer le menu
        menu = pystray.Menu(
            pystray.MenuItem("Configuration", self._on_config, default=True),
            pystray.MenuItem("Quitter", self._on_quit)
        )
        
        self.icon = pystray.Icon("OpenSuperWhisper", image, "OpenSuperWhisper", menu)
    
    def _on_config(self, icon, item):
        """Gère le clic sur Configuration."""
        if self.on_config_clicked:
            self.on_config_clicked()
    
    def _on_quit(self, icon, item):
        """Gère le clic sur Quitter."""
        if self.on_quit_clicked:
            self.on_quit_clicked()
        self.stop()
    
    def set_status(self, status: str):
        """
        Définit le statut de l'application.
        
        Args:
            status: "idle", "recording", "processing", "error"
        """
        self.status = status
        if self.icon:
            # Mettre à jour l'icône selon le statut
            image = Image.new('RGB', (64, 64), color='#2C2C2C')
            draw = ImageDraw.Draw(image)
            
            # Couleur selon le statut
            if status == "recording":
                color = '#FF0000'
            elif status == "processing":
                color = '#FFFF00'
            elif status == "error":
                color = '#FF0000'
            else:
                color = '#00FF00'
            
            draw.ellipse([10, 10, 54, 54], fill='#1E1E1E', outline='#404040', width=2)
            draw.ellipse([28, 28, 36, 36], fill=color)
            
            self.icon.icon = image
    
    def run(self):
        """Lance le System Tray dans un thread séparé."""
        def run_icon():
            self.icon.run()
        
        thread = threading.Thread(target=run_icon, daemon=True)
        thread.start()
    
    def stop(self):
        """Arrête le System Tray."""
        if self.icon:
            self.icon.stop()

