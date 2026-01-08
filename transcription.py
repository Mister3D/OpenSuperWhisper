"""
Module de transcription (mode local Whisper et mode API).
"""
import os
import requests
from typing import Optional
from pathlib import Path


class TranscriptionService:
    """Service de transcription (local ou API)."""
    
    def __init__(self, mode: str = "api", api_url: Optional[str] = None, 
                 api_token: Optional[str] = None, whisper_model: str = "base"):
        """
        Initialise le service de transcription.
        
        Args:
            mode: "local" ou "api"
            api_url: URL de l'API (requis si mode="api")
            api_token: Token Bearer pour l'API (requis si mode="api")
            whisper_model: Modèle Whisper à utiliser (si mode="local")
        """
        self.mode = mode
        self.api_url = api_url
        self.api_token = api_token
        self.whisper_model = whisper_model
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
                        
                        self.whisper_model_obj = whisper.load_model(self.whisper_model)
                        
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
                    
                    self._loading_in_progress = True
                    try:
                        self.whisper_model_obj = whisper.load_model(self.whisper_model)
                        
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
            
            # Charger l'audio avec soundfile au lieu d'utiliser ffmpeg
            try:
                import soundfile as sf
                import numpy as np
                
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
                
                # Transcrire directement avec les données audio
                result = self.whisper_model_obj.transcribe(audio_data, language="fr")
                text = result.get("text", "").strip()
                
            except ImportError:
                # Fallback: essayer avec ffmpeg si soundfile n'est pas disponible
                print("[Whisper] soundfile non disponible, tentative avec ffmpeg...")
                result = self.whisper_model_obj.transcribe(audio_file_path, language="fr")
                text = result.get("text", "").strip()
            except Exception as e:
                print(f"[Whisper] Erreur lors du chargement de l'audio avec soundfile: {e}")
                # Fallback: essayer avec ffmpeg
                print("[Whisper] Tentative avec ffmpeg...")
                result = self.whisper_model_obj.transcribe(audio_file_path, language="fr")
                text = result.get("text", "").strip()
            
            print(f"[Whisper] Transcription terminée: '{text[:50]}...' (longueur: {len(text)})")
            return text if text else None
            
        except Exception as e:
            print(f"Erreur lors de la transcription locale: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def transcribe_api(self, audio_file_path: str) -> Optional[str]:
        """
        Transcrit un fichier audio en utilisant l'API distante.
        
        Args:
            audio_file_path: Chemin vers le fichier audio WAV
        
        Returns:
            Texte transcrit ou None en cas d'erreur
        """
        if not self.api_url or not self.api_token:
            return None
        
        try:
            # Préparer les headers
            headers = {
                'Authorization': f'Bearer {self.api_token}'
            }
            
            # Préparer le fichier
            with open(audio_file_path, 'rb') as audio_file:
                files = {
                    'audio': (os.path.basename(audio_file_path), audio_file, 'audio/wav')
                }
                
                # Envoyer la requête
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
                    # Si c'est un dict avec 'message', retourner le dict complet
                    if isinstance(data, dict) and 'message' in data:
                        return data
                    # Sinon, extraire le texte
                    text = data.get('text', '') or data.get('transcription', '') or data.get('message', '')
                    if text:
                        return text
                    # Si pas de texte mais que c'est un dict, retourner le dict
                    if isinstance(data, dict):
                        return data
                except ValueError:
                    # Si ce n'est pas du JSON, prendre le texte directement
                    text = response.text.strip()
                    return text if text else None
                
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"Erreur lors de la transcription API: {e}")
            return None
        except Exception as e:
            print(f"Erreur lors de la transcription API: {e}")
            return None
    
    def transcribe(self, audio_file_path: str) -> Optional[str]:
        """
        Transcrit un fichier audio selon le mode configuré.
        
        Args:
            audio_file_path: Chemin vers le fichier audio WAV
        
        Returns:
            Texte transcrit ou None en cas d'erreur
        """
        if self.mode == "local":
            return self.transcribe_local(audio_file_path)
        elif self.mode == "api":
            return self.transcribe_api(audio_file_path)
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

