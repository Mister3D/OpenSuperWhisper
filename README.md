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

## Fonctionnalités

- Enregistrement audio au maintien d'un raccourci clavier
- Transcription locale avec Whisper ou via API distante
- Insertion automatique du texte à l'emplacement du curseur
- Widget flottant avec visualisation en temps réel
- Interface de configuration intuitive

