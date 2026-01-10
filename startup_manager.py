"""
Module pour gérer le démarrage automatique de l'application sous Windows.
"""
import sys
import os
from pathlib import Path


def get_app_path() -> str:
    """Retourne le chemin complet de l'exécutable de l'application."""
    if getattr(sys, 'frozen', False):
        # L'application est compilée (exe)
        return sys.executable
    else:
        # L'application est en mode développement
        # Retourner le chemin vers main.py
        app_dir = Path(__file__).parent
        python_exe = sys.executable
        main_py = app_dir / "main.py"
        return f'"{python_exe}" "{main_py}"'


def set_startup(enabled: bool) -> bool:
    """
    Active ou désactive le démarrage automatique de l'application.
    
    Args:
        enabled: True pour activer, False pour désactiver
    
    Returns:
        True si l'opération a réussi, False sinon
    """
    try:
        import winreg
        
        # Clé du registre pour le démarrage automatique
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "OpenSuperWhisper"
        
        # Ouvrir la clé du registre
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            key_path,
            0,
            winreg.KEY_SET_VALUE
        )
        
        if enabled:
            # Ajouter l'application au démarrage
            app_path = get_app_path()
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, app_path)
            print(f"[Startup] Application ajoutée au démarrage automatique: {app_path}")
        else:
            # Supprimer l'application du démarrage
            try:
                winreg.DeleteValue(key, app_name)
                print(f"[Startup] Application supprimée du démarrage automatique")
            except FileNotFoundError:
                # La valeur n'existe pas, c'est OK
                pass
        
        winreg.CloseKey(key)
        return True
        
    except ImportError:
        print("[Startup] ERREUR: Module winreg non disponible (pas sur Windows)")
        return False
    except Exception as e:
        print(f"[Startup] ERREUR lors de la modification du démarrage automatique: {e}")
        return False


def is_startup_enabled() -> bool:
    """
    Vérifie si l'application est configurée pour démarrer automatiquement.
    
    Returns:
        True si le démarrage automatique est activé, False sinon
    """
    try:
        import winreg
        
        # Clé du registre pour le démarrage automatique
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "OpenSuperWhisper"
        
        # Ouvrir la clé du registre
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            key_path,
            0,
            winreg.KEY_READ
        )
        
        try:
            # Essayer de lire la valeur
            value, _ = winreg.QueryValueEx(key, app_name)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            # La valeur n'existe pas
            winreg.CloseKey(key)
            return False
            
    except ImportError:
        return False
    except Exception as e:
        print(f"[Startup] ERREUR lors de la vérification du démarrage automatique: {e}")
        return False
