"""
Script de vérification et d'aide à l'installation des drivers NVIDIA.
Vérifie si un GPU NVIDIA est présent et si les drivers CUDA sont installés.
"""
import subprocess
import sys
import webbrowser
from pathlib import Path


def check_nvidia_gpu():
    """Vérifie si un GPU NVIDIA est présent."""
    try:
        result = subprocess.run(
            ['nvidia-smi'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # Extraire le nom du GPU
            lines = result.stdout.split('\n')
            for line in lines:
                if 'NVIDIA' in line and ('GeForce' in line or 'Quadro' in line or 'Tesla' in line or 'RTX' in line or 'GTX' in line):
                    return True, result.stdout
            return True, result.stdout
        return False, None
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False, None
    except Exception as e:
        print(f"[Vérification] Erreur lors de la vérification du GPU: {e}")
        return False, None


def check_cuda_drivers():
    """Vérifie si les drivers CUDA sont installés."""
    try:
        result = subprocess.run(
            ['nvidia-smi'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # Chercher la version CUDA dans la sortie
            import re
            match = re.search(r'CUDA Version: (\d+\.\d+)', result.stdout)
            if match:
                cuda_version = match.group(1)
                return True, cuda_version
            return True, "Version inconnue"
        return False, None
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False, None
    except Exception as e:
        print(f"[Vérification] Erreur lors de la vérification CUDA: {e}")
        return False, None


def open_nvidia_driver_download():
    """Ouvre la page de téléchargement des drivers NVIDIA."""
    url = "https://www.nvidia.com/Download/index.aspx"
    print(f"[Installation] Ouverture de la page de téléchargement: {url}")
    try:
        webbrowser.open(url)
        return True
    except Exception as e:
        print(f"[Installation] Erreur lors de l'ouverture du navigateur: {e}")
        return False


def main():
    """Fonction principale de vérification."""
    print("=" * 60)
    print("Vérification des drivers NVIDIA pour OpenSuperWhisper")
    print("=" * 60)
    print()
    
    # Vérifier si un GPU NVIDIA est présent
    print("[1/2] Vérification de la présence d'un GPU NVIDIA...")
    has_gpu, gpu_info = check_nvidia_gpu()
    
    if not has_gpu:
        print("[INFO] Aucun GPU NVIDIA détecté.")
        print("[INFO] L'application fonctionnera en mode CPU (plus lent mais fonctionne).")
        print()
        response = input("Voulez-vous quand même vérifier l'installation des drivers? (o/n): ")
        if response.lower() != 'o':
            return 0
    else:
        print("[OK] GPU NVIDIA détecté!")
        if gpu_info:
            # Afficher les premières lignes avec les infos GPU
            lines = gpu_info.split('\n')[:5]
            for line in lines:
                if line.strip():
                    print(f"  {line}")
        print()
    
    # Vérifier si les drivers CUDA sont installés
    print("[2/2] Vérification des drivers CUDA...")
    has_cuda, cuda_version = check_cuda_drivers()
    
    if not has_cuda:
        print("[WARNING] Les drivers CUDA ne sont pas installés ou nvidia-smi n'est pas disponible.")
        print()
        print("Pour utiliser l'accélération GPU avec Whisper, vous devez installer:")
        print("  1. Les drivers NVIDIA (GeForce Game Ready ou Studio)")
        print("  2. Les drivers doivent inclure le support CUDA")
        print()
        response = input("Voulez-vous ouvrir la page de téléchargement des drivers NVIDIA? (o/n): ")
        if response.lower() == 'o':
            open_nvidia_driver_download()
            print()
            print("[INFO] Après l'installation des drivers:")
            print("  1. Redémarrez votre ordinateur")
            print("  2. Relancez ce script pour vérifier l'installation")
            print("  3. Lancez install_cuda.py pour installer PyTorch avec CUDA")
    else:
        print(f"[OK] Drivers CUDA détectés! Version: {cuda_version}")
        print()
        print("[INFO] Les drivers CUDA sont installés.")
        print("[INFO] Vous pouvez maintenant installer PyTorch avec CUDA en exécutant:")
        print("  python install_cuda.py")
        print()
        print("[INFO] Ou manuellement:")
        print("  pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128")
    
    print()
    print("=" * 60)
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
