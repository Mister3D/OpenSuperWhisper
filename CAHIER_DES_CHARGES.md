# Cahier des Charges - OpenSuperWhisper

## 1. Vue d'ensemble du projet

### 1.1. Contexte
OpenSuperWhisper est une application de transcription vocale (Speech-to-Text) permettant une utilisation efficace et rapide de la technologie Whisper pour convertir la voix en texte. L'application fonctionne en arrière-plan et permet de transcrire la voix directement dans n'importe quelle application active.

### 1.2. Objectif principal
Créer une application de transcription vocale autonome fonctionnant en local (avec Whisper) ou via une API distante, accessible via un raccourci clavier configurable, et capable d'insérer automatiquement le texte transcrit à l'emplacement du curseur de l'utilisateur.

### 1.3. Public cible
Tous types d'utilisateurs, quel que soit leur niveau technique. L'interface doit être intuitive et l'installation simple.

---

## 2. Fonctionnalités principales

### 2.1. Détection et enregistrement audio
- **Détection automatique du microphone** : L'application doit détecter automatiquement le microphone actif du système
- **Enregistrement au déclenchement** : L'enregistrement commence lorsque le raccourci clavier configuré est **pressé et maintenu**
- **Arrêt de l'enregistrement** : L'enregistrement s'arrête lorsque le raccourci clavier est **relâché**
- **Gestion des formats audio** : 
  - **Format d'enregistrement** : L'enregistrement doit être effectué en format **WAV** pour garantir la compatibilité avec l'API
  - **Format requis pour l'API** : Les fichiers audio envoyés à l'API doivent être au format **WAV** (requis)
  - L'application doit convertir ou enregistrer directement en WAV si nécessaire
- **Feedback audio** : 
  - **Son de début** : Un son court doit être joué au démarrage de l'enregistrement
  - **Son de fin** : Un son court doit être joué à la fin de l'enregistrement
  - Les sons doivent être discrets mais audibles pour confirmer l'état de l'enregistrement

### 2.2. Modes de traitement
L'application doit supporter deux modes de traitement, **choisis manuellement par l'utilisateur** dans l'interface de configuration :

#### 2.2.1. Mode Local (Whisper)
- **Sélection manuelle** : L'utilisateur choisit explicitement le mode "Local (Whisper)" dans la configuration
- **Fonctionnement autonome** : Le traitement se fait entièrement hors ligne avec Whisper installé localement
- **Validation** : L'application doit vérifier que Whisper est disponible lorsque ce mode est sélectionné
- **Gestion d'erreur** : Si Whisper n'est pas disponible et que le mode local est sélectionné, afficher un message d'erreur clair à l'utilisateur
- **Pas de basculement automatique** : Aucun fallback automatique vers l'API, l'utilisateur doit configurer le mode souhaité

#### 2.2.2. Mode API
- **Configuration de l'URL** : L'utilisateur peut configurer l'URL de l'API dans l'interface de configuration
- **Configuration du token** : L'utilisateur peut configurer le token d'autorisation Bearer
- **Format de requête** : 
  - Méthode : POST
  - Endpoint : Configurable (exemple : `http://mister3d.fr:5001/transcribes`)
  - Headers :
    - `Authorization: Bearer {token}`
    - `Content-Type: multipart/form-data`
  - Body : Fichier audio **WAV** via `--form 'audio=@{chemin_fichier}'`
  - **Format audio requis** : L'API accepte uniquement les fichiers au format **WAV**
- **Gestion des erreurs** : Gestion des erreurs réseau et de l'API avec messages appropriés

### 2.3. Interface utilisateur

#### 2.3.1. Widget flottant (Overlay)
- **Widget minimal** : Un petit widget circulaire de **20x20 pixels** doit s'afficher par défaut à l'écran
  - Toujours au-dessus de toutes les applications (topmost)
  - Indique que OpenSuperWhisper est lancé et actif
  - Position configurable ou par défaut (coin de l'écran)
  - **Déplacement** : Le widget doit pouvoir être **déplacé** sur l'écran par glisser-déposer (drag and drop)
  - **Indicateur de statut** : Au centre du widget, un **point coloré** indique l'état de l'application :
    - **Vert** : Tout fonctionne correctement (application prête, microphone détecté, mode configuré)
    - **Rouge** : Il y a un problème ou une erreur (microphone non détecté, erreur de configuration, Whisper non disponible en mode local, erreur API, etc.)
- **Widget étendu pendant l'enregistrement** : Lorsque l'enregistrement audio est actif, le widget s'agrandit pour afficher :
  - **Waveform en temps réel** : Visualisation graphique de l'onde audio qui se met à jour en direct
  - **Timer d'enregistrement** : Affichage du temps écoulé depuis le début de l'enregistrement (format MM:SS ou HH:MM:SS)
  - Le widget étendu doit être suffisamment visible mais non intrusif
  - L'indicateur de statut (point vert/rouge) reste visible dans le widget étendu
- **Visibilité du widget** :
  - **Mode minimal** : Peut être masqué dans la configuration (option "Afficher le widget")
  - **Pendant l'enregistrement** : Le widget doit **toujours** s'afficher, même si masqué en mode normal
  - Le widget revient automatiquement en mode minimal après la fin de l'enregistrement
- **Sauvegarde de position** : La position du widget doit être sauvegardée et restaurée au redémarrage de l'application
- **Technologie** : Le widget doit être développé avec **Tkinter** pour garantir la compatibilité et la simplicité

#### 2.3.2. System Tray (Zone de notification)
- **Icône dans le System Tray** : Une icône doit être visible dans la zone de notification Windows
- **Menu contextuel** : Clic sur l'icône pour ouvrir l'interface de configuration
- **Indicateur visuel** : Indication visuelle de l'état de l'application (en attente, enregistrement en cours, traitement)

#### 2.3.3. Interface de configuration
L'interface de configuration doit permettre de configurer :
- **Raccourci clavier** : Configuration du raccourci clavier pour déclencher l'enregistrement
  - Support des combinaisons de touches (Ctrl, Alt, Shift + touche)
  - Validation de la disponibilité du raccourci
- **Mode de traitement** : **Choix manuel obligatoire** entre "Local (Whisper)" ou "API"
  - L'utilisateur doit sélectionner explicitement le mode souhaité
  - Validation de la disponibilité de Whisper si le mode local est sélectionné
  - Message d'avertissement si Whisper n'est pas disponible en mode local
- **Configuration API** (si mode API sélectionné) :
  - URL de l'API
  - Token d'autorisation Bearer
  - Test de connexion optionnel
- **Configuration audio** :
  - Sélection manuelle du microphone (optionnel, par défaut auto-détection)
  - Paramètres audio (qualité, format)
- **Configuration du widget** :
  - Option pour afficher/masquer le widget en mode minimal
  - Note : Le widget s'affichera toujours pendant l'enregistrement, même si masqué en mode normal
- **Sauvegarde des paramètres** : Les paramètres doivent être sauvegardés de manière persistante

### 2.4. Insertion automatique du texte
- **Détection de la fenêtre active** : L'application doit détecter la fenêtre où se trouve le curseur
- **Insertion du texte** : Le texte transcrit doit être automatiquement inséré à l'emplacement du curseur
- **Simulation de frappe** : Utilisation de méthodes de simulation de frappe clavier pour garantir la compatibilité avec toutes les applications (Discord, éditeurs de texte, navigateurs, etc.)
- **Gestion des erreurs** : Si l'insertion échoue, afficher une notification et/ou copier dans le presse-papiers

### 2.5. Gestion des erreurs et notifications
- **Notifications système** : Notifications pour informer l'utilisateur des événements importants :
  - Démarrage de l'enregistrement
  - Fin de l'enregistrement
  - Erreur de traitement
  - Succès de la transcription
- **Gestion des erreurs** : Messages d'erreur clairs et compréhensibles pour :
  - Erreurs réseau (mode API)
  - Erreurs de traitement (mode local)
  - Erreurs d'enregistrement audio
  - Erreurs d'insertion de texte

---

## 3. Spécifications techniques

### 3.1. Technologies et langages
- **Langage principal** : Python
- **Packaging** : L'application doit être packagée comme un logiciel professionnel (exécutable standalone, installation possible)
- **Bibliothèques suggérées** :
  - `whisper` (OpenAI) pour le traitement local
  - `pyaudio` ou `sounddevice` pour l'enregistrement audio
  - `keyboard` ou `pynput` pour la gestion des raccourcis clavier
  - `pystray` pour le System Tray
  - **`tkinter`** (inclus avec Python) pour l'interface graphique principale et le widget flottant
  - `numpy` et `matplotlib` ou `Pillow` pour la génération du waveform en temps réel
  - `pygame` ou `winsound` pour la lecture des sons de feedback
  - `requests` pour les appels API
  - `pyinstaller` ou `cx_Freeze` pour le packaging

### 3.2. Architecture
- **Architecture modulaire** : Code organisé en modules séparés :
  - Module d'enregistrement audio
  - Module de traitement (local/API)
  - Module d'interface utilisateur (Tkinter)
  - Module widget flottant (Tkinter overlay)
  - Module de configuration
  - Module d'insertion de texte
  - Module System Tray
  - Module de feedback audio (sons)

### 3.3. Performance
- **Traitement rapide** : Le traitement doit être le plus rapide possible (pas de streaming asynchrone, mais traitement efficace)
- **Optimisation** : Optimisation pour réduire la latence entre la fin de l'enregistrement et l'insertion du texte
- **Gestion mémoire** : Gestion efficace de la mémoire pour éviter les ralentissements

### 3.4. Compatibilité
- **Système d'exploitation** : Windows (priorité initiale, basé sur l'environnement de développement)
- **Applications compatibles** : Compatibilité avec toutes les applications Windows standard (Discord, navigateurs, éditeurs de texte, etc.)

---

## 4. Installation et déploiement

### 4.1. Packaging
- **Format d'installation** : Installateur Windows (.exe ou .msi)
- **Exécution locale** : Possibilité de lancer l'application sans installation (version portable)
- **Dépendances incluses** : Toutes les dépendances doivent être incluses dans le package
- **Whisper local** : Option d'inclure Whisper dans le package ou instructions pour l'installation séparée

### 4.2. Configuration initiale
- **Premier lancement** : Assistant de configuration au premier lancement
- **Configuration par défaut** : Valeurs par défaut sensées pour permettre un usage immédiat
- **Fichier de configuration** : Sauvegarde des paramètres dans un fichier de configuration (JSON, INI, ou YAML)

---

## 5. Contraintes et exigences

### 5.1. Contraintes fonctionnelles
- L'enregistrement ne doit se déclencher que lorsque le raccourci est **maintenu** (pas un simple appui)
- Le texte doit être inséré **exactement** là où se trouve le curseur
- L'application doit fonctionner en arrière-plan sans perturber l'utilisation normale de l'ordinateur

### 5.2. Contraintes techniques
- Fonctionnement autonome en mode local (sans connexion Internet)
- Gestion des erreurs robuste pour éviter les plantages
- Faible consommation de ressources système
- **Interface utilisateur** : Utilisation de **Tkinter** pour toutes les interfaces graphiques (widget flottant et interface de configuration)
- **Widget flottant** : 
  - Doit rester toujours au-dessus (topmost) de toutes les applications
  - Performance optimisée pour l'affichage du waveform en temps réel
  - Transition fluide entre mode minimal et mode étendu

### 5.3. Contraintes d'utilisation
- Interface intuitive pour tous les niveaux d'utilisateurs
- Documentation minimale nécessaire (interface auto-explicative)

---

## 6. Phases de développement

### Phase 1 : Architecture et modules de base
- Structure du projet
- Module de configuration
- Module System Tray
- Interface de configuration de base (Tkinter)
- Widget flottant minimal (20x20 pixels, toujours au-dessus)
- Indicateur de statut (point vert/rouge) au centre du widget
- Fonctionnalité de déplacement du widget (glisser-déposer)
- Sauvegarde de la position du widget

### Phase 2 : Enregistrement audio
- Détection automatique du microphone
- Module d'enregistrement audio
- Gestion du raccourci clavier (pressé/maintenu/relâché)
- Widget flottant étendu avec waveform et timer
- Module de feedback audio (sons de début/fin)

### Phase 3 : Traitement
- Intégration Whisper local
- Module API avec gestion des requêtes
- Validation du mode sélectionné (vérification de la disponibilité de Whisper si mode local)
- Gestion du mode choisi par l'utilisateur (pas de basculement automatique)

### Phase 4 : Insertion de texte
- Module d'insertion automatique de texte
- Tests de compatibilité avec différentes applications

### Phase 5 : Interface et UX
- Finalisation de l'interface de configuration
- Notifications système
- Gestion des erreurs et messages utilisateur

### Phase 6 : Packaging et distribution
- Packaging en exécutable standalone
- Création de l'installateur
- Tests d'installation et de déploiement

---

## 7. Critères d'acceptation

### 7.1. Fonctionnalités essentielles
- [ ] Détection automatique du microphone
- [ ] Enregistrement déclenché par raccourci clavier maintenu
- [ ] Arrêt d'enregistrement au relâchement du raccourci
- [ ] Widget flottant minimal (20x20 pixels) toujours au-dessus des applications
- [ ] Widget déplaçable sur l'écran (glisser-déposer)
- [ ] Indicateur de statut au centre du widget (point vert/rouge)
  - Point vert lorsque tout fonctionne correctement
  - Point rouge en cas de problème ou d'erreur
- [ ] Sauvegarde et restauration de la position du widget
- [ ] Widget étendu pendant l'enregistrement avec waveform en temps réel
- [ ] Timer d'enregistrement affiché dans le widget étendu
- [ ] Option de masquage du widget (sauf pendant l'enregistrement)
- [ ] Sons de début et fin d'enregistrement
- [ ] Sélection manuelle du mode de traitement (Local ou API) dans la configuration
- [ ] Fonctionnement en mode local (Whisper) avec validation de disponibilité
- [ ] Fonctionnement en mode API avec configuration personnalisée (URL et token)
- [ ] Message d'erreur clair si Whisper n'est pas disponible en mode local
- [ ] Insertion automatique du texte à l'emplacement du curseur
- [ ] Interface de configuration accessible via System Tray (Tkinter)
- [ ] Sauvegarde persistante des paramètres

### 7.2. Qualité
- [ ] Application stable sans plantages
- [ ] Gestion d'erreurs complète
- [ ] Performance acceptable (traitement rapide)
- [ ] Compatibilité avec les applications Windows courantes

### 7.3. Packaging
- [ ] Exécutable standalone fonctionnel
- [ ] Installateur Windows opérationnel
- [ ] Version portable disponible

---

## 8. Informations complémentaires

### 8.1. API de référence
L'API distante fonctionne selon le modèle suivant :
```bash
curl --request POST \
  --url http://mister3d.fr:5001/transcribes \
  --header 'Authorization: Bearer {token}' \
  --header 'Content-Type: multipart/form-data' \
  --form 'audio=@{chemin_fichier.wav}'
```

**Note importante** : Le fichier audio doit être au format **WAV** (.wav). L'API n'accepte que ce format.

### 8.2. Exemple de token (à remplacer par configuration utilisateur)
Token d'exemple fourni : `2h4jW8zYxL7vQgR1pBnX5K9mTp3CuAR1pBnX5K9W8zYxLR1pBnX5K9mTp3CuAR1pB`

### 8.3. Notes importantes
- Le token fourni est un exemple et doit être configurable par l'utilisateur
- L'URL de l'API doit être entièrement configurable
- La sécurité des tokens doit être prise en compte (stockage sécurisé)

---

## 9. Évolutions futures possibles

### 9.1. Fonctionnalités avancées (non prioritaires)
- Support de plusieurs langues avec détection automatique
- Historique des transcriptions
- Export des transcriptions
- Personnalisation avancée des raccourcis
- Support multi-plateforme (Linux, macOS)

---

## 10. Glossaire

- **STT** : Speech-to-Text (Reconnaissance vocale)
- **Whisper** : Modèle de transcription vocale développé par OpenAI
- **System Tray** : Zone de notification Windows (systray)
- **Bearer Token** : Token d'autorisation utilisé dans les en-têtes HTTP
- **Fallback** : Mécanisme de repli en cas d'échec

---

**Date de création** : 2024  
**Version** : 1.0  
**Statut** : En attente de validation

