"""
Point d'entrée principal de l'application OpenSuperWhisper.
"""
import sys
import threading
import time
import signal
import tkinter as tk
from pathlib import Path
from pynput import keyboard
from pynput.keyboard import Key, Listener

from config import Config
from widget import FloatingWidget
from system_tray import SystemTray
from audio_recorder import AudioRecorder
from audio_feedback import AudioFeedback
from transcription import TranscriptionService
from text_inserter import TextInserter
from config_ui import ConfigWindow


class OpenSuperWhisperApp:
    """Application principale OpenSuperWhisper."""
    
    def __init__(self):
        """Initialise l'application."""
        # Initialiser la configuration en premier (nécessaire pour les autres méthodes)
        self.config = Config()
        
        # Synchroniser le démarrage automatique avec le registre Windows
        self._sync_startup_setting()
        
        # S'assurer que le cache Whisper est accessible
        self._ensure_whisper_cache()
        
        # Vérifier les drivers NVIDIA au premier démarrage (une seule fois)
        self._check_nvidia_on_first_run()
    
    def _ensure_whisper_cache(self):
        """S'assure que le répertoire de cache Whisper existe et est accessible."""
        try:
            from pathlib import Path
            cache_dir = Path.home() / ".cache" / "whisper"
            cache_dir.mkdir(parents=True, exist_ok=True)
            # Vérifier l'accessibilité en écriture
            test_file = cache_dir / ".test_write"
            try:
                test_file.write_text("test")
                test_file.unlink()
            except Exception:
                # Si on ne peut pas écrire, afficher un avertissement mais continuer
                # (l'utilisateur pourra peut-être utiliser un autre emplacement)
                pass
        except Exception:
            # Ignorer les erreurs - Whisper gérera cela lui-même
            pass
        self.widget = None
        self.system_tray = None
        self.audio_recorder = None
        self.audio_feedback = AudioFeedback()
        self.transcription_service = None
        self.text_inserter = TextInserter()
        # Initialiser le processeur de texte (sera configuré dans _initialize_components)
        self.text_processor = None
        
        self.is_recording = False
        self.hotkey_listener = None
        self.hotkey_modifiers = []
        self.hotkey_key = None
        self.hotkey_key_obj = None
        self.pressed_keys = set()
        self.hotkey_active = False
        
        # Thread pour le widget
        self.widget_thread = None
        
        # Initialiser les composants
        self._initialize_components()
    
    def _check_nvidia_on_first_run(self):
        """Vérifie les drivers NVIDIA au premier démarrage et informe l'utilisateur si nécessaire."""
        try:
            config = Config()
            nvidia_checked = config.get("nvidia_drivers_checked", False)
            
            if not nvidia_checked:
                # Vérifier si un GPU NVIDIA est présent
                try:
                    import subprocess
                    result = subprocess.run(
                        ['nvidia-smi'],
                        capture_output=True,
                        text=True,
                        timeout=3
                    )
                    if result.returncode != 0:
                        # GPU NVIDIA probablement présent mais drivers non installés
                        print("[Application] [INFO] GPU NVIDIA détecté mais drivers non installés.")
                        print("[Application] [INFO] Pour utiliser l'accélération GPU:")
                        print("[Application] [INFO]   1. Installez les drivers NVIDIA depuis https://www.nvidia.com/Download/")
                        print("[Application] [INFO]   2. Redémarrez votre ordinateur")
                        print("[Application] [INFO]   3. L'application utilisera automatiquement le GPU si disponible")
                        print("[Application] [INFO] L'application fonctionnera en mode CPU pour l'instant.")
                except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                    # nvidia-smi non disponible - pas de GPU ou drivers non installés
                    pass
                except Exception:
                    # Ignorer les autres erreurs
                    pass
                
                # Marquer comme vérifié pour ne pas afficher à chaque démarrage
                config.set("nvidia_drivers_checked", True)
                config.save()
        except Exception:
            # Ignorer les erreurs lors de la vérification
            pass
    
    def _initialize_components(self):
        """Initialise tous les composants de l'application."""
        # Widget flottant
        position = self.config.get_widget_position()
        visible = self.config.get("widget.visible", True)
        self.widget = FloatingWidget(position=position, visible=visible)
        self.widget.on_position_changed = self._on_widget_position_changed
        self.widget.on_click = self._open_config
        
        # System Tray
        self.system_tray = SystemTray(
            on_config_clicked=self._open_config,
            on_quit_clicked=self._quit_application
        )
        
        # Enregistreur audio
        device_index = self.config.get("audio.device_index")
        sample_rate = self.config.get("audio.sample_rate", 16000)
        channels = self.config.get("audio.channels", 1)
        self.audio_recorder = AudioRecorder(
            sample_rate=sample_rate,
            channels=channels,
            device_index=device_index
        )
        self.audio_recorder.on_audio_chunk = self._on_audio_chunk
        
        # Service de transcription
        mode = self.config.get("mode", "api")
        api_url = self.config.get("api.url")
        api_token = self.config.get("api.token")
        whisper_model = self.config.get("whisper.model", "base")
        whisper_device = self.config.get("whisper.device", "cpu")
        self.transcription_service = TranscriptionService(
            mode=mode,
            api_url=api_url,
            api_token=api_token,
            whisper_model=whisper_model,
            whisper_device=whisper_device
        )
        
        # Processeur de texte intelligent
        from text_processor import TextProcessor
        keywords = self.config.get("text_processing.keywords", {})
        self.text_processor = TextProcessor(keywords=keywords)
        
        # Configurer le raccourci clavier
        self._setup_hotkey()
        
        # Vérifier si on doit charger le modèle Whisper au démarrage
        # Si oui, mettre le statut en "loading" IMMÉDIATEMENT pour éviter qu'il soit mis en "error"
        if (self.transcription_service.mode == "local" and 
            not self.transcription_service.is_model_loaded() and
            self.transcription_service.is_model_downloaded()):
            # Mettre le statut en "loading" AVANT tout autre appel
            # On doit attendre que le widget soit créé, donc on le fait dans run()
            pass  # On le fera dans run() après que le widget soit affiché
        else:
            # Si on ne charge pas le modèle, mettre à jour le statut maintenant
            self._update_status()
    
    def _on_widget_position_changed(self, x: int, y: int):
        """Callback appelé quand la position du widget change."""
        self.config.set_widget_position(x, y)
    
    def _on_audio_chunk(self, chunk):
        """Callback appelé pour chaque chunk audio."""
        if self.widget and self.is_recording:
            # Calculer le niveau audio
            import numpy as np
            level = float(np.sqrt(np.mean(chunk**2)))
            # update_audio_level est déjà thread-safe (utilise root.after)
            self.widget.update_audio_level(level)
    
    def _setup_hotkey(self):
        """Configure le raccourci clavier."""
        # Arrêter l'ancien listener si existant
        if self.hotkey_listener:
            try:
                self.hotkey_listener.stop()
                # Attendre un peu pour s'assurer que le listener est bien arrêté
                import time
                time.sleep(0.1)
            except Exception as e:
                print(f"[Application] Erreur lors de l'arrêt du listener: {e}")
        
        # Récupérer la configuration du raccourci
        self.hotkey_modifiers, self.hotkey_key = self.config.get_hotkey_tuple()
        
        # Convertir la touche en objet Key si nécessaire
        self.hotkey_key_obj = self._parse_key(self.hotkey_key)
        
        # État des touches
        self.pressed_keys = set()
        self.hotkey_active = False
        
        # Créer le listener personnalisé
        try:
            self.hotkey_listener = keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release
            )
            self.hotkey_listener.start()
            print(f"[Application] Raccourci clavier configuré: {self.config.get_hotkey_string()}")
        except Exception as e:
            print(f"[Application] Erreur lors de la création du listener: {e}")
            self.hotkey_listener = None
    
    def _parse_key(self, key_str: str):
        """Parse une chaîne de touche en objet Key."""
        key_str = key_str.lower()
        key_map = {
            'space': Key.space,
            'enter': Key.enter,
            'tab': Key.tab,
            'esc': Key.esc,
            'f1': Key.f1, 'f2': Key.f2, 'f3': Key.f3, 'f4': Key.f4,
            'f5': Key.f5, 'f6': Key.f6, 'f7': Key.f7, 'f8': Key.f8,
            'f9': Key.f9, 'f10': Key.f10, 'f11': Key.f11, 'f12': Key.f12,
        }
        return key_map.get(key_str, key_str)
    
    def _on_key_press(self, key):
        """Gère l'appui sur une touche."""
        try:
            # Vérifier si le widget existe encore
            if not self.widget or not self.widget.root:
                return
            
            # Ajouter la touche à l'ensemble des touches pressées
            self.pressed_keys.add(key)
            
            # Vérifier si le raccourci est activé
            if self._check_hotkey():
                if not self.hotkey_active:
                    self.hotkey_active = True
                    self._start_recording()
        except RuntimeError as e:
            # Ignorer les erreurs "main thread is not in main loop" si l'app se ferme
            if "main loop" not in str(e):
                print(f"Erreur dans _on_key_press: {e}")
        except Exception as e:
            print(f"Erreur dans _on_key_press: {e}")
    
    def _on_key_release(self, key):
        """Gère le relâchement d'une touche."""
        try:
            # Vérifier si le widget existe encore
            if not self.widget or not self.widget.root:
                return
            
            # Retirer la touche de l'ensemble
            self.pressed_keys.discard(key)
            
            # Vérifier si le raccourci est toujours actif
            if not self._check_hotkey():
                if self.hotkey_active:
                    self.hotkey_active = False
                    self._stop_recording()
        except RuntimeError as e:
            # Ignorer les erreurs "main thread is not in main loop" si l'app se ferme
            if "main loop" not in str(e):
                print(f"Erreur dans _on_key_release: {e}")
        except Exception as e:
            print(f"Erreur dans _on_key_release: {e}")
    
    def _check_hotkey(self) -> bool:
        """Vérifie si le raccourci clavier est actif."""
        # Vérifier les modificateurs
        ctrl_keys = {Key.ctrl, Key.ctrl_l, Key.ctrl_r}
        alt_keys = {Key.alt, Key.alt_l, Key.alt_r}
        shift_keys = {Key.shift, Key.shift_l, Key.shift_r}
        
        ctrl_pressed = bool(ctrl_keys & self.pressed_keys)
        alt_pressed = bool(alt_keys & self.pressed_keys)
        shift_pressed = bool(shift_keys & self.pressed_keys)
        
        # Vérifier les modificateurs requis
        if "ctrl" in self.hotkey_modifiers and not ctrl_pressed:
            return False
        if "alt" in self.hotkey_modifiers and not alt_pressed:
            return False
        if "shift" in self.hotkey_modifiers and not shift_pressed:
            return False
        
        # Vérifier que les modificateurs non requis ne sont pas pressés
        if "ctrl" not in self.hotkey_modifiers and ctrl_pressed:
            return False
        if "alt" not in self.hotkey_modifiers and alt_pressed:
            return False
        if "shift" not in self.hotkey_modifiers and shift_pressed:
            return False
        
        # Vérifier la touche principale
        if isinstance(self.hotkey_key_obj, Key):
            # Touche spéciale (Key.space, Key.f1, etc.)
            if self.hotkey_key_obj not in self.pressed_keys:
                return False
        else:
            # Touche normale (a-z, 0-9, etc.)
            key_str = self.hotkey_key.lower()
            found = False
            for k in self.pressed_keys:
                if isinstance(k, Key):
                    # Ignorer les touches spéciales
                    continue
                # Vérifier le caractère
                if hasattr(k, 'char') and k.char:
                    if k.char.lower() == key_str:
                        found = True
                        break
                # Vérifier la représentation en chaîne
                try:
                    k_str = str(k).replace("'", "").lower()
                    if k_str == key_str:
                        found = True
                        break
                except:
                    pass
            if not found:
                return False
        
        return True
    
    def _start_recording(self):
        """Démarre l'enregistrement."""
        if self.is_recording:
            return
        
        # Vérifier que le service de transcription est valide (sans charger le modèle ici)
        # Le modèle sera chargé automatiquement lors de la transcription si nécessaire
        is_valid, error = self.transcription_service.validate_configuration(load_model=False)
        if not is_valid:
            # Utiliser after pour les mises à jour thread-safe
            self.widget.root.after(0, lambda: self.widget.set_status("error"))
            self.system_tray.set_status("error")
            print(f"Erreur de configuration: {error}")
            return
        
        self.is_recording = True
        
        # Utiliser after pour toutes les mises à jour du widget (thread-safe)
        self.widget.root.after(0, lambda: self.widget.set_status("ok"))
        self.widget.root.after(0, lambda: self.widget.show())
        self.widget.root.after(0, lambda: self.widget.start_recording())
        self.system_tray.set_status("recording")
        
        # Démarrer l'enregistrement audio
        if self.audio_recorder.start_recording():
            self.audio_feedback.play_start_sound()
        else:
            self._stop_recording()
            self.widget.root.after(0, lambda: self.widget.set_status("error"))
            self.system_tray.set_status("error")
    
    def _stop_recording(self):
        """Arrête l'enregistrement et lance la transcription."""
        if not self.is_recording:
            return
        
        self.is_recording = False
        
        # Utiliser after pour les mises à jour thread-safe
        self.widget.root.after(0, lambda: self.widget.stop_recording())
        self.system_tray.set_status("processing")
        
        # Arrêter l'enregistrement audio
        audio_data = self.audio_recorder.stop_recording()
        self.audio_feedback.play_end_sound()
        
        if not audio_data:
            self.widget.root.after(0, lambda: self.widget.set_status("error"))
            self.system_tray.set_status("error")
            return
        
        # Lancer la transcription dans un thread séparé
        threading.Thread(
            target=self._process_transcription,
            args=(audio_data,),
            daemon=True
        ).start()
    
    def _process_transcription(self, audio_data):
        """Traite la transcription dans un thread séparé."""
        try:
            # Préparer les données selon le mode
            if self.transcription_service.mode == "api":
                # Mode API: passer directement les données audio
                print(f"[Application] Données audio: {len(audio_data[0])} échantillons")
                text = self.transcription_service.transcribe(audio_data)
            else:
                # Mode local: créer un fichier temporaire (nécessaire pour Whisper)
                import tempfile
                import uuid
                import wave
                import numpy as np
                
                audio_array, sample_rate, channels = audio_data
                
                # Convertir en int16 pour WAV
                audio_int16 = (audio_array * 32767).astype(np.int16)
                
                # Créer un fichier temporaire WAV
                temp_dir = Path(tempfile.gettempdir())
                temp_file = temp_dir / f"opensuperwhisper_{uuid.uuid4().hex}.wav"
                
                with wave.open(str(temp_file), 'wb') as wav_file:
                    wav_file.setnchannels(channels)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(sample_rate)
                    wav_file.writeframes(audio_int16.tobytes())
                
                print(f"[Application] Fichier temporaire créé: {temp_file} ({temp_file.stat().st_size} bytes)")
                text = self.transcription_service.transcribe(str(temp_file))
                
                # Nettoyer le fichier temporaire
                try:
                    temp_file.unlink()
                except:
                    pass
            
            if text:
                # Traiter le texte avec le processeur intelligent
                processed_text = self.text_processor.process(text)
                
                # Insérer le texte traité
                success = self.text_inserter.insert_text_smart(processed_text)
                
                if success:
                    self.widget.root.after(0, lambda: self.widget.set_status("ok"))
                    self.system_tray.set_status("idle")
                else:
                    # Le texte a été copié dans le presse-papiers
                    self.widget.root.after(0, lambda: self.widget.set_status("ok"))
                    self.system_tray.set_status("idle")
                    print("Texte copié dans le presse-papiers (insertion échouée)")
            else:
                self.widget.root.after(0, lambda: self.widget.set_status("error"))
                self.system_tray.set_status("error")
                print("Erreur: Aucun texte transcrit")
        
        except Exception as e:
            print(f"Erreur lors de la transcription: {e}")
            import traceback
            traceback.print_exc()
            self.widget.root.after(0, lambda: self.widget.set_status("error"))
            self.system_tray.set_status("error")
    
    def _update_status(self):
        """Met à jour le statut de l'application."""
        # Vérifier d'abord si le modèle est chargé, même si le statut est "loading"
        # car validate_configuration peut charger le modèle de manière synchrone
        if (self.transcription_service.mode == "local" and 
            self.transcription_service.is_model_loaded()):
            # Le modèle est chargé, mettre à jour le statut
            self.widget.root.after(0, lambda: self.widget.set_status("ok"))
            self.system_tray.set_status("idle")
            # Mettre à jour le bandeau d'information dans la fenêtre de configuration si elle est ouverte
            if hasattr(self, '_config_window') and self._config_window:
                self.widget.root.after(0, self._config_window._update_status_banner)
            return
        
        # Ne pas mettre à jour le statut si on est en train de charger (et le modèle n'est pas encore chargé)
        if self.widget.status == "loading":
            return
        
        # Vérifier si un chargement est en cours pour éviter les appels multiples
        if (hasattr(self.transcription_service, '_loading_in_progress') and 
            self.transcription_service._loading_in_progress):
            return  # Ne pas appeler validate_configuration si un chargement est déjà en cours
        
        # Si le modèle n'est pas chargé, vérifier la configuration
        # validate_configuration peut maintenant charger le modèle automatiquement
        is_valid, error = self.transcription_service.validate_configuration(load_model=False)
        
        if is_valid:
            # Vérifier si le modèle a été chargé par validate_configuration
            if (self.transcription_service.mode == "local" and 
                self.transcription_service.is_model_loaded()):
                # Le modèle vient d'être chargé, mettre à jour le statut
                self.widget.root.after(0, lambda: self.widget.set_status("ok"))
                self.system_tray.set_status("idle")
                # Mettre à jour le bandeau d'information dans la fenêtre de configuration si elle est ouverte
                if hasattr(self, '_config_window') and self._config_window:
                    self.widget.root.after(0, self._config_window._update_status_banner)
            elif self.transcription_service.mode == "local":
                # Le modèle n'est pas encore chargé, le chargement est en cours ou va se faire
                # Ne pas mettre en erreur si le chargement est prévu
                pass
            else:
                self.widget.root.after(0, lambda: self.widget.set_status("ok"))
                self.system_tray.set_status("idle")
        else:
            self.widget.root.after(0, lambda: self.widget.set_status("error"))
            self.system_tray.set_status("error")
            print(f"Configuration invalide: {error}")
    
    def _load_whisper_model_at_startup(self):
        """Charge le modèle Whisper au démarrage en arrière-plan (GPU si configuré)."""
        import threading
        
        # Note: Le mécanisme global_event_processor dans run() s'occupe déjà
        # de forcer Tkinter à traiter les événements pendant le chargement
        
        def load_thread():
            """Charge le modèle dans un thread séparé."""
            try:
                # Vérifier la configuration GPU
                device = self.transcription_service.whisper_device
                print(f"[Application] Chargement du modèle Whisper en arrière-plan (device: {device})...")
                
                # Si GPU est configuré, vérifier la disponibilité avant de charger
                if device == "cuda":
                    try:
                        import torch
                        if not torch.cuda.is_available():
                            print("[Application] [ERREUR] GPU CUDA demandé mais non disponible")
                            self.widget.root.after(0, lambda: self.widget.set_status("error"))
                            self.widget.root.after(0, self._update_status)
                            return
                        gpu_name = torch.cuda.get_device_name(0) if torch.cuda.device_count() > 0 else "GPU"
                        print(f"[Application] GPU CUDA disponible: {gpu_name}, préchargement en GPU...")
                    except ImportError:
                        print("[Application] [ERREUR] PyTorch non disponible pour le GPU")
                        self.widget.root.after(0, lambda: self.widget.set_status("error"))
                        self.widget.root.after(0, self._update_status)
                        return
                    except Exception as e:
                        print(f"[Application] [ERREUR] Erreur lors de la vérification GPU: {e}")
                        self.widget.root.after(0, lambda: self.widget.set_status("error"))
                        self.widget.root.after(0, self._update_status)
                        return
                
                # Charger le modèle (sera chargé en GPU si device="cuda" et CUDA disponible)
                success = self.transcription_service.load_whisper_model()
                
                # Mettre à jour le statut dans le thread principal
                if success:
                    # Vérifier que le modèle est bien sur GPU si demandé
                    if device == "cuda":
                        try:
                            import torch
                            if self.transcription_service.whisper_model_obj:
                                model_device = next(self.transcription_service.whisper_model_obj.parameters()).device
                                if model_device.type == "cuda":
                                    print(f"[Application] [OK] Modèle Whisper chargé avec succès sur GPU ({model_device})")
                                else:
                                    print(f"[Application] [WARNING] Modèle chargé mais sur {model_device.type} au lieu de GPU")
                        except:
                            pass
                    
                    # Sauvegarder la configuration seulement si le chargement réussit
                    try:
                        self.config.save()
                        print("[Application] Configuration sauvegardée après chargement réussi du modèle")
                    except Exception as e:
                        print(f"[Application] [WARNING] Erreur lors de la sauvegarde de la configuration: {e}")
                    
                    self.widget.root.after(0, lambda: self.widget.set_status("ok"))
                    self.widget.root.after(0, self._update_status)
                    print("[Application] [OK] Modèle Whisper chargé avec succès au démarrage")
                else:
                    print("[Application] [ERREUR] Erreur lors du chargement du modèle Whisper au démarrage")
                    self.widget.root.after(0, lambda: self.widget.set_status("error"))
                    self.widget.root.after(0, self._update_status)
            except Exception as e:
                print(f"[Application] [ERREUR] Exception lors du chargement du modèle au démarrage: {e}")
                import traceback
                traceback.print_exc()
                self.widget.root.after(0, lambda: self.widget.set_status("error"))
                self.widget.root.after(0, self._update_status)
        
        # Lancer le chargement dans un thread séparé
        thread = threading.Thread(target=load_thread, daemon=True)
        thread.start()
    
    def _open_config(self):
        """Ouvre la fenêtre de configuration."""
        # Recharger la configuration avant d'ouvrir la fenêtre
        self.config.load()
        
        # Vérifier si une fenêtre de configuration est déjà ouverte
        if hasattr(self, '_config_window') and self._config_window:
            try:
                # Vérifier si la fenêtre existe encore
                if self._config_window.root.winfo_exists():
                    # Ramener la fenêtre au premier plan
                    self._config_window.root.lift()
                    self._config_window.root.focus_force()
                    # Recharger les valeurs dans la fenêtre existante
                    self._config_window._reload_values()
                    return
            except:
                # La fenêtre n'existe plus, on peut en créer une nouvelle
                pass
        
        def on_config_saved():
            """Callback appelé après chaque sauvegarde automatique."""
            # Recharger la configuration
            self.config.load()
            
            # Mettre à jour l'enregistreur audio avec le nouveau périphérique
            if self.audio_recorder:
                device_index = self.config.get("audio.device_index")
                sample_rate = self.config.get("audio.sample_rate", 16000)
                channels = self.config.get("audio.channels", 1)
                self.audio_recorder.device_index = device_index
                self.audio_recorder.sample_rate = sample_rate
                self.audio_recorder.channels = channels
            
            # Mettre à jour le service de transcription
            # NE PAS charger le modèle ici car cela freeze l'interface
            # Le modèle sera chargé automatiquement lors de la première transcription
            mode = self.config.get("mode", "api")
            api_url = self.config.get("api.url")
            api_token = self.config.get("api.token")
            whisper_model = self.config.get("whisper.model", "base")
            
            # Si on passe en mode API et qu'un chargement est en cours, arrêter le chargement
            old_mode = self.transcription_service.mode if self.transcription_service else None
            if old_mode == "local" and mode == "api":
                if hasattr(self.transcription_service, '_loading_in_progress'):
                    if self.transcription_service._loading_in_progress:
                        print("[Application] Arrêt du chargement du modèle : passage en mode API")
                        # Le chargement sera annulé lors de la prochaine vérification dans load_whisper_model()
                        # On peut aussi réinitialiser le flag
                        self.transcription_service._loading_in_progress = False
            
            whisper_device = self.config.get("whisper.device", "cpu")
            self.transcription_service = TranscriptionService(
                mode=mode,
                api_url=api_url,
                api_token=api_token,
                whisper_model=whisper_model,
                whisper_device=whisper_device
            )
            # Ne pas charger le modèle ici - il sera chargé à la demande lors de la transcription
            # Cela évite de freeze l'interface lors de la sauvegarde de la configuration
            
            # Mettre à jour le processeur de texte avec les nouveaux mots-clés
            if self.text_processor:
                keywords = self.config.get("text_processing.keywords", {})
                self.text_processor.update_keywords(keywords)
            
            # Reconfigurer le raccourci clavier
            self._setup_hotkey()
            
            # Ne pas mettre à jour le statut depuis la fenêtre de configuration
            # car cela déclencherait validate_configuration qui chargerait le modèle en boucle
            # Le statut sera mis à jour automatiquement après le chargement du modèle ou lors de la fermeture de la fenêtre
            # self._update_status()  # Désactivé pour éviter les chargements en boucle
        
        def on_window_close():
            # Arrêter le test du microphone si actif
            if self._config_window and hasattr(self._config_window, 'test_is_recording') and self._config_window.test_is_recording:
                self._config_window._stop_test_recording()
            
            # Arrêter la capture du raccourci clavier si en cours
            if self._config_window and hasattr(self._config_window, 'hotkey_capturing') and self._config_window.hotkey_capturing:
                self._config_window._stop_hotkey_capture()
            
            # Détruire la fenêtre
            if self._config_window:
                try:
                    self._config_window.root.destroy()
                except:
                    pass
            
            # Nettoyer la référence quand la fenêtre est fermée
            self._config_window = None
            
            # Mettre à jour le statut après la fermeture de la fenêtre de configuration
            # pour s'assurer que tout est à jour
            self._update_status()
        
        self._config_window = ConfigWindow(self.config, on_save=on_config_saved, app_instance=self)
        # Intercepter la fermeture de la fenêtre
        self._config_window.root.protocol("WM_DELETE_WINDOW", on_window_close)
        self._config_window.show()
    
    def _sync_startup_setting(self):
        """Synchronise le paramètre de démarrage automatique avec le registre Windows."""
        try:
            from startup_manager import is_startup_enabled, set_startup
            config_enabled = self.config.get("startup.enabled", False)
            registry_enabled = is_startup_enabled()
            
            # Si la configuration et le registre ne correspondent pas, synchroniser
            if config_enabled != registry_enabled:
                print(f"[Application] Synchronisation du démarrage automatique: config={config_enabled}, registre={registry_enabled}")
                set_startup(config_enabled)
        except Exception as e:
            print(f"[Application] Erreur lors de la synchronisation du démarrage automatique: {e}")
    
    def _sync_startup_setting(self):
        """Synchronise le paramètre de démarrage automatique avec le registre Windows."""
        try:
            from startup_manager import is_startup_enabled, set_startup
            config_enabled = self.config.get("startup.enabled", False)
            registry_enabled = is_startup_enabled()
            
            # Si la configuration et le registre ne correspondent pas, synchroniser
            if config_enabled != registry_enabled:
                print(f"[Application] Synchronisation du démarrage automatique: config={config_enabled}, registre={registry_enabled}")
                set_startup(config_enabled)
        except Exception as e:
            print(f"[Application] Erreur lors de la synchronisation du démarrage automatique: {e}")
    
    def _quit_application(self):
        """Quitte l'application."""
        print("[Application] Arrêt de l'application...")
        
        # Arrêter le listener de raccourci clavier en premier
        if self.hotkey_listener:
            try:
                self.hotkey_listener.stop()
                self.hotkey_listener = None
            except Exception as e:
                print(f"[Application] Erreur lors de l'arrêt du hotkey listener: {e}")
        
        # Arrêter l'enregistrement si en cours
        if self.is_recording:
            try:
                # Ne pas appeler _stop_recording qui utilise root.after()
                # Arrêter directement l'enregistrement
                self.is_recording = False
                if self.audio_recorder:
                    self.audio_recorder.stop_recording()
            except Exception as e:
                print(f"[Application] Erreur lors de l'arrêt de l'enregistrement: {e}")
        
        # Fermer le widget Tkinter
        if self.widget:
            try:
                # Quitter la boucle mainloop si elle est encore active
                if self.widget.root:
                    try:
                        self.widget.root.quit()
                    except:
                        pass
                    try:
                        self.widget.destroy()
                    except:
                        pass
            except Exception as e:
                print(f"[Application] Erreur lors de la fermeture du widget: {e}")
        
        # Arrêter le System Tray
        if self.system_tray:
            try:
                self.system_tray.stop()
            except Exception as e:
                print(f"[Application] Erreur lors de l'arrêt du System Tray: {e}")
        
        print("[Application] Application fermée.")
        sys.exit(0)
    
    def run(self):
        """Lance l'application."""
        # Configurer le gestionnaire de signaux pour CTRL+C
        def signal_handler(signum, frame):
            print("\n[Application] Interruption detectee (CTRL+C), fermeture en cours...")
            # Arrêter le hotkey listener immédiatement pour éviter les erreurs
            if self.hotkey_listener:
                try:
                    self.hotkey_listener.stop()
                except:
                    pass
            
            # Quitter directement la boucle Tkinter
            if self.widget and self.widget.root:
                try:
                    self.widget.root.quit()
                except:
                    pass
            
            # Fermer proprement
            self._quit_application()
        
        signal.signal(signal.SIGINT, signal_handler)
        
        # Lancer le System Tray dans un thread séparé
        self.system_tray.run()
        
        # Le widget Tkinter DOIT s'exécuter dans le thread principal
        # Afficher le widget si nécessaire
        if self.widget.visible:
            self.widget.show()
        else:
            self.widget.hide()
        
        # Démarrer le timer du widget
        self.widget._update_timer()
        
        # Créer un mécanisme global pour forcer Tkinter à traiter les événements
        # pendant les opérations longues (comme le chargement du modèle)
        # Cela est nécessaire car whisper.load_model() peut bloquer le GIL même dans un thread
        def global_event_processor():
            """Force Tkinter à traiter les événements en attente de manière périodique."""
            try:
                # Vérifier si un chargement est en cours
                loading = (hasattr(self.transcription_service, '_loading_in_progress') and 
                          self.transcription_service._loading_in_progress)
                
                if loading:
                    # Pendant un chargement, forcer le traitement des événements plus fréquemment
                    self.widget.root.update()
                    # Programmer le prochain appel très rapidement pour maintenir la réactivité
                    self.widget.root.after(10, global_event_processor)
                else:
                    # Pas de chargement, vérifier moins fréquemment (toutes les 100ms)
                    # pour ne pas surcharger le système
                    self.widget.root.after(100, global_event_processor)
            except tk.TclError:
                # La fenêtre a été fermée, arrêter
                pass
            except Exception:
                # Autre erreur, continuer quand même
                try:
                    self.widget.root.after(100, global_event_processor)
                except:
                    pass
        
        # Démarrer le traitement périodique des événements
        self.widget.root.after(100, global_event_processor)
        
        # Vérifier si on doit charger le modèle Whisper au démarrage
        # (en mode local, charger automatiquement le modèle si la configuration est bonne)
        if (self.transcription_service.mode == "local" and 
            not self.transcription_service.is_model_loaded() and
            self.transcription_service.is_whisper_available()):
            # Vérifier si la configuration est valide avant de charger
            device = self.transcription_service.whisper_device
            should_load = True
            
            if device == "cuda":
                try:
                    import torch
                    if not torch.cuda.is_available():
                        print("[Application] [ERREUR] GPU CUDA demandé mais non disponible")
                        should_load = False
                    else:
                        gpu_name = torch.cuda.get_device_name(0) if torch.cuda.device_count() > 0 else "GPU"
                        print(f"[Application] GPU CUDA disponible: {gpu_name}, chargement du modèle en GPU...")
                except ImportError:
                    print("[Application] [ERREUR] PyTorch non disponible pour le GPU")
                    should_load = False
                except Exception as e:
                    print(f"[Application] [ERREUR] Erreur lors de la vérification GPU: {e}")
                    should_load = False
            
            if should_load:
                print("[Application] Mode local activé, chargement automatique du modèle Whisper...")
                # Mettre le statut en "loading" avec clignotement orange IMMÉDIATEMENT
                # Cela doit être fait AVANT tout autre appel qui pourrait changer le statut
                # Ne pas forcer l'affichage du widget - respecter la configuration de l'utilisateur
                self.widget.set_status("loading")
                # Forcer la mise à jour de l'affichage pour que le clignotement orange commence immédiatement
                # (seulement si le widget est visible)
                if self.widget.visible:
                    self.widget.root.update()
                # Lancer le chargement en arrière-plan après un court délai pour s'assurer que l'interface est prête
                self.widget.root.after(500, self._load_whisper_model_at_startup)
            else:
                # Configuration invalide, passer en erreur
                print("[Application] [ERREUR] Configuration invalide")
                self.widget.set_status("error")
                self._update_status()
        else:
            # Si on ne charge pas le modèle, mettre à jour le statut maintenant
            self._update_status()
        
        # Lancer la boucle principale de Tkinter (bloquant)
        # Cette boucle doit être dans le thread principal
        try:
            self.widget.root.mainloop()
        except KeyboardInterrupt:
            print("\n[Application] Interruption detectee, fermeture en cours...")
            self._quit_application()
        except Exception as e:
            print(f"[Application] Erreur dans mainloop: {e}")
            self._quit_application()


def main():
    """Point d'entrée principal."""
    try:
        app = OpenSuperWhisperApp()
        app.run()
    except Exception as e:
        print(f"Erreur fatale: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

