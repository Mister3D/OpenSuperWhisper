"""
Script d'installation automatique pour OpenSuperWhisper.
Vérifie les prérequis et installe les dépendances nécessaires.
"""
import subprocess
import sys
import os
from pathlib import Path


def check_python_version():
    """Vérifie la version de Python."""
    version = sys.version_info
    print(f"[Installation] Version Python détectée: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("[Installation] [ERREUR] Python 3.8 ou supérieur est requis!")
        return False
    
    if version.major == 3 and version.minor >= 13:
        print("[Installation] [INFO] Python 3.13+ détecté - support CUDA disponible avec PyTorch 2.9+")
    
    return True


def check_pip():
    """Vérifie si pip est disponible."""
    try:
        subprocess.run([sys.executable, "-m", "pip", "--version"], 
                      capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def install_requirements():
    """Installe les dépendances de base."""
    print("[Installation] Installation des dépendances de base...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            check=True
        )
        print("[Installation] [OK] Dépendances de base installées!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[Installation] [ERREUR] Erreur lors de l'installation: {e}")
        return False


def check_nvidia_and_install_cuda():
    """Vérifie si un GPU NVIDIA est présent et propose d'installer CUDA."""
    print()
    print("[Installation] Vérification du GPU NVIDIA...")
    
    try:
        result = subprocess.run(
            ['nvidia-smi'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print("[Installation] [OK] GPU NVIDIA détecté!")
            print()
            response = input("Voulez-vous installer PyTorch avec support CUDA pour utiliser le GPU? (o/n): ")
            if response.lower() == 'o':
                print("[Installation] Lancement de l'installation CUDA...")
                try:
                    subprocess.run([sys.executable, "install_cuda.py"], check=True)
                    print("[Installation] [OK] PyTorch avec CUDA installé!")
                    return True
                except subprocess.CalledProcessError as e:
                    print(f"[Installation] [ERREUR] Erreur lors de l'installation CUDA: {e}")
                    print("[Installation] Vous pouvez installer manuellement plus tard avec: python install_cuda.py")
                    return False
            else:
                print("[Installation] Installation CUDA ignorée. L'application utilisera le CPU.")
                return True
        else:
            print("[Installation] [INFO] Aucun GPU NVIDIA détecté. L'application utilisera le CPU.")
            return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        print("[Installation] [INFO] nvidia-smi non disponible. L'application utilisera le CPU.")
        return True
    except Exception as e:
        print(f"[Installation] [WARNING] Erreur lors de la vérification GPU: {e}")
        return True


def main():
    """Fonction principale d'installation."""
    print("=" * 60)
    print("Installation de OpenSuperWhisper")
    print("=" * 60)
    print()
    
    # Vérifier Python
    if not check_python_version():
        return 1
    
    # Vérifier pip
    if not check_pip():
        print("[Installation] [ERREUR] pip n'est pas disponible!")
        print("[Installation] Installez pip et réessayez.")
        return 1
    
    # Installer les dépendances de base
    if not install_requirements():
        return 1
    
    # Vérifier GPU et installer CUDA si demandé
    check_nvidia_and_install_cuda()
    
    print()
    print("=" * 60)
    print("[Installation] Installation terminée!")
    print("=" * 60)
    print()
    print("Pour lancer l'application:")
    print("  python main.py")
    print()
    print("Pour vérifier les drivers NVIDIA:")
    print("  python check_nvidia_drivers.py")
    print()
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[Installation] Interrompu par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        print(f"[Installation] Erreur: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
