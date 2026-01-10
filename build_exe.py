"""
Script de build pour créer un exécutable Windows avec PyInstaller.
"""
import subprocess
import sys
import shutil
from pathlib import Path


def check_pyinstaller():
    """Vérifie si PyInstaller est installé."""
    try:
        import PyInstaller
        return True
    except ImportError:
        return False


def install_pyinstaller():
    """Installe PyInstaller."""
    print("[Build] Installation de PyInstaller...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
        print("[Build] PyInstaller installé avec succès!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[Build] Erreur lors de l'installation de PyInstaller: {e}")
        return False


def build_exe():
    """Construit l'exécutable."""
    print("=" * 60)
    print("Build de OpenSuperWhisper en exécutable Windows")
    print("=" * 60)
    print()
    
    # Vérifier PyInstaller
    if not check_pyinstaller():
        print("[Build] PyInstaller n'est pas installé.")
        response = input("Voulez-vous l'installer maintenant? (o/n): ")
        if response.lower() == 'o':
            if not install_pyinstaller():
                print("[Build] Impossible d'installer PyInstaller. Arrêt.")
                return 1
        else:
            print("[Build] PyInstaller est requis. Arrêt.")
            return 1
    
    # Nettoyer les anciens builds
    build_dir = Path("build")
    dist_dir = Path("dist")
    spec_file = Path("OpenSuperWhisper.spec")
    
    if build_dir.exists():
        print("[Build] Nettoyage des anciens builds...")
        shutil.rmtree(build_dir)
    
    if dist_dir.exists():
        print("[Build] Nettoyage des anciennes distributions...")
        shutil.rmtree(dist_dir)
    
    # Construire avec PyInstaller
    print("[Build] Construction de l'exécutable...")
    print("[Build] Cela peut prendre plusieurs minutes...")
    print()
    
    try:
        # Utiliser le fichier .spec si disponible, sinon utiliser les options en ligne de commande
        if spec_file.exists():
            cmd = [sys.executable, "-m", "PyInstaller", str(spec_file), "--clean"]
        else:
            cmd = [
                sys.executable, "-m", "PyInstaller",
                "--name=OpenSuperWhisper",
                "--onefile",
                "--windowed",  # Pas de console (pour l'application GUI)
                "--icon=NONE",  # Ajoutez une icône si vous en avez une
                "--add-data=locales;locales",  # Inclure les fichiers de traduction
                "--add-data=refresh.svg;.",  # Inclure l'icône SVG
                "--hidden-import=whisper",
                "--hidden-import=torch",
                "--hidden-import=torchaudio",
                "--hidden-import=numpy",
                "--hidden-import=scipy",
                "--hidden-import=sounddevice",
                "--hidden-import=soundfile",
                "--hidden-import=pynput",
                "--hidden-import=pystray",
                "--hidden-import=PIL",
                "--hidden-import=sv_ttk",
                "--hidden-import=darkdetect",
                "--hidden-import=pywinstyles",
                "--hidden-import=win32api",
                "--hidden-import=win32con",
                "--hidden-import=win32gui",
                "--hidden-import=win32process",
                "--collect-all=torch",
                # Ne pas inclure --collect-all=whisper pour éviter d'inclure les modèles
                # Les modèles Whisper seront téléchargés à la demande dans ~/.cache/whisper/
                "main.py"
            ]
        
        result = subprocess.run(cmd, check=True)
        
        print()
        print("[Build] Build terminé avec succès!")
        print(f"[Build] L'exécutable se trouve dans: {dist_dir.absolute()}")
        print()
        print("[Build] Note: L'exécutable est volumineux car il inclut:")
        print("  - Python et toutes les dépendances")
        print("  - PyTorch et Whisper")
        print("  - Tous les modèles Whisper (si inclus)")
        print()
        print("[Build] Pour réduire la taille, vous pouvez:")
        print("  - Exclure les modèles Whisper non utilisés")
        print("  - Utiliser --onedir au lieu de --onefile")
        print()
        
        return 0
        
    except subprocess.CalledProcessError as e:
        print(f"[Build] Erreur lors du build: {e}")
        return 1
    except Exception as e:
        print(f"[Build] Erreur inattendue: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(build_exe())
