"""
Module de gestion de la configuration de l'application.
"""
import json
import os
from typing import Dict, Any, Optional
from pathlib import Path


class Config:
    """Gestionnaire de configuration de l'application."""
    
    DEFAULT_CONFIG = {
        "hotkey": {
            "ctrl": True,
            "alt": False,
            "shift": False,
            "key": "space"
        },
        "mode": "api",  # "local" ou "api"
        "api": {
            "url": "http://mister3d.fr:5001/transcribes",
            "token": ""
        },
        "audio": {
            "device_index": None,  # None = auto-détection
            "sample_rate": 16000,
            "channels": 1
        },
        "widget": {
            "visible": True,
            "position": {
                "x": 50,
                "y": 50
            }
        },
        "whisper": {
            "model": "base",  # tiny, base, small, medium, large
            "device": "cpu"  # "cpu" ou "cuda" (GPU)
        },
        "startup": {
            "enabled": False  # Démarrer l'application au démarrage de Windows
        },
        "text_processing": {
            "keywords": {}  # Dictionnaire de mots-clés et leurs remplacements (ex: {"POINT": "."})
        }
    }
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialise le gestionnaire de configuration.
        
        Args:
            config_path: Chemin vers le fichier de configuration. 
                        Si None, utilise config.json dans le répertoire de l'application.
        """
        if config_path is None:
            # Utiliser le répertoire de l'application
            app_dir = Path(__file__).parent
            config_path = app_dir / "config.json"
        
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self.load()
    
    def load(self) -> None:
        """Charge la configuration depuis le fichier."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
                # Fusionner avec les valeurs par défaut pour les nouvelles clés
                self._merge_defaults()
            except (json.JSONDecodeError, IOError) as e:
                print(f"Erreur lors du chargement de la configuration: {e}")
                self._config = self.DEFAULT_CONFIG.copy()
        else:
            self._config = self.DEFAULT_CONFIG.copy()
            self.save()
    
    def _merge_defaults(self) -> None:
        """Fusionne la configuration chargée avec les valeurs par défaut."""
        def merge_dict(default: dict, loaded: dict) -> dict:
            # Commencer par les valeurs chargées (elles ont priorité)
            result = loaded.copy()
            # Ajouter les valeurs par défaut manquantes
            for key, default_value in default.items():
                if key not in result:
                    result[key] = default_value
                elif isinstance(default_value, dict) and isinstance(result[key], dict):
                    # Fusionner récursivement les dictionnaires
                    result[key] = merge_dict(default_value, result[key])
            return result
        
        self._config = merge_dict(self.DEFAULT_CONFIG.copy(), self._config)
    
    def save(self) -> None:
        """Sauvegarde la configuration dans le fichier."""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=4, ensure_ascii=False)
        except IOError as e:
            print(f"Erreur lors de la sauvegarde de la configuration: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Récupère une valeur de configuration.
        
        Args:
            key: Clé de configuration (peut être une clé imbriquée avec des points, ex: "api.url")
            default: Valeur par défaut si la clé n'existe pas
        
        Returns:
            La valeur de configuration ou la valeur par défaut
        """
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def set(self, key: str, value: Any) -> None:
        """
        Définit une valeur de configuration.
        
        Args:
            key: Clé de configuration (peut être une clé imbriquée avec des points, ex: "api.url")
            value: Valeur à définir
        """
        keys = key.split('.')
        config = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
    
    def get_hotkey_string(self) -> str:
        """Retourne la représentation en chaîne du raccourci clavier."""
        parts = []
        if self.get("hotkey.ctrl", False):
            parts.append("Ctrl")
        if self.get("hotkey.alt", False):
            parts.append("Alt")
        if self.get("hotkey.shift", False):
            parts.append("Shift")
        parts.append(self.get("hotkey.key", "space").title())
        return "+".join(parts)
    
    def get_hotkey_tuple(self) -> tuple:
        """Retourne le raccourci clavier sous forme de tuple pour pynput."""
        modifiers = []
        if self.get("hotkey.ctrl", False):
            modifiers.append("ctrl")
        if self.get("hotkey.alt", False):
            modifiers.append("alt")
        if self.get("hotkey.shift", False):
            modifiers.append("shift")
        key = self.get("hotkey.key", "space")
        return (modifiers, key)
    
    def get_widget_position(self) -> tuple:
        """Retourne la position du widget."""
        pos = self.get("widget.position", {"x": 50, "y": 50})
        return (pos.get("x", 50), pos.get("y", 50))
    
    def set_widget_position(self, x: int, y: int) -> None:
        """Définit la position du widget."""
        self.set("widget.position", {"x": x, "y": y})
        self.save()

