# OpenSuperWhisper

Application de transcription vocale (Speech-to-Text) permettant une utilisation efficace et rapide de la technologie Whisper pour convertir la voix en texte.

## Installation

1. Installer Python 3.8 ou supérieur
   - **Important** : Assurez-vous que Python est installé avec tkinter inclus (option "tcl/tk" lors de l'installation)
   - Sur Windows, tkinter devrait être inclus par défaut. Si vous obtenez une erreur `ModuleNotFoundError: No module named 'tkinter'`, réinstallez Python en cochant l'option "tcl/tk and IDLE" ou utilisez une distribution Python complète (comme Anaconda)
   - **Note Windows** : Si la commande `python` n'est pas trouvée, utilisez `py` à la place (ex: `py -m venv venv`)

2. Créer un environnement virtuel (recommandé) :
   - **Windows** :
   ```powershell
   py -m venv venv
   ```
   - **Linux/Mac** :
   ```bash
   python3 -m venv venv
   ```

3. Activer l'environnement virtuel :
   - **Windows (PowerShell)** :
   ```powershell
   venv\Scripts\Activate.ps1
   ```
   - **Windows (CMD)** :
   ```cmd
   venv\Scripts\activate.bat
   ```
   - **Linux/Mac** :
   ```bash
   source venv/bin/activate
   ```

4. Installer les dépendances :
   ```bash
   pip install -r requirements.txt
   ```

5. **Installation automatique de PyTorch avec CUDA** (optionnel, pour GPU) :
   ```bash
   python install_cuda.py
   ```
   
   Ce script :
   - ✅ Détecte automatiquement votre version CUDA (via `nvidia-smi` ou `nvcc`)
   - ✅ Installe la bonne version de PyTorch avec support CUDA
   - ✅ Vérifie que l'installation fonctionne correctement
   - ✅ Bascule automatiquement sur CPU si aucun GPU n'est détecté
   
   **Alternative manuelle** (si vous préférez) :
   ```bash
   # D'abord, vérifiez votre version CUDA : nvidia-smi
   # Puis modifiez requirements-cuda.txt avec la bonne version CUDA (cu118, cu121, etc.)
   pip install -r requirements-cuda.txt
   ```

**Note** : Si vous n'avez pas de GPU NVIDIA, le script installera automatiquement PyTorch en version CPU.

## Utilisation

Lancer l'application :
   - **Avec l'environnement virtuel activé** (recommandé) :
   ```bash
   python main.py
   ```
   - **Sans environnement virtuel (Windows)** :
   ```powershell
   py main.py
   ```
   - **Sans environnement virtuel (Linux/Mac)** :
   ```bash
   python3 main.py
   ```

L'application s'exécute en arrière-plan avec un widget flottant visible. Utilisez le raccourci clavier configuré (par défaut) pour déclencher l'enregistrement.

## Configuration

Cliquez sur l'icône dans la zone de notification (System Tray) pour accéder à l'interface de configuration.

## Installation automatique

Pour une installation complète avec vérification des drivers NVIDIA:

```bash
python installer_setup.py
```

Ce script:
- Vérifie la version de Python
- Installe toutes les dépendances
- Détecte un GPU NVIDIA et propose d'installer PyTorch avec CUDA

## Vérification des drivers NVIDIA

Pour vérifier si vos drivers NVIDIA sont installés:

```bash
python check_nvidia_drivers.py
```

Ce script vous guidera pour installer les drivers si nécessaire.

## Build d'un exécutable Windows

Pour créer un exécutable Windows (.exe):

```bash
python build_exe.py
```

Voir `BUILD_INSTRUCTIONS.md` pour les détails complets sur le build et la création d'un installateur.

## Fonctionnalités

- Enregistrement audio au maintien d'un raccourci clavier
- Transcription locale avec Whisper ou via API distante
- Support GPU NVIDIA (CUDA) pour accélération
- Insertion automatique du texte à l'emplacement du curseur
- Widget flottant avec visualisation en temps réel
- Interface de configuration intuitive

