"""
Module d'enregistrement audio.
"""
import sounddevice as sd
import numpy as np
import wave
import threading
import queue
from typing import Optional, Callable
from pathlib import Path
import tempfile


class AudioRecorder:
    """Gestionnaire d'enregistrement audio."""
    
    def __init__(self, sample_rate: int = 16000, channels: int = 1, device_index: Optional[int] = None):
        """
        Initialise l'enregistreur audio.
        
        Args:
            sample_rate: Taux d'échantillonnage (Hz)
            channels: Nombre de canaux (1 = mono, 2 = stéréo)
            device_index: Index du périphérique audio. None = auto-détection
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.device_index = device_index
        self.is_recording = False
        self.audio_queue = queue.Queue()
        self.audio_data = []
        self.stream = None
        self.recording_thread = None
        self.on_audio_chunk: Optional[Callable[[np.ndarray], None]] = None
    
    def get_default_device(self) -> Optional[int]:
        """Retourne l'index du périphérique audio par défaut."""
        try:
            default_device = sd.query_devices(kind='input')
            return default_device['index']
        except Exception:
            return None
    
    def list_devices(self) -> list:
        """Liste tous les périphériques d'entrée audio disponibles."""
        devices = []
        try:
            all_devices = sd.query_devices()
            for i, device in enumerate(all_devices):
                if device['max_input_channels'] > 0:
                    devices.append({
                        'index': i,
                        'name': device['name'],
                        'channels': device['max_input_channels'],
                        'sample_rate': device['default_samplerate']
                    })
        except Exception as e:
            print(f"Erreur lors de la liste des périphériques: {e}")
        return devices
    
    def _audio_callback(self, indata, frames, time, status):
        """Callback appelé pour chaque chunk audio."""
        if status:
            print(f"Status audio: {status}")
        
        if self.is_recording:
            # Convertir en format approprié (float32)
            audio_chunk = indata.copy()
            self.audio_queue.put(audio_chunk)
            
            # Appeler le callback si défini (pour le waveform)
            if self.on_audio_chunk:
                try:
                    self.on_audio_chunk(audio_chunk)
                except Exception:
                    pass
    
    def start_recording(self) -> bool:
        """
        Démarre l'enregistrement audio.
        
        Returns:
            True si l'enregistrement a démarré avec succès, False sinon
        """
        if self.is_recording:
            return False
        
        try:
            # Utiliser le périphérique par défaut si non spécifié
            device = self.device_index if self.device_index is not None else self.get_default_device()
            
            # Vider la queue
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                except queue.Empty:
                    break
            
            self.audio_data = []
            self.is_recording = True
            
            # Créer le stream audio
            self.stream = sd.InputStream(
                device=device,
                channels=self.channels,
                samplerate=self.sample_rate,
                callback=self._audio_callback,
                dtype=np.float32
            )
            
            self.stream.start()
            return True
            
        except Exception as e:
            print(f"Erreur lors du démarrage de l'enregistrement: {e}")
            self.is_recording = False
            return False
    
    def stop_recording(self) -> Optional[str]:
        """
        Arrête l'enregistrement et sauvegarde le fichier WAV.
        
        Returns:
            Chemin vers le fichier WAV créé, ou None en cas d'erreur
        """
        if not self.is_recording:
            return None
        
        try:
            self.is_recording = False
            
            # Arrêter le stream
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None
            
            # Récupérer toutes les données audio de la queue
            audio_chunks = []
            while not self.audio_queue.empty():
                try:
                    chunk = self.audio_queue.get_nowait()
                    audio_chunks.append(chunk)
                except queue.Empty:
                    break
            
            # Convertir en array numpy
            if audio_chunks:
                audio_array = np.concatenate(audio_chunks, axis=0)
            else:
                # Pas de données enregistrées
                return None
            
            # Normaliser et convertir en int16 pour WAV
            # Normaliser entre -1.0 et 1.0
            if audio_array.max() > 1.0 or audio_array.min() < -1.0:
                audio_array = np.clip(audio_array, -1.0, 1.0)
            
            # Convertir en int16 (format WAV standard)
            audio_int16 = (audio_array * 32767).astype(np.int16)
            
            # Créer un fichier temporaire WAV
            temp_dir = Path(tempfile.gettempdir())
            temp_file = temp_dir / f"opensuperwhisper_{threading.get_ident()}.wav"
            
            # Sauvegarder en WAV
            with wave.open(str(temp_file), 'wb') as wav_file:
                wav_file.setnchannels(self.channels)
                wav_file.setsampwidth(2)  # 16 bits = 2 bytes
                wav_file.setframerate(self.sample_rate)
                wav_file.writeframes(audio_int16.tobytes())
            
            return str(temp_file)
            
        except Exception as e:
            print(f"Erreur lors de l'arrêt de l'enregistrement: {e}")
            return None
    
    def get_current_audio_level(self) -> float:
        """
        Retourne le niveau audio actuel (pour le waveform).
        
        Returns:
            Niveau audio entre 0.0 et 1.0
        """
        if not self.is_recording or self.audio_queue.empty():
            return 0.0
        
        try:
            # Récupérer le dernier chunk
            chunk = self.audio_queue.get_nowait()
            # Calculer le RMS (Root Mean Square) pour le niveau
            rms = np.sqrt(np.mean(chunk**2))
            return min(float(rms), 1.0)
        except queue.Empty:
            return 0.0
        except Exception:
            return 0.0

