"""
Module de feedback audio (sons de début et fin d'enregistrement).
"""
import winsound
import threading
import os
from pathlib import Path


class AudioFeedback:
    """Gestionnaire des sons de feedback."""
    
    def __init__(self):
        """Initialise le gestionnaire de feedback audio."""
        self._generate_beep_sounds()
    
    def _generate_beep_sounds(self) -> None:
        """Génère les sons de feedback si nécessaire."""
        # Pour Windows, on utilise winsound.Beep qui génère des sons simples
        # On peut aussi utiliser des fichiers WAV si disponibles
        self.start_sound_available = False
        self.end_sound_available = False
        
        # Chercher des fichiers audio dans le répertoire de l'application
        app_dir = Path(__file__).parent
        start_sound_path = app_dir / "sounds" / "start.wav"
        end_sound_path = app_dir / "sounds" / "end.wav"
        
        if start_sound_path.exists():
            self.start_sound_path = str(start_sound_path)
            self.start_sound_available = True
        else:
            self.start_sound_path = None
        
        if end_sound_path.exists():
            self.end_sound_path = str(end_sound_path)
            self.end_sound_available = True
        else:
            self.end_sound_path = None
    
    def play_start_sound(self) -> None:
        """Joue le son de début d'enregistrement."""
        threading.Thread(target=self._play_sound, args=(True,), daemon=True).start()
    
    def play_end_sound(self) -> None:
        """Joue le son de fin d'enregistrement."""
        threading.Thread(target=self._play_sound, args=(False,), daemon=True).start()
    
    def _play_sound(self, is_start: bool) -> None:
        """Joue un son de manière asynchrone."""
        try:
            if is_start:
                if self.start_sound_available:
                    winsound.PlaySound(self.start_sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                else:
                    # Son par défaut : beep court aigu
                    winsound.Beep(800, 100)
            else:
                if self.end_sound_available:
                    winsound.PlaySound(self.end_sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                else:
                    # Son par défaut : beep court grave
                    winsound.Beep(400, 100)
        except Exception as e:
            # En cas d'erreur, on ignore silencieusement pour ne pas perturber l'utilisateur
            pass

