"""
Script d'installation automatique de PyTorch avec support CUDA.
Détecte automatiquement la version CUDA disponible et installe la bonne version de PyTorch.
"""
import subprocess
import sys
import re
import platform

def get_cuda_version_from_nvidia_smi():
    """Détecte la version CUDA via nvidia-smi."""
    try:
        result = subprocess.run(['nvidia-smi'], capture_output=True, text=True, check=True)
        # Chercher la version CUDA dans la sortie
        match = re.search(r'CUDA Version: (\d+\.\d+)', result.stdout)
        if match:
            return match.group(1)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return None

def get_cuda_version_from_nvcc():
    """Détecte la version CUDA via nvcc."""
    try:
        result = subprocess.run(['nvcc', '--version'], capture_output=True, text=True, check=True)
        match = re.search(r'release (\d+\.\d+)', result.stdout)
        if match:
            return match.group(1)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return None

def detect_cuda_version():
    """Détecte la version CUDA disponible sur le système."""
    print("[Installation CUDA] Détection de la version CUDA...")
    
    # Essayer nvidia-smi d'abord (plus fiable)
    cuda_version = get_cuda_version_from_nvidia_smi()
    if cuda_version:
        print(f"[Installation CUDA] Version CUDA détectée via nvidia-smi: {cuda_version}")
        return cuda_version
    
    # Essayer nvcc en fallback
    cuda_version = get_cuda_version_from_nvcc()
    if cuda_version:
        print(f"[Installation CUDA] Version CUDA détectée via nvcc: {cuda_version}")
        return cuda_version
    
    print("[Installation CUDA] [WARNING] Impossible de détecter la version CUDA automatiquement")
    return None

def get_pytorch_cuda_versions_to_try(cuda_version):
    """Retourne une liste de versions PyTorch CUDA à essayer, de la plus récente à la plus ancienne."""
    if not cuda_version:
        return ["cu128", "cu121", "cu118"]  # Versions par défaut (cu128 supporte Python 3.13+)
    
    try:
        major, minor = map(int, cuda_version.split('.'))
        version_str = f"{major}.{minor}"
        
        # Versions CUDA supportées par PyTorch (dans l'ordre de préférence)
        # - cu128 (CUDA 12.8) - supporte Python 3.13+
        # - cu121 (CUDA 12.1)
        # - cu118 (CUDA 11.8)
        
        if major >= 13:
            # CUDA 13.x : essayer cu128 (support Python 3.13+), puis cu121 puis cu118 (compatibilité descendante)
            print(f"[Installation CUDA] [INFO] Version CUDA {version_str} très récente, essai avec cu128 (support Python 3.13+) puis cu121 puis cu118")
            return ["cu128", "cu121", "cu118"]
        elif major == 12:
            if minor >= 8:
                return ["cu128", "cu121", "cu118"]
            elif minor >= 1:
                return ["cu128", "cu121", "cu118"]
            else:
                return ["cu128", "cu121", "cu118"]  # CUDA 12.0
        elif major == 11:
            if minor >= 8:
                return ["cu128", "cu118"]
            elif minor >= 7:
                return ["cu128", "cu117", "cu118"]
            else:
                return ["cu128", "cu118"]
        else:
            # Versions anciennes : utiliser cu128 puis cu118
            print(f"[Installation CUDA] [WARNING] Version CUDA {version_str} ancienne, essai avec cu128 puis cu118")
            return ["cu128", "cu118"]
    except ValueError:
        print(f"[Installation CUDA] [WARNING] Version CUDA invalide: {cuda_version}")
        return ["cu128", "cu121", "cu118"]

def check_gpu_available():
    """Vérifie si un GPU NVIDIA est disponible."""
    try:
        result = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False

def try_install_pytorch_cuda(pytorch_cuda_version, use_nightly=False):
    """Essaie d'installer PyTorch avec une version CUDA spécifique."""
    if use_nightly:
        index_url = f"https://download.pytorch.org/whl/nightly/{pytorch_cuda_version}"
        print(f"[Installation CUDA] Tentative avec {pytorch_cuda_version} (NIGHTLY)...")
    else:
        index_url = f"https://download.pytorch.org/whl/{pytorch_cuda_version}"
        print(f"[Installation CUDA] Tentative avec {pytorch_cuda_version}...")
    print(f"[Installation CUDA] Index URL: {index_url}")
    
    # Essayer d'installer avec torchaudio d'abord
    try:
        cmd = [
            sys.executable, "-m", "pip", "install",
            "torch", "torchvision", "torchaudio",
            "--index-url", index_url,
            "--upgrade", "--no-cache-dir"
        ]
        if use_nightly:
            cmd.append("--pre")  # Permet les versions pre-release pour nightly
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"[Installation CUDA] [OK] PyTorch avec CUDA ({pytorch_cuda_version}) installé avec succès!")
        return True
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else e.stdout if e.stdout else ""
        # Vérifier si c'est parce que l'index n'existe pas ou pas de version compatible
        if "Could not find a version" in error_msg or "No matching distribution" in error_msg:
            return False
        # Si torchaudio n'est pas disponible, essayer sans
        try:
            cmd = [
                sys.executable, "-m", "pip", "install",
                "torch", "torchvision",
                "--index-url", index_url,
                "--upgrade", "--no-cache-dir"
            ]
            if use_nightly:
                cmd.append("--pre")
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            print(f"[Installation CUDA] [OK] PyTorch avec CUDA ({pytorch_cuda_version}) installé avec succès (sans torchaudio)!")
            return True
        except subprocess.CalledProcessError:
            return False

def try_install_pytorch_from_pypi_with_cuda():
    """Essaie d'installer PyTorch depuis PyPI standard - peut avoir des builds CUDA pour Python 3.13+."""
    print("[Installation CUDA] Tentative d'installation depuis PyPI standard...")
    print("[Installation CUDA] PyPI peut avoir des builds récents avec support CUDA pour Python 3.13+")
    
    # Désinstaller d'abord la version CPU
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "uninstall",
            "torch", "torchvision", "torchaudio",
            "-y"
        ], capture_output=True)
    except:
        pass
    
    # Essayer d'installer depuis PyPI avec spécification CUDA
    try:
        # Pour Python 3.13+, essayer d'abord avec cu128 (support Python 3.13+)
        cmd = [
            sys.executable, "-m", "pip", "install",
            "torch", "torchvision", "torchaudio",
            "--index-url", "https://download.pytorch.org/whl/cu128",
            "--upgrade", "--no-cache-dir"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("[Installation CUDA] [OK] PyTorch installé depuis l'index cu128 (support Python 3.13+)")
        return True
    except subprocess.CalledProcessError:
        # Essayer avec cu121
        try:
            cmd = [
                sys.executable, "-m", "pip", "install",
                "torch", "torchvision", "torchaudio",
                "--index-url", "https://download.pytorch.org/whl/cu121",
                "--upgrade", "--no-cache-dir"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            print("[Installation CUDA] [OK] PyTorch installé depuis l'index cu121")
            return True
        except subprocess.CalledProcessError:
            # Essayer avec cu118
            try:
                cmd = [
                    sys.executable, "-m", "pip", "install",
                    "torch", "torchvision", "torchaudio",
                    "--index-url", "https://download.pytorch.org/whl/cu118",
                    "--upgrade", "--no-cache-dir"
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                print("[Installation CUDA] [OK] PyTorch installé depuis l'index cu118")
                return True
            except subprocess.CalledProcessError:
            # Essayer PyPI standard (peut avoir des builds récents)
            try:
                cmd = [
                    sys.executable, "-m", "pip", "install",
                    "torch", "torchvision", "torchaudio",
                    "--upgrade", "--no-cache-dir"
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                print("[Installation CUDA] [OK] PyTorch installé depuis PyPI standard")
                # Vérifier si CUDA est disponible
                try:
                    import torch
                    if torch.cuda.is_available():
                        print("[Installation CUDA] [OK] CUDA est disponible après l'installation depuis PyPI!")
                        return True
                    else:
                        print("[Installation CUDA] [WARNING] PyTorch installé depuis PyPI mais CUDA non détecté")
                        return False
                except ImportError:
                    return False
            except subprocess.CalledProcessError as e:
                error_msg = e.stderr if e.stderr else e.stdout if e.stdout else ""
                print(f"[Installation CUDA] [ERREUR] Erreur lors de l'installation depuis PyPI: {error_msg[:200] if error_msg else 'Erreur inconnue'}")
                return False

def try_install_pytorch_cuda_from_main_index(use_nightly=False):
    """Essaie d'installer PyTorch avec CUDA depuis l'index principal."""
    if use_nightly:
        print("[Installation CUDA] Tentative d'installation depuis l'index PyTorch NIGHTLY...")
    else:
        print("[Installation CUDA] Tentative d'installation depuis l'index principal PyTorch...")
    print("[Installation CUDA] Note: PyTorch peut détecter CUDA automatiquement si les drivers sont installés")
    
    # Désinstaller d'abord la version CPU
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "uninstall",
            "torch", "torchvision", "torchaudio",
            "-y"
        ], capture_output=True)
    except:
        pass
    
    # Essayer d'installer depuis pytorch.org avec l'index CUDA 12.8 (support Python 3.13+)
    # ou CUDA 12.1 en fallback
    if use_nightly:
        index_url = "https://download.pytorch.org/whl/nightly/cu128"
        print("[Installation CUDA] Installation depuis l'index PyTorch NIGHTLY CUDA 12.8...")
    else:
        index_url = "https://download.pytorch.org/whl/cu128"
        print("[Installation CUDA] Installation depuis l'index PyTorch CUDA 12.8 (support Python 3.13+)...")
    
    try:
        cmd = [
            sys.executable, "-m", "pip", "install",
            "torch", "torchvision", "torchaudio",
            "--index-url", index_url,
            "--upgrade", "--no-cache-dir"
        ]
        if use_nightly:
            cmd.append("--pre")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("[Installation CUDA] [OK] PyTorch installé depuis l'index CUDA 12.8")
        return True
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else e.stdout if e.stdout else ""
        print(f"[Installation CUDA] [WARNING] Index CUDA 12.8 non disponible: {error_msg[:200] if error_msg else 'Erreur inconnue'}")
        # Essayer avec cu121 en fallback
        print("[Installation CUDA] Essai avec CUDA 12.1 en fallback...")
        try:
            index_url = "https://download.pytorch.org/whl/cu121" if not use_nightly else "https://download.pytorch.org/whl/nightly/cu121"
            cmd = [
                sys.executable, "-m", "pip", "install",
                "torch", "torchvision", "torchaudio",
                "--index-url", index_url,
                "--upgrade", "--no-cache-dir"
            ]
            if use_nightly:
                cmd.append("--pre")
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            print("[Installation CUDA] [OK] PyTorch installé depuis l'index CUDA 12.1")
            return True
        except subprocess.CalledProcessError:
        
        # Essayer avec l'index standard - PyTorch peut détecter CUDA automatiquement
        print("[Installation CUDA] Tentative avec l'index PyPI standard...")
        try:
            cmd = [
                sys.executable, "-m", "pip", "install",
                "torch", "torchvision", "torchaudio",
                "--upgrade", "--no-cache-dir"
            ]
            if use_nightly:
                cmd.extend(["--index-url", "https://download.pytorch.org/whl/nightly/cpu", "--pre"])
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            print("[Installation CUDA] [OK] PyTorch installé depuis PyPI")
            # Vérifier si CUDA est disponible
            try:
                import torch
                if torch.cuda.is_available():
                    print("[Installation CUDA] [OK] CUDA est disponible!")
                    return True
                else:
                    print("[Installation CUDA] [WARNING] PyTorch installé mais CUDA non détecté")
                    print("[Installation CUDA] Cela peut signifier que les drivers CUDA ne sont pas correctement installés")
                    return False
            except ImportError:
                return False
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else e.stdout if e.stdout else ""
            print(f"[Installation CUDA] [ERREUR] Erreur lors de l'installation: {error_msg[:200] if error_msg else 'Erreur inconnue'}")
            return False

def install_pytorch_cuda(pytorch_cuda_versions, try_nightly=True):
    """Installe PyTorch avec support CUDA en essayant plusieurs versions."""
    # Désinstaller d'abord les versions existantes pour éviter les conflits
    print("[Installation CUDA] Désinstallation des versions existantes de PyTorch...")
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "uninstall",
            "torch", "torchvision", "torchaudio",
            "-y"
        ], capture_output=True)  # Ignorer les erreurs si pas installé
    except:
        pass
    
    # Essayer d'abord les versions stables
    for version in pytorch_cuda_versions:
        if try_install_pytorch_cuda(version, use_nightly=False):
            return True
        print(f"[Installation CUDA] [WARNING] {version} (stable) non disponible, essai de la version suivante...")
    
    # Si les versions stables ne fonctionnent pas et qu'on peut essayer nightly
    if try_nightly:
        print("[Installation CUDA] Les versions stables ne sont pas disponibles, essai avec les builds nightly...")
        for version in pytorch_cuda_versions:
            if try_install_pytorch_cuda(version, use_nightly=True):
                return True
            print(f"[Installation CUDA] [WARNING] {version} (nightly) non disponible, essai de la version suivante...")
    
    return False

def verify_installation():
    """Vérifie que PyTorch avec CUDA est correctement installé."""
    try:
        import torch
        cuda_available = torch.cuda.is_available()
        if cuda_available:
            gpu_name = torch.cuda.get_device_name(0)
            print(f"[Installation CUDA] [OK] Vérification réussie!")
            print(f"[Installation CUDA] GPU détecté: {gpu_name}")
            print(f"[Installation CUDA] Version PyTorch: {torch.__version__}")
            return True
        else:
            print("[Installation CUDA] [WARNING] PyTorch installé mais CUDA non disponible")
            return False
    except ImportError:
        print("[Installation CUDA] [ERREUR] PyTorch n'est pas installé")
        return False

def check_python_version():
    """Vérifie la version de Python et avertit si elle est trop récente."""
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    
    print(f"[Installation CUDA] Version Python détectée: {version_str}")
    
    # PyTorch supporte généralement Python 3.8 à 3.12
    # Python 3.13+ peut ne pas avoir de builds CUDA disponibles
    if version.major == 3 and version.minor >= 13:
        print(f"[Installation CUDA] [WARNING] Python {version.major}.{version.minor} est très récent")
        print(f"[Installation CUDA] [WARNING] PyTorch peut ne pas avoir de builds CUDA officiels pour cette version")
        print(f"[Installation CUDA] [INFO] Nous allons essayer les builds nightly qui peuvent supporter Python 3.13+")
        print()
        return False
    return True

def main():
    """Fonction principale."""
    print("=" * 60)
    print("Installation automatique de PyTorch avec support CUDA")
    print("=" * 60)
    print()
    
    # Vérifier la version de Python
    python_ok = check_python_version()
    
    # Vérifier si un GPU est disponible
    if not check_gpu_available():
        print("[Installation CUDA] [WARNING] Aucun GPU NVIDIA détecté")
        print("[Installation CUDA] Installation de PyTorch en version CPU...")
        try:
            subprocess.run([
                sys.executable, "-m", "pip", "install",
                "torch", "torchvision", "torchaudio",
                "--upgrade"
            ], check=True)
            print("[Installation CUDA] [OK] PyTorch (CPU) installé avec succès!")
        except subprocess.CalledProcessError as e:
            print(f"[Installation CUDA] [ERREUR] Erreur lors de l'installation: {e}")
            sys.exit(1)
        return
    
    # Détecter la version CUDA
    cuda_version = detect_cuda_version()
    if not cuda_version:
        print("[Installation CUDA] [ERREUR] Impossible de détecter CUDA")
        print("[Installation CUDA] Installation de PyTorch en version CPU...")
        try:
            subprocess.run([
                sys.executable, "-m", "pip", "install",
                "torch", "torchvision", "torchaudio",
                "--upgrade"
            ], check=True)
            print("[Installation CUDA] [OK] PyTorch (CPU) installé avec succès!")
        except subprocess.CalledProcessError as e:
            print(f"[Installation CUDA] [ERREUR] Erreur lors de l'installation: {e}")
            sys.exit(1)
        return
    
    # Obtenir les versions PyTorch CUDA à essayer
    pytorch_cuda_versions = get_pytorch_cuda_versions_to_try(cuda_version)
    if not pytorch_cuda_versions:
        print("[Installation CUDA] [ERREUR] Impossible de déterminer les versions PyTorch CUDA à essayer")
        sys.exit(1)
    
    print(f"[Installation CUDA] Versions PyTorch CUDA à essayer: {', '.join(pytorch_cuda_versions)}")
    print()
    
    # Installer PyTorch (essayer aussi nightly si Python 3.13+)
    try_nightly = not python_ok  # Essayer nightly si Python est trop récent
    cuda_available = False
    
    if not install_pytorch_cuda(pytorch_cuda_versions, try_nightly=try_nightly):
        print("[Installation CUDA] [WARNING] Les index CUDA spécifiques ne sont pas disponibles")
        print("[Installation CUDA] Cela peut être dû à:")
        print("  - Python 3.13+ est très récent et peut ne pas avoir de builds CUDA disponibles")
        print("  - Les index PyTorch peuvent avoir changé")
        print()
        
        # Pour Python 3.13+, essayer d'abord PyPI qui peut avoir des builds récents
        if not python_ok:
            print("[Installation CUDA] Tentative depuis PyPI (peut avoir des builds pour Python 3.13+)...")
            if try_install_pytorch_from_pypi_with_cuda():
                cuda_available = True
            else:
                print("[Installation CUDA] PyPI n'a pas de builds compatibles, essai depuis l'index principal PyTorch...")
        
        # Essayer depuis l'index principal (d'abord stable, puis nightly si Python 3.13+)
        if not cuda_available:
            if try_install_pytorch_cuda_from_main_index(use_nightly=False):
                cuda_available = True
            elif try_nightly and try_install_pytorch_cuda_from_main_index(use_nightly=True):
                cuda_available = True
        
        if cuda_available:
            # Vérifier si CUDA fonctionne réellement
            try:
                import torch
                if torch.cuda.is_available():
                    print("[Installation CUDA] [OK] CUDA est disponible après l'installation!")
                    cuda_available = True
                else:
                    print("[Installation CUDA] [WARNING] PyTorch installé mais CUDA non détecté")
                    print("[Installation CUDA] Vérification des drivers CUDA...")
                    cuda_available = False
                    # Vérifier si nvidia-smi fonctionne
                    try:
                        result = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
                        if result.returncode == 0:
                            print("[Installation CUDA] [WARNING] GPU détecté mais PyTorch ne peut pas l'utiliser")
                            print("[Installation CUDA] Cela peut signifier que:")
                            print("  - PyTorch a été installé en version CPU uniquement")
                            print("  - Les drivers CUDA ne sont pas compatibles avec cette version de PyTorch")
                            print("  - Il faut installer PyTorch depuis https://pytorch.org/get-started/locally/")
                        else:
                            print("[Installation CUDA] [WARNING] GPU non détecté par nvidia-smi")
                    except:
                        pass
            except ImportError:
                cuda_available = False
        
        if not cuda_available:
            print()
            print("[Installation CUDA] [INFO] Solutions recommandées:")
            if not python_ok:
                print("  OPTION 1 (Recommandé): Utiliser Python 3.11 ou 3.12")
                print("    - Créez un nouvel environnement virtuel avec Python 3.11/3.12")
                print("    - Réinstallez les dépendances")
                print("    - Relancez ce script")
                print()
            print("  OPTION 2: Essayer les builds CUDA 12.8 manuellement (support Python 3.13+)")
            print("    pip uninstall torch torchvision torchaudio -y")
            print("    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128")
                print()
            print("  OPTION 3: Installation manuelle depuis pytorch.org")
            print("    1. Visitez https://pytorch.org/get-started/locally/")
            print("    2. Sélectionnez: Windows, pip, Python, CUDA 12.1")
            print("    3. Copiez et exécutez la commande générée")
            print()
            print("  OPTION 4: Essayer avec une version spécifique")
            print("    pip uninstall torch torchvision torchaudio -y")
            print("    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128")
            print()
            print("  OPTION 5: Continuer avec CPU (plus lent mais fonctionne)")
            print("    L'application fonctionnera mais sera plus lente pour la transcription")
    
    print()
    print("[Installation CUDA] Vérification de l'installation...")
    verify_installation()
    
    print()
    print("=" * 60)
    print("Installation terminée!")
    print("=" * 60)

if __name__ == "__main__":
    main()
