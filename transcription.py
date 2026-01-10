"""
Module de transcription (mode local Whisper et mode API).
"""
import os
import requests
import numpy as np
import warnings
from typing import Optional
from pathlib import Path


class TranscriptionService:
    """Service de transcription (local ou API)."""
    
    def __init__(self, mode: str = "api", api_url: Optional[str] = None, 
                 api_token: Optional[str] = None, whisper_model: str = "base", 
                 whisper_device: str = "cpu"):
        """
        Initialise le service de transcription.
        
        Args:
            mode: "local" ou "api"
            api_url: URL de l'API (requis si mode="api")
            api_token: Token Bearer pour l'API (requis si mode="api")
            whisper_model: Modèle Whisper à utiliser (si mode="local")
            whisper_device: "cpu" ou "cuda" pour le chargement du modèle (si mode="local")
        """
        self.mode = mode
        self.api_url = api_url
        self.api_token = api_token
        self.whisper_model = whisper_model
        self.whisper_device = whisper_device
        self.whisper_model_obj = None
        self._loading_in_progress = False  # Flag pour indiquer qu'un chargement est en cours
    
    def is_whisper_available(self) -> bool:
        """Vérifie si Whisper est disponible."""
        try:
            import whisper
            return True
        except ImportError:
            return False
    
    def load_whisper_model(self, progress_callback=None) -> bool:
        """
        Charge le modèle Whisper.
        
        Args:
            progress_callback: Fonction appelée avec les messages de progression (str) pendant le téléchargement
        
        Returns:
            True si le modèle est chargé, False en cas d'erreur ou d'annulation
        """
        # Vérifier si on est toujours en mode local
        if self.mode != "local":
            print(f"[Whisper] Chargement annulé : le mode a changé vers '{self.mode}'")
            return False
        
        # Debug: afficher la configuration du device
        print(f"[Whisper] Configuration device demandée: '{self.whisper_device}'")
        
        if not self.is_whisper_available():
            print("ERREUR: Whisper n'est pas disponible. Installez-le avec: pip install openai-whisper")
            return False
        
        try:
            import whisper
            import sys
            import io
            from contextlib import redirect_stdout, redirect_stderr
            
            if self.whisper_model_obj is None:
                # Marquer qu'un chargement est en cours
                self._loading_in_progress = True
                
                print(f"[Whisper] Début du chargement du modèle '{self.whisper_model}'...")
                print(f"[Whisper] Cela peut prendre quelques instants lors du premier chargement...")
                
                # Intercepter les messages de tqdm pour extraire les Mo téléchargés
                if progress_callback:
                    # Créer un wrapper pour intercepter stdout/stderr
                    class TqdmInterceptor:
                        def __init__(self, callback):
                            self.callback = callback
                            self.buffer = ""
                        
                        def write(self, text):
                            # Capturer les messages de tqdm
                            self.buffer += text
                            # Limiter la taille du buffer pour éviter les problèmes de mémoire
                            if len(self.buffer) > 1000:
                                self.buffer = self.buffer[-500:]
                            
                            import re
                            # Pattern pour tqdm: "100%|████████████████████| 150M/150M [00:30<00:00, 5.0MB/s]"
                            # Ou: "50%|████████████          | 75M/150M [00:15<00:15, 5.0MB/s]"
                            # Chercher le pattern complet avec pourcentage et Mo
                            full_pattern = r'(\d+)%\s*\|\s*[^\|]+\|\s*(\d+(?:\.\d+)?)\s*([KMGT]?)\s*/\s*(\d+(?:\.\d+)?)\s*([KMGT]?)'
                            full_matches = re.findall(full_pattern, self.buffer)
                            if full_matches:
                                # Prendre le dernier match
                                percent, downloaded_num, downloaded_unit, total_num, total_unit = full_matches[-1]
                                try:
                                    downloaded_mo = self._convert_to_mb(f"{downloaded_num}{downloaded_unit}")
                                    total_mo = self._convert_to_mb(f"{total_num}{total_unit}")
                                    self.callback(f"{downloaded_mo:.1f} Mo / {total_mo:.1f} Mo ({percent}%)")
                                except:
                                    self.callback(f"{percent}%")
                            else:
                                # Pattern simple pour les Mo sans pourcentage
                                simple_pattern = r'(\d+(?:\.\d+)?)\s*([KMGT]?)\s*/\s*(\d+(?:\.\d+)?)\s*([KMGT]?)'
                                simple_matches = re.findall(simple_pattern, self.buffer)
                                if simple_matches:
                                    downloaded_num, downloaded_unit, total_num, total_unit = simple_matches[-1]
                                    try:
                                        downloaded_mo = self._convert_to_mb(f"{downloaded_num}{downloaded_unit}")
                                        total_mo = self._convert_to_mb(f"{total_num}{total_unit}")
                                        self.callback(f"{downloaded_mo:.1f} Mo / {total_mo:.1f} Mo")
                                    except:
                                        pass
                            
                            # Écrire aussi dans stdout pour garder la console
                            sys.__stdout__.write(text)
                            sys.__stdout__.flush()
                        
                        def flush(self):
                            sys.__stdout__.flush()
                        
                        def _convert_to_mb(self, value_str):
                            """Convertit une valeur (ex: '150M', '1.5G', '500K') en Mo."""
                            import re
                            # Nettoyer la chaîne
                            value_str = value_str.strip().upper()
                            match = re.match(r'(\d+(?:\.\d+)?)\s*([KMGT]?)', value_str)
                            if not match:
                                try:
                                    return float(value_str) / (1024 * 1024)  # Assume bytes
                                except:
                                    return 0
                            
                            num = float(match.group(1))
                            unit = match.group(2) if match.group(2) else ''
                            
                            if unit == 'K':
                                return num / 1024
                            elif unit == 'M':
                                return num
                            elif unit == 'G':
                                return num * 1024
                            elif unit == 'T':
                                return num * 1024 * 1024
                            else:
                                # Assume bytes
                                return num / (1024 * 1024)
                    
                    interceptor = TqdmInterceptor(progress_callback)
                    old_stdout = sys.stdout
                    old_stderr = sys.stderr
                    sys.stdout = interceptor
                    sys.stderr = interceptor
                    
                    try:
                        # Vérifier périodiquement si le mode a changé pendant le chargement
                        # Note: whisper.load_model() est bloquant, on ne peut pas l'interrompre facilement
                        # Mais on vérifie avant et après
                        if self.mode != "local":
                            print(f"[Whisper] Chargement annulé : le mode a changé vers '{self.mode}'")
                            self._loading_in_progress = False
                            return False
                        
                        # Déterminer le device à utiliser
                        device = self.whisper_device
                        if device == "cuda":
                            # Vérifier si CUDA est disponible
                            try:
                                import torch
                                if torch.cuda.is_available():
                                    device = "cuda"
                                    gpu_name = torch.cuda.get_device_name(0) if torch.cuda.device_count() > 0 else "GPU"
                                    print(f"[Whisper] Utilisation du GPU (CUDA): {gpu_name}")
                                else:
                                    # Vérifier pourquoi CUDA n'est pas disponible
                                    reason = "GPU non détecté ou drivers CUDA non installés"
                                    try:
                                        if torch.version.cuda is None:
                                            reason = "PyTorch compilé sans support CUDA"
                                    except:
                                        pass
                                    print(f"[Whisper] ⚠️ CUDA demandé mais non disponible ({reason}), utilisation du CPU")
                                    device = "cpu"
                            except ImportError:
                                print(f"[Whisper] ⚠️ PyTorch non disponible, utilisation du CPU")
                                device = "cpu"
                        else:
                            device = "cpu"
                            print(f"[Whisper] Utilisation du CPU")
                        
                        self.whisper_model_obj = whisper.load_model(self.whisper_model, device=device)
                        
                        # Vérifier à nouveau après le chargement
                        if self.mode != "local":
                            print(f"[Whisper] Chargement terminé mais le mode a changé vers '{self.mode}', modèle non utilisé")
                            self.whisper_model_obj = None
                            self._loading_in_progress = False
                            return False
                    finally:
                        sys.stdout = old_stdout
                        sys.stderr = old_stderr
                        self._loading_in_progress = False
                else:
                    # Vérifier si on est toujours en mode local
                    if self.mode != "local":
                        print(f"[Whisper] Chargement annulé : le mode a changé vers '{self.mode}'")
                        return False
                    
                    # Déterminer le device à utiliser
                    device = self.whisper_device
                    print(f"[Whisper] Device configuré lors du chargement: '{device}'")
                    if device == "cuda":
                        # Vérifier si CUDA est disponible
                        try:
                            import torch
                            if torch.cuda.is_available():
                                device = "cuda"
                                gpu_name = torch.cuda.get_device_name(0) if torch.cuda.device_count() > 0 else "GPU"
                                print(f"[Whisper] Utilisation du GPU (CUDA): {gpu_name}")
                            else:
                                # Vérifier pourquoi CUDA n'est pas disponible
                                reason = "GPU non détecté ou drivers CUDA non installés"
                                try:
                                    if torch.version.cuda is None:
                                        reason = "PyTorch compilé sans support CUDA"
                                except:
                                    pass
                                print(f"[Whisper] ⚠️ CUDA demandé mais non disponible ({reason}), utilisation du CPU")
                                device = "cpu"
                        except ImportError:
                            print(f"[Whisper] ⚠️ PyTorch non disponible, utilisation du CPU")
                            device = "cpu"
                    else:
                        device = "cpu"
                        print(f"[Whisper] Utilisation du CPU")
                    
                    self._loading_in_progress = True
                    try:
                        self.whisper_model_obj = whisper.load_model(self.whisper_model, device=device)
                        
                        # Vérifier à nouveau après le chargement
                        if self.mode != "local":
                            print(f"[Whisper] Chargement terminé mais le mode a changé vers '{self.mode}', modèle non utilisé")
                            self.whisper_model_obj = None
                            self._loading_in_progress = False
                            return False
                    finally:
                        self._loading_in_progress = False
                
                print(f"[Whisper] [OK] Modele '{self.whisper_model}' charge avec succes!")
            else:
                print(f"[Whisper] Le modèle '{self.whisper_model}' est déjà chargé.")
            return True
        except Exception as e:
            self._loading_in_progress = False
            print(f"[Whisper] ERREUR lors du chargement du modèle '{self.whisper_model}': {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def transcribe_local(self, audio_file_path: str) -> Optional[str]:
        """
        Transcrit un fichier audio en utilisant Whisper local.
        
        Args:
            audio_file_path: Chemin vers le fichier audio WAV
        
        Returns:
            Texte transcrit ou None en cas d'erreur
        """
        if not self.is_whisper_available():
            return None
        
        try:
            import whisper
            
            # Vérifier que le fichier existe
            if not Path(audio_file_path).exists():
                print(f"[Whisper] ERREUR: Fichier audio introuvable: {audio_file_path}")
                return None
            
            # Charger le modèle si nécessaire
            if self.whisper_model_obj is None:
                if not self.load_whisper_model():
                    return None
            
            print(f"[Whisper] Début de la transcription du fichier: {audio_file_path}")
            
            # Vérifier et forcer le device du modèle sur GPU si demandé
            # C'est crucial car Whisper vérifie model.device dans transcribe() et peut utiliser CPU même si CUDA est disponible
            if self.whisper_device == "cuda":
                try:
                    import torch
                    if torch.cuda.is_available():
                        # Vérifier que les paramètres du modèle sont sur GPU
                        model_device = next(self.whisper_model_obj.parameters()).device
                        if model_device.type != "cuda":
                            print(f"[Whisper] [WARNING] Les paramètres du modèle sont sur {model_device.type}, déplacement vers GPU...")
                            self.whisper_model_obj = self.whisper_model_obj.to("cuda")
                            model_device = next(self.whisper_model_obj.parameters()).device
                            print(f"[Whisper] Paramètres déplacés sur GPU: {model_device}")
                        
                        # CRUCIAL: Vérifier et corriger model.device (Whisper utilise model.device pour décider du device)
                        # Si model.device est CPU, Whisper utilisera CPU même si les paramètres sont sur GPU
                        if hasattr(self.whisper_model_obj, 'device'):
                            if self.whisper_model_obj.device.type != "cuda":
                                print(f"[Whisper] [WARNING] model.device est {self.whisper_model_obj.device} (devrait être cuda), correction...")
                                # Forcer le device du modèle - Whisper utilise model.device pour la détection
                                # On doit s'assurer que model.device pointe vers cuda
                                self.whisper_model_obj.device = torch.device("cuda")
                                print(f"[Whisper] model.device corrigé: {self.whisper_model_obj.device}")
                        else:
                            # Si le modèle n'a pas d'attribut device, on doit le définir
                            print(f"[Whisper] Le modèle n'a pas d'attribut device, définition...")
                            self.whisper_model_obj.device = torch.device("cuda")
                            print(f"[Whisper] model.device défini: {self.whisper_model_obj.device}")
                        
                        # Vérification finale
                        final_device = next(self.whisper_model_obj.parameters()).device
                        model_device_attr = getattr(self.whisper_model_obj, 'device', None)
                        print(f"[Whisper] Vérification finale - Paramètres: {final_device}, model.device: {model_device_attr}")
                except Exception as e:
                    print(f"[Whisper] [WARNING] Impossible de vérifier/déplacer le modèle sur GPU: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Charger l'audio avec soundfile (ffmpeg n'est pas nécessaire et peut ne pas être installé)
            # Puis passer l'array numpy à transcribe() - maintenant que model.device est correctement défini,
            # Whisper devrait utiliser le GPU
            try:
                import soundfile as sf
                import torch
                
                # Charger l'audio
                audio_data, sample_rate = sf.read(audio_file_path)
                
                # Convertir en mono si stéréo
                if len(audio_data.shape) > 1:
                    audio_data = np.mean(audio_data, axis=1)
                
                # Normaliser entre -1.0 et 1.0
                if audio_data.dtype != np.float32:
                    if audio_data.dtype == np.int16:
                        audio_data = audio_data.astype(np.float32) / 32768.0
                    elif audio_data.dtype == np.int32:
                        audio_data = audio_data.astype(np.float32) / 2147483648.0
                    else:
                        audio_data = audio_data.astype(np.float32)
                
                # Resample à 16kHz si nécessaire (Whisper attend 16kHz)
                if sample_rate != 16000:
                    from scipy import signal
                    num_samples = int(len(audio_data) * 16000 / sample_rate)
                    audio_data = signal.resample(audio_data, num_samples)
                    sample_rate = 16000
                
                print(f"[Whisper] Audio chargé: {len(audio_data)} échantillons à {sample_rate}Hz")
                
                # Déterminer si on doit utiliser FP16 (seulement sur GPU)
                fp16 = False
                if self.whisper_device == "cuda":
                    try:
                        if torch.cuda.is_available():
                            model_device = next(self.whisper_model_obj.parameters()).device
                            if model_device.type == "cuda":
                                fp16 = True
                                print(f"[Whisper] Utilisation de FP16 sur GPU pour une meilleure performance")
                    except:
                        pass
                
                # Transcrire avec l'array numpy - maintenant que model.device est correctement défini,
                # Whisper devrait utiliser le GPU automatiquement
                print(f"[Whisper] Transcription avec array numpy (modèle sur GPU)...")
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", message="FP16 is not supported on CPU")
                    result = self.whisper_model_obj.transcribe(
                        audio_data, 
                        language="fr",
                        fp16=fp16
                    )
                text = result.get("text", "").strip()
                
            except ImportError:
                # Fallback: essayer avec le chemin du fichier si soundfile n'est pas disponible
                # (nécessite ffmpeg installé)
                print("[Whisper] soundfile non disponible, utilisation directe du fichier (nécessite ffmpeg)...")
                try:
                    fp16 = False
                    if self.whisper_device == "cuda":
                        try:
                            import torch
                            if torch.cuda.is_available():
                                model_device = next(self.whisper_model_obj.parameters()).device
                                if model_device.type == "cuda":
                                    fp16 = True
                        except:
                            pass
                    with warnings.catch_warnings():
                        warnings.filterwarnings("ignore", message="FP16 is not supported on CPU")
                        result = self.whisper_model_obj.transcribe(audio_file_path, language="fr", fp16=fp16)
                    text = result.get("text", "").strip()
                except Exception as e:
                    print(f"[Whisper] Erreur lors de la transcription avec le fichier: {e}")
                    print("[Whisper] [ERREUR] ffmpeg n'est pas installé. Installez ffmpeg ou utilisez soundfile.")
                    return None
            except Exception as e:
                print(f"[Whisper] Erreur lors du chargement de l'audio avec soundfile: {e}")
                import traceback
                traceback.print_exc()
                return None
            
            print(f"[Whisper] Transcription terminée: '{text[:50]}...' (longueur: {len(text)})")
            return text if text else None
            
        except Exception as e:
            print(f"Erreur lors de la transcription locale: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def transcribe_api(self, audio_data) -> Optional[str]:
        """
        Transcrit des données audio en utilisant l'API distante.
        
        Args:
            audio_data: Tuple (audio_array, sample_rate, channels) ou chemin vers fichier audio (str)
                audio_array est un array numpy float32 normalisé entre -1.0 et 1.0
        
        Returns:
            Texte transcrit ou None en cas d'erreur
        """
        if not self.api_url or not self.api_token:
            return None
        
        try:
            import io
            import wave
            import soundfile as sf
            
            # Si audio_data est un chemin de fichier, le charger
            if isinstance(audio_data, (str, Path)):
                audio_file_path = str(audio_data)
                audio_array, sample_rate = sf.read(audio_file_path)
                
                # Convertir en mono si stéréo
                if len(audio_array.shape) > 1:
                    audio_array = np.mean(audio_array, axis=1)
                
                # Normaliser en float32
                if audio_array.dtype != np.float32:
                    if audio_array.dtype == np.int16:
                        audio_array = audio_array.astype(np.float32) / 32768.0
                    elif audio_array.dtype == np.int32:
                        audio_array = audio_array.astype(np.float32) / 2147483648.0
                    else:
                        audio_array = audio_array.astype(np.float32)
                
                channels = 1  # Toujours mono après conversion
            else:
                # audio_data est un tuple (audio_array, sample_rate, channels)
                audio_array, sample_rate, channels = audio_data
            
            # Convertir en int16 pour WAV
            audio_int16 = (audio_array * 32767).astype(np.int16)
            
            # Créer un fichier WAV en mémoire
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(2)  # 16 bits = 2 bytes
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_int16.tobytes())
            
            # Préparer les headers
            headers = {
                'Authorization': f'Bearer {self.api_token}'
            }
            
            # Préparer le fichier en mémoire
            wav_buffer.seek(0)
            files = {
                'audio': ('audio.wav', wav_buffer, 'audio/wav')
            }
            
            # Envoyer la requête
            print(f"[API] Envoi de {len(audio_array)} échantillons à l'API...")
            response = requests.post(
                self.api_url,
                headers=headers,
                files=files,
                timeout=30
            )
            
            # Vérifier la réponse
            response.raise_for_status()
            
            # Extraire le texte de la réponse
            # L'API peut retourner JSON ou texte directement
            try:
                data = response.json()
                print(f"[API] Réponse reçue: {data}")
                
                # Si c'est un dict avec 'message', extraire le message
                if isinstance(data, dict):
                    # Extraire le texte (priorité: message > text > transcription)
                    text = data.get('message', '') or data.get('text', '') or data.get('transcription', '')
                    if text:
                        return text
                    # Si pas de texte, retourner None
                    return None
            except ValueError:
                # Si ce n'est pas du JSON, prendre le texte directement
                text = response.text.strip()
                return text if text else None
            
            return None
                
        except requests.exceptions.RequestException as e:
            print(f"Erreur lors de la transcription API: {e}")
            import traceback
            traceback.print_exc()
            return None
        except Exception as e:
            print(f"Erreur lors de la transcription API: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def transcribe(self, audio_data) -> Optional[str]:
        """
        Transcrit des données audio selon le mode configuré.
        
        Args:
            audio_data: Pour mode local: chemin vers le fichier audio WAV (str)
                       Pour mode API: tuple (audio_array, sample_rate, channels)
        
        Returns:
            Texte transcrit ou None en cas d'erreur
        """
        if self.mode == "local":
            # Mode local: audio_data est un chemin de fichier
            return self.transcribe_local(audio_data)
        elif self.mode == "api":
            # Mode API: audio_data est un tuple (audio_array, sample_rate, channels)
            return self.transcribe_api(audio_data)
        else:
            return None
    
    def is_model_loaded(self) -> bool:
        """Vérifie si le modèle Whisper est chargé."""
        return self.whisper_model_obj is not None
    
    def is_model_downloaded(self) -> bool:
        """Vérifie si le modèle Whisper est téléchargé sur le disque."""
        if not self.is_whisper_available():
            return False
        
        try:
            import whisper
            import os
            from pathlib import Path
            
            # Whisper stocke les modèles dans ~/.cache/whisper/
            cache_dir = Path.home() / ".cache" / "whisper"
            model_file = cache_dir / f"{self.whisper_model}.pt"
            
            # Vérifier si le fichier existe
            return model_file.exists()
        except Exception:
            return False
    
    def validate_configuration(self, load_model: bool = False) -> tuple[bool, str]:
        """
        Valide la configuration actuelle.
        
        Args:
            load_model: Si True, charge le modèle Whisper (par défaut False pour éviter le freeze)
        
        Returns:
            Tuple (is_valid, error_message)
        """
        if self.mode == "local":
            print("[Whisper] Validation de la configuration en mode local...")
            if not self.is_whisper_available():
                print("[Whisper] ERREUR: Whisper n'est pas installé")
                return (False, "Whisper n'est pas installé. Installez-le avec: pip install openai-whisper")
            
            # Ne charger le modèle que si explicitement demandé
            if load_model:
                print(f"[Whisper] Whisper est disponible, chargement du modèle '{self.whisper_model}'...")
                if not self.load_whisper_model():
                    print("[Whisper] ERREUR: Impossible de charger le modèle")
                    return (False, "Impossible de charger le modèle Whisper")
                print("[Whisper] [OK] Configuration validee avec succes")
                return (True, "")
            else:
                # Vérifier si le modèle est chargé
                if self.is_model_loaded():
                    print("[Whisper] [OK] Whisper est disponible et le modele est charge")
                    return (True, "")
                else:
                    # En mode local, le modèle sera chargé automatiquement lors de la première transcription
                    # Ne pas considérer cela comme une erreur si Whisper est disponible
                    print("[Whisper] [WARNING] Whisper est disponible mais le modele n'est pas charge (sera charge automatiquement)")
                    return (True, "")  # Retourner True car le modèle peut être chargé à la demande
            
        elif self.mode == "api":
            if not self.api_url:
                return (False, "URL de l'API non configurée")
            if not self.api_token:
                return (False, "Token API non configuré")
            return (True, "")
        else:
            return (False, f"Mode invalide: {self.mode}")

