# Instructions de Build et Déploiement

Ce document explique comment créer un exécutable Windows (.exe) et un installateur pour OpenSuperWhisper.

## Prérequis

1. **Python 3.8+** (recommandé: 3.11 ou 3.12 pour meilleure compatibilité)
2. **PyInstaller** (sera installé automatiquement)
3. **Toutes les dépendances** installées dans un environnement virtuel

## Étape 1: Préparation de l'environnement

```bash
# Créer un environnement virtuel
python -m venv venv

# Activer l'environnement virtuel
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Installer les dépendances
python installer_setup.py
```

## Étape 2: Vérification des drivers NVIDIA (optionnel)

Si vous voulez supporter le GPU:

```bash
python check_nvidia_drivers.py
```

Ce script:
- Vérifie si un GPU NVIDIA est présent
- Vérifie si les drivers CUDA sont installés
- Ouvre la page de téléchargement des drivers si nécessaire

## Étape 3: Build de l'exécutable

```bash
python build_exe.py
```

Cela créera un fichier `OpenSuperWhisper.exe` dans le dossier `dist/`.

**Note importante**: L'exécutable sera volumineux (plusieurs centaines de Mo) car il inclut:
- Python et toutes les dépendances
- PyTorch (avec ou sans CUDA selon ce qui est installé)
- Whisper (sans les modèles - ils seront téléchargés à la demande)
- Toutes les bibliothèques nécessaires

**Les modèles Whisper ne sont PAS inclus** - ils seront téléchargés automatiquement lors du premier usage dans `~/.cache/whisper/` (ou `%USERPROFILE%\.cache\whisper\` sur Windows).

## Étape 4: Création d'un installateur (optionnel)

### Option A: Inno Setup (Recommandé pour Windows)

1. Téléchargez et installez [Inno Setup](https://jrsoftware.org/isdl.php)

2. Créez un fichier `installer.iss`:

```iss
[Setup]
AppName=OpenSuperWhisper
AppVersion=1.0
DefaultDirName={pf}\OpenSuperWhisper
DefaultGroupName=OpenSuperWhisper
OutputDir=installer
OutputBaseFilename=OpenSuperWhisper-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin

[Files]
Source: "dist\OpenSuperWhisper.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme

[Icons]
Name: "{group}\OpenSuperWhisper"; Filename: "{app}\OpenSuperWhisper.exe"
Name: "{commondesktop}\OpenSuperWhisper"; Filename: "{app}\OpenSuperWhisper.exe"

[Run]
Filename: "{app}\OpenSuperWhisper.exe"; Description: "Lancer OpenSuperWhisper"; Flags: nowait postinstall skipifsilent
```

3. Compilez l'installateur avec Inno Setup Compiler

### Option B: NSIS (Alternative)

1. Téléchargez et installez [NSIS](https://nsis.sourceforge.io/Download)

2. Créez un script NSIS similaire

### Option C: PyInstaller avec --onedir (Plus simple)

Au lieu de `--onefile`, utilisez `--onedir` pour créer un dossier avec tous les fichiers:

```bash
pyinstaller --onedir --windowed --name=OpenSuperWhisper main.py
```

Puis créez un script batch pour lancer l'application.

## Gestion des drivers NVIDIA dans l'installateur

Pour automatiser la vérification des drivers NVIDIA dans l'installateur:

1. **Inclure check_nvidia_drivers.py** dans l'exécutable
2. **Lancer la vérification au premier démarrage** de l'application
3. **Afficher un message** si les drivers ne sont pas installés

### Modification de main.py pour vérifier au démarrage

Ajoutez ceci dans `main.py` au début de `__init__`:

```python
def __init__(self):
    """Initialise l'application."""
    # Vérifier les drivers NVIDIA au premier démarrage
    self._check_nvidia_on_first_run()
    
    self.config = Config()
    # ... reste du code

def _check_nvidia_on_first_run(self):
    """Vérifie les drivers NVIDIA au premier démarrage."""
    config = Config()
    nvidia_checked = config.get("nvidia_drivers_checked", False)
    
    if not nvidia_checked:
        try:
            import subprocess
            result = subprocess.run(['nvidia-smi'], capture_output=True, timeout=5)
            if result.returncode != 0:
                # Afficher un message à l'utilisateur
                print("[Application] GPU NVIDIA détecté mais drivers non installés.")
                print("[Application] Pour utiliser le GPU, installez les drivers NVIDIA.")
                print("[Application] L'application fonctionnera en mode CPU.")
        except:
            pass
        
        config.set("nvidia_drivers_checked", True)
        config.save()
```

## Réduction de la taille de l'exécutable

### ✅ Modèles Whisper exclus par défaut

**Les modèles Whisper ne sont PAS inclus dans l'exécutable** - ils sont téléchargés automatiquement à la demande lors du premier usage.

- Les modèles sont stockés dans `~/.cache/whisper/` (ou `%USERPROFILE%\.cache\whisper\` sur Windows)
- Le téléchargement se fait automatiquement lors du premier chargement d'un modèle
- L'utilisateur voit une barre de progression pendant le téléchargement
- Chaque modèle n'est téléchargé qu'une seule fois

**Taille des modèles Whisper** (pour référence):
- `tiny`: ~75 MB
- `base`: ~150 MB
- `small`: ~500 MB
- `medium`: ~1.5 GB
- `large`: ~3 GB

**Avantages**:
- Exécutable beaucoup plus petit (réduction de plusieurs GB)
- L'utilisateur télécharge uniquement le modèle qu'il utilise
- Mise à jour des modèles possible sans recompiler l'exécutable

### Utiliser --onedir au lieu de --onefile

`--onedir` crée un dossier avec tous les fichiers au lieu d'un seul exécutable. C'est plus rapide au démarrage et permet de partager des fichiers.

## Distribution

### Fichiers à inclure dans la distribution

1. `OpenSuperWhisper.exe` (ou le dossier avec --onedir)
2. `README.md`
3. `LICENSE` (si applicable)
4. Instructions d'installation des drivers NVIDIA (optionnel)

### Note sur PyTorch et CUDA

- Si l'utilisateur a un GPU NVIDIA, il doit installer les drivers séparément
- L'exécutable peut inclure PyTorch avec ou sans CUDA
- Pour inclure CUDA, installez PyTorch avec CUDA avant de builder
- Pour CPU uniquement, installez PyTorch standard

## Dépannage

### L'exécutable ne démarre pas

1. Vérifiez les logs dans `%TEMP%`
2. Testez avec `--console` au lieu de `--windowed` pour voir les erreurs
3. Vérifiez que toutes les dépendances sont incluses

### L'exécutable est trop volumineux

1. Utilisez `--onedir` au lieu de `--onefile`
2. Excluez les modèles Whisper non utilisés
3. Utilisez UPX pour compresser (déjà activé dans le .spec)

### Erreurs liées à PyTorch/CUDA

1. Vérifiez que la version de PyTorch correspond à la version de CUDA
2. Testez avec PyTorch CPU uniquement si CUDA pose problème
3. Incluez les DLL CUDA nécessaires si vous utilisez CUDA

## Support

Pour plus d'aide, consultez:
- [Documentation PyInstaller](https://pyinstaller.org/)
- [Documentation Inno Setup](https://jrsoftware.org/ishelp/)
- [Documentation PyTorch](https://pytorch.org/docs/stable/index.html)
