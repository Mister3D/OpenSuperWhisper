"""
Interface de configuration Tkinter.
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Optional, Callable
import threading
from pynput import keyboard
from pynput.keyboard import Key, Listener
from config import Config
from transcription import TranscriptionService


class ConfigWindow:
    """Fenêtre de configuration."""
    
    def __init__(self, config: Config, on_save: Optional[Callable] = None, app_instance=None):
        """
        Initialise la fenêtre de configuration.
        
        Args:
            config: Instance de Config
            on_save: Callback appelé après la sauvegarde
            app_instance: Instance de l'application principale (pour mettre à jour le widget)
        """
        self.config = config
        self.on_save = on_save
        self.app_instance = app_instance
        
        # Utiliser Toplevel au lieu de Tk() pour éviter les conflits avec le widget principal
        # Si app_instance existe et a un widget, utiliser sa fenêtre comme parent
        if app_instance and app_instance.widget and app_instance.widget.root:
            self.root = tk.Toplevel(app_instance.widget.root)
        else:
            # Fallback : créer une nouvelle fenêtre principale (ne devrait pas arriver normalement)
            self.root = tk.Tk()
        
        self.root.title("Configuration - OpenSuperWhisper")
        self.root.geometry("600x700")
        self.root.resizable(True, True)  # Permettre le redimensionnement
        
        # Variables - initialiser avec les valeurs de la config
        self._init_variables()
        
        # Créer le bandeau d'information en premier
        self._create_status_banner()
        
        self._create_widgets()
        self._update_mode_display()
        # Mettre à jour le bandeau après la création des widgets
        self._update_status_banner()
    
    def _init_variables(self):
        """Initialise les variables avec les valeurs de la configuration."""
        # Recharger la config pour être sûr d'avoir les dernières valeurs
        self.config.load()
        
        self.hotkey_vars = {
            'ctrl': tk.BooleanVar(value=self.config.get("hotkey.ctrl", False)),
            'alt': tk.BooleanVar(value=self.config.get("hotkey.alt", False)),
            'shift': tk.BooleanVar(value=self.config.get("hotkey.shift", False)),
            'key': tk.StringVar(value=self.config.get("hotkey.key", "space"))
        }
        self.mode_var = tk.StringVar(value=self.config.get("mode", "api"))
        self.api_url_var = tk.StringVar(value=self.config.get("api.url", ""))
        self.api_token_var = tk.StringVar(value=self.config.get("api.token", ""))
        # S'assurer que les valeurs sont bien booléennes
        widget_visible = self.config.get("widget.visible", True)
        if not isinstance(widget_visible, bool):
            widget_visible = bool(widget_visible)
        
        use_default_mic = self.config.get("audio.device_index") is None
        if not isinstance(use_default_mic, bool):
            use_default_mic = bool(use_default_mic)
        
        self.widget_visible_var = tk.BooleanVar(value=widget_visible)
        self.whisper_model_var = tk.StringVar(value=self.config.get("whisper.model", "base"))
        self.use_default_mic_var = tk.BooleanVar(value=use_default_mic)
        self.selected_device_var = tk.StringVar()
        self.device_map = {}
        
        print(f"[Configuration] Initialisation - widget_visible={widget_visible} (type: {type(widget_visible)}), use_default_mic={use_default_mic} (type: {type(use_default_mic)})")
        
        # S'assurer que device_combo existe (sera créé dans _create_audio_tab)
        self.device_combo = None
        
        # Variables pour le test du microphone en temps réel
        self.test_stream = None
        self.test_is_recording = False
        self.test_audio_buffer = []
        self._buffer_lock = threading.Lock()
        self._update_scheduled = False
        
        # Flag pour éviter les chargements multiples en parallèle
        self._model_loading_in_progress = False
        self._loading_thread = None
    
    def _reload_values(self):
        """Recharge les valeurs depuis la configuration dans les variables existantes."""
        self.config.load()
        self.hotkey_vars['ctrl'].set(self.config.get("hotkey.ctrl", False))
        self.hotkey_vars['alt'].set(self.config.get("hotkey.alt", False))
        self.hotkey_vars['shift'].set(self.config.get("hotkey.shift", False))
        self.hotkey_vars['key'].set(self.config.get("hotkey.key", "space"))
        # Mettre à jour l'affichage du raccourci
        if hasattr(self, 'hotkey_keys_frame'):
            self._update_hotkey_display()
        self.mode_var.set(self.config.get("mode", "api"))
        self.api_url_var.set(self.config.get("api.url", ""))
        self.api_token_var.set(self.config.get("api.token", ""))
        # S'assurer que les valeurs sont bien booléennes
        widget_visible = self.config.get("widget.visible", True)
        if not isinstance(widget_visible, bool):
            widget_visible = bool(widget_visible)
        
        use_default_mic = self.config.get("audio.device_index") is None
        if not isinstance(use_default_mic, bool):
            use_default_mic = bool(use_default_mic)
        
        self.widget_visible_var.set(widget_visible)
        self.whisper_model_var.set(self.config.get("whisper.model", "base"))
        self.use_default_mic_var.set(use_default_mic)
        
        print(f"[Configuration] Rechargement - widget_visible={widget_visible} (type: {type(widget_visible)}), use_default_mic={use_default_mic} (type: {type(use_default_mic)})")
        
        # Charger le nom du périphérique sélectionné si configuré
        device_index = self.config.get("audio.device_index")
        if device_index is not None:
            try:
                import sounddevice as sd
                device = sd.query_devices(device_index)
                if device['max_input_channels'] > 0:
                    self.selected_device_var.set(device['name'])
            except:
                pass
        
        self._update_mode_display()
    
    def _create_status_banner(self):
        """Crée le bandeau d'information en haut de la fenêtre."""
        # Frame pour le bandeau
        self.status_banner_frame = ttk.Frame(self.root)
        self.status_banner_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 0))
        
        # Label pour le message de statut
        self.status_banner_label = ttk.Label(
            self.status_banner_frame,
            text="",
            font=('Arial', 9),
            padding=10,
            relief=tk.RAISED,
            wraplength=580,  # Permettre le retour à la ligne (largeur fenêtre - padding)
            justify=tk.LEFT  # Alignement à gauche pour le texte multiligne
        )
        self.status_banner_label.pack(fill=tk.BOTH, expand=True)  # Permettre l'expansion verticale
    
    def _update_status_banner(self):
        """Met à jour le bandeau d'information selon le statut de l'application."""
        if not hasattr(self, 'status_banner_label') or not self.app_instance:
            return
        
        try:
            widget_status = self.app_instance.widget.status if self.app_instance.widget else "ok"
            transcription_service = self.app_instance.transcription_service
            
            if widget_status == "loading":
                message = "⏳ Chargement du modèle Whisper en cours... Le widget clignote en orange pendant le chargement."
                bg_color = '#FFF4E6'  # Orange clair
                fg_color = '#B8860B'  # Orange foncé
            elif widget_status == "error":
                # Déterminer la raison de l'erreur
                if transcription_service.mode == "local":
                    if not transcription_service.is_whisper_available():
                        message = "[ERREUR] Whisper n'est pas installe. Installez-le avec: pip install openai-whisper"
                    elif not transcription_service.is_model_loaded():
                        if transcription_service.is_model_downloaded():
                            message = "[ERREUR] Le modele Whisper est telecharge mais non charge. Cliquez sur 'Charger le modele' dans l'onglet General."
                        else:
                            message = "[ERREUR] Le modele Whisper n'est pas charge. Selectionnez un modele et cliquez sur 'Charger le modele' dans l'onglet General."
                    else:
                        message = "[ERREUR] Erreur de configuration Whisper. Verifiez les parametres dans l'onglet General."
                elif transcription_service.mode == "api":
                    if not transcription_service.api_url:
                        message = "[ERREUR] URL de l'API non configuree. Configurez l'URL dans l'onglet General."
                    elif not transcription_service.api_token:
                        message = "[ERREUR] Token API non configure. Configurez le token dans l'onglet General."
                    else:
                        message = "[ERREUR] Erreur de configuration API. Verifiez les parametres dans l'onglet General."
                else:
                    message = "[ERREUR] Erreur de configuration. Verifiez les parametres dans l'onglet General."
                bg_color = '#FFE6E6'  # Rouge clair
                fg_color = '#CC0000'  # Rouge foncé
            else:  # ok
                message = "[OK] Configuration valide. L'application est prete a etre utilisee."
                bg_color = '#E6FFE6'  # Vert clair
                fg_color = '#006600'  # Vert foncé
            
            self.status_banner_label.config(
                text=message,
                background=bg_color,
                foreground=fg_color
            )
        except Exception as e:
            print(f"Erreur lors de la mise à jour du bandeau: {e}")
            import traceback
            traceback.print_exc()
    
    def _create_widgets(self):
        """Crée les widgets de l'interface."""
        # Notebook pour les onglets
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Onglet Général
        general_frame = ttk.Frame(notebook, padding=10)
        notebook.add(general_frame, text="Général")
        self._create_general_tab(general_frame)
        
        # Onglet Audio
        audio_frame = ttk.Frame(notebook, padding=10)
        notebook.add(audio_frame, text="Audio")
        self._create_audio_tab(audio_frame)
        
        # Onglet Interface
        interface_frame = ttk.Frame(notebook, padding=10)
        notebook.add(interface_frame, text="Interface")
        self._create_interface_tab(interface_frame)
        
        # Pas de boutons - sauvegarde automatique
    
    def _create_general_tab(self, parent):
        """Crée l'onglet Général."""
        # Raccourci clavier avec nouvelle interface
        hotkey_section_frame = ttk.Frame(parent)
        hotkey_section_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Titre et description
        title_frame = ttk.Frame(hotkey_section_frame)
        title_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(title_frame, text="Toggle recording", font=('Arial', 11, 'bold')).pack(anchor=tk.W)
        ttk.Label(title_frame, text="Starts and stops recordings", font=('Arial', 9), foreground='gray').pack(anchor=tk.W)
        
        # Frame pour le bouton Changer et l'affichage des touches
        hotkey_display_frame = ttk.Frame(hotkey_section_frame)
        hotkey_display_frame.pack(fill=tk.X, pady=5)
        
        # Bouton "Changer"
        self.hotkey_change_button = ttk.Button(
            hotkey_display_frame,
            text="Changer",
            command=self._start_hotkey_capture
        )
        self.hotkey_change_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Frame pour afficher les touches (style pilules)
        self.hotkey_keys_frame = ttk.Frame(hotkey_display_frame)
        self.hotkey_keys_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Variables pour la capture du raccourci
        self.hotkey_capturing = False
        self.hotkey_listener = None
        self.captured_modifiers = []
        self.captured_key = None
        
        # Initialiser l'affichage des touches
        self._update_hotkey_display()
        
        # Sauvegarder automatiquement quand les variables changent (pour compatibilité)
        self.hotkey_vars['ctrl'].trace('w', lambda *args: [self._update_hotkey_display(), self._auto_save()])
        self.hotkey_vars['alt'].trace('w', lambda *args: [self._update_hotkey_display(), self._auto_save()])
        self.hotkey_vars['shift'].trace('w', lambda *args: [self._update_hotkey_display(), self._auto_save()])
        self.hotkey_vars['key'].trace('w', lambda *args: [self._update_hotkey_display(), self._auto_save()])
        
        # Sélection du modèle Whisper (visible avant de choisir le mode)
        whisper_model_frame = ttk.LabelFrame(parent, text="Modèle Whisper (si mode Local)", padding=10)
        whisper_model_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(whisper_model_frame, text="Taille du modèle:").pack(anchor=tk.W, pady=2)
        model_combo = ttk.Combobox(
            whisper_model_frame,
            textvariable=self.whisper_model_var,
            values=["tiny", "base", "small", "medium", "large"],
            state="readonly",
            width=20
        )
        model_combo.pack(anchor=tk.W, pady=2)
        model_combo.bind('<<ComboboxSelected>>', lambda e: [self._auto_save(), self._on_model_changed()])
        
        ttk.Label(
            whisper_model_frame,
            text="Note: Les modèles plus grands sont plus précis mais plus lents.",
            font=('Arial', 8),
            foreground='gray'
        ).pack(anchor=tk.W, pady=5)
        
        # Mode de traitement
        ttk.Label(parent, text="Mode de traitement:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(0, 5))
        
        mode_frame = ttk.Frame(parent)
        mode_frame.pack(fill=tk.X, pady=5)
        
        ttk.Radiobutton(
            mode_frame,
            text="Local (Whisper)",
            variable=self.mode_var,
            value="local",
            command=lambda: [self._update_mode_display(), self._auto_save()]
        ).pack(anchor=tk.W, pady=2)
        
        ttk.Radiobutton(
            mode_frame,
            text="API distante",
            variable=self.mode_var,
            value="api",
            command=lambda: [self._update_mode_display(), self._auto_save()]
        ).pack(anchor=tk.W, pady=2)
        
        # Validation Whisper avec indicateur de chargement
        self.whisper_status_label = ttk.Label(parent, text="", foreground='red')
        self.whisper_status_label.pack(anchor=tk.W, pady=5)
        
        # Progress bar pour le chargement du modèle
        self.whisper_progress = ttk.Progressbar(parent, mode='indeterminate', length=300)
        self.whisper_progress.pack(anchor=tk.W, pady=5)
        self.whisper_progress.pack_forget()  # Caché par défaut
        
        if self.mode_var.get() == "local":
            self._check_whisper()
            # Mettre à jour l'état du bouton après un court délai pour laisser le temps à l'interface de se créer
            self.root.after(100, self._update_load_model_button)
        
        # Configuration API
        self.api_frame = ttk.LabelFrame(parent, text="Configuration API", padding=10)
        self.api_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        ttk.Label(self.api_frame, text="URL de l'API:").pack(anchor=tk.W, pady=2)
        api_url_entry = ttk.Entry(self.api_frame, textvariable=self.api_url_var, width=50)
        api_url_entry.pack(fill=tk.X, pady=2)
        api_url_entry.bind('<FocusOut>', lambda e: self._auto_save())
        
        ttk.Label(self.api_frame, text="Token Bearer:").pack(anchor=tk.W, pady=(10, 2))
        api_token_entry = ttk.Entry(self.api_frame, textvariable=self.api_token_var, width=50, show="*")
        api_token_entry.pack(fill=tk.X, pady=2)
        api_token_entry.bind('<FocusOut>', lambda e: self._auto_save())
        
        ttk.Button(self.api_frame, text="Tester la connexion", command=self._test_api).pack(anchor=tk.W, pady=5)
        ttk.Button(self.api_frame, text="Test avec fichier audio", command=self._test_with_file).pack(anchor=tk.W, pady=5)
        
        # Configuration Whisper
        self.whisper_frame = ttk.LabelFrame(parent, text="Configuration Whisper", padding=10)
        self.whisper_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Note: Le modèle est maintenant sélectionné avant les boutons radio
        ttk.Label(
            self.whisper_frame,
            text="Le modèle Whisper peut être sélectionné dans la section 'Modèle Whisper' ci-dessus.",
            font=('Arial', 9),
            foreground='gray'
        ).pack(anchor=tk.W, pady=5)
        
        # Bouton pour charger le modèle
        self.load_model_button = ttk.Button(
            self.whisper_frame,
            text="[ERREUR] Charger le modele",
            command=self._load_whisper_model_async
        )
        self.load_model_button.pack(anchor=tk.W, pady=10)
        
        # Mettre à jour l'état du bouton
        self._update_load_model_button()
        
        ttk.Button(self.whisper_frame, text="Test avec fichier audio", command=self._test_with_file).pack(anchor=tk.W, pady=10)
    
    def _create_audio_tab(self, parent):
        """Crée l'onglet Audio."""
        ttk.Label(parent, text="Configuration audio", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(0, 10))
        
        # Case à cocher pour utiliser le microphone par défaut
        default_mic_checkbox = ttk.Checkbutton(
            parent,
            text="Microphone par défaut du système",
            variable=self.use_default_mic_var,
            command=lambda: self._on_default_mic_changed()
        )
        default_mic_checkbox.pack(anchor=tk.W, pady=10)
        
        # Frame pour la sélection manuelle
        self.manual_device_frame = ttk.Frame(parent)
        self.manual_device_frame.pack(fill=tk.X, pady=5)
        
        # Frame pour le label et le bouton actualiser
        device_header_frame = ttk.Frame(self.manual_device_frame)
        device_header_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(device_header_frame, text="Sélectionner un microphone:", font=('Arial', 9)).pack(side=tk.LEFT, anchor=tk.W)
        
        # Bouton pour actualiser la liste
        refresh_button = ttk.Button(
            device_header_frame,
            text="Actualiser",
            command=self._refresh_audio_devices_list
        )
        refresh_button.pack(side=tk.RIGHT, padx=5)
        
        # Liste déroulante des périphériques
        self.device_combo = ttk.Combobox(
            self.manual_device_frame,
            textvariable=self.selected_device_var,
            state="readonly",
            width=60
        )
        self.device_combo.pack(fill=tk.X, pady=5)
        self.device_combo.bind('<<ComboboxSelected>>', self._on_device_selected)
        
        # Bouton de test
        self.test_button = ttk.Button(
            self.manual_device_frame,
            text="Tester le microphone",
            command=self._test_microphone
        )
        self.test_button.pack(anchor=tk.W, pady=5)
        
        # Canvas pour afficher le waveform
        self.test_waveform_canvas = tk.Canvas(
            self.manual_device_frame,
            width=400,
            height=100,
            bg='#2C2C2C',
            highlightthickness=1,
            highlightbackground='#666666'
        )
        self.test_waveform_canvas.pack(fill=tk.X, pady=5)
        
        # Label pour le statut du test
        self.test_status_label = ttk.Label(self.manual_device_frame, text="", font=('Arial', 9))
        self.test_status_label.pack(anchor=tk.W, pady=5)
        
        # Charger les périphériques et mettre à jour l'affichage
        self._load_audio_devices_list()
        # Mettre à jour l'état initial (après création de device_combo)
        use_default = bool(self.use_default_mic_var.get())
        print(f"[Configuration] État initial microphone: use_default={use_default} (type: {type(use_default)})")
        if use_default:
            if self.device_combo is not None:
                self.device_combo.config(state="disabled")
                print("[Configuration] Liste désactivée au démarrage")
        else:
            if self.device_combo is not None:
                self.device_combo.config(state="readonly")
                print("[Configuration] Liste activée au démarrage")
    
    def _create_interface_tab(self, parent):
        """Crée l'onglet Interface."""
        ttk.Label(parent, text="Configuration de l'interface", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(0, 10))
        
        widget_checkbox = ttk.Checkbutton(
            parent,
            text="Afficher le widget flottant (sera toujours visible pendant l'enregistrement)",
            variable=self.widget_visible_var,
            command=lambda: self._on_widget_visible_changed()
        )
        widget_checkbox.pack(anchor=tk.W, pady=10)
    
    def _refresh_audio_devices_list(self):
        """Actualise la liste des périphériques audio."""
        self._load_audio_devices_list()
        # Réactiver la combobox si elle était désactivée
        if not self.use_default_mic_var.get():
            self.device_combo.config(state="readonly")
    
    def _load_audio_devices_list(self):
        """Charge la liste des périphériques audio dans la combobox."""
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            device_names = []
            self.device_map = {}  # Map nom -> index
            
            for i, device in enumerate(devices):
                if device['max_input_channels'] > 0:
                    device_name = device['name']
                    device_names.append(device_name)
                    self.device_map[device_name] = i
            
            self.device_combo['values'] = device_names
            
            # Sélectionner le périphérique actuel si configuré
            current_device_index = self.config.get("audio.device_index")
            if current_device_index is not None:
                try:
                    current_device = sd.query_devices(current_device_index)
                    if current_device['max_input_channels'] > 0:
                        self.selected_device_var.set(current_device['name'])
                except:
                    pass
        except Exception as e:
            print(f"Erreur lors du chargement des périphériques: {e}")
    
    def _on_default_mic_changed(self):
        """Appelé quand la case "Microphone par défaut" change."""
        try:
            use_default = bool(self.use_default_mic_var.get())
            print(f"[Configuration] Microphone par défaut changé: {use_default} (type: {type(use_default)})")
            
            if use_default:
                # Désactiver la sélection manuelle
                if self.device_combo is not None:
                    self.device_combo.config(state="disabled")
                    print(f"[Configuration] Liste désactivée (état après: {self.device_combo.cget('state')})")
                else:
                    print("[Configuration] ERREUR: device_combo n'existe pas!")
                # Sauvegarder None pour utiliser le défaut
                self.config.set("audio.device_index", None)
                self.config.save()
                print("[Configuration] Microphone par défaut activé et sauvegardé")
            else:
                # Activer la sélection manuelle
                if self.device_combo is not None:
                    print(f"[Configuration] Avant activation - état: {self.device_combo.cget('state')}")
                    self.device_combo.config(state="readonly")
                    print(f"[Configuration] Après activation - état: {self.device_combo.cget('state')}")
                    # Forcer la mise à jour de l'interface
                    self.root.update_idletasks()  # Utiliser update_idletasks au lieu de update
                    # Si aucun périphérique n'est sélectionné, sélectionner le premier
                    if not self.selected_device_var.get() and self.device_combo['values']:
                        self.selected_device_var.set(self.device_combo['values'][0])
                        self._on_device_selected()
                else:
                    print("[Configuration] ERREUR: device_combo n'existe pas!")
                print("[Configuration] Sélection manuelle activée")
            
            # Recharger les composants si callback disponible
            if self.on_save:
                self.on_save()
        except Exception as e:
            print(f"[Configuration] Erreur dans _on_default_mic_changed: {e}")
            import traceback
            traceback.print_exc()
    
    def _on_device_selected(self, event=None):
        """Appelé quand un périphérique est sélectionné."""
        device_name = self.selected_device_var.get()
        if device_name and device_name in self.device_map:
            device_index = self.device_map[device_name]
            self.config.set("audio.device_index", device_index)
            self.config.save()
            
            # Recharger les composants si callback disponible
            if self.on_save:
                self.on_save()
    
    def _test_microphone(self):
        """Teste le microphone sélectionné et affiche le waveform en temps réel."""
        import sounddevice as sd
        import numpy as np
        
        # Si on est déjà en train d'enregistrer, arrêter
        if self.test_is_recording:
            self._stop_test_recording()
            return
        
        # Déterminer le périphérique à tester
        if self.use_default_mic_var.get():
            device_index = None
            device_name = "microphone par défaut"
        else:
            device_name = self.selected_device_var.get()
            if not device_name or device_name not in self.device_map:
                self.test_status_label.config(text="[ERREUR] Aucun microphone selectionne", foreground='red')
                return
            device_index = self.device_map[device_name]
        
        # Initialiser le buffer audio
        self.test_audio_buffer = []
        self.test_is_recording = True
        
        # Changer le texte du bouton
        self.test_button.config(text="⏸ Arrêter le test", state="normal")
        self.test_status_label.config(text="⏳ Enregistrement en cours... Cliquez sur 'Arrêter le test' pour arrêter.", foreground='blue')
        
        # Effacer le canvas et afficher un message initial
        self.test_waveform_canvas.delete("all")
        self.test_waveform_canvas.create_text(
            200, 50,
            text="Enregistrement en cours...",
            fill='#FFFFFF',
            font=('Arial', 10)
        )
        
        # Fonction callback pour recevoir les données audio en temps réel
        def audio_callback(indata, frames, time, status):
            if status:
                print(f"Status audio: {status}")
            if self.test_is_recording:
                try:
                    # Ajouter les données au buffer de manière thread-safe
                    audio_chunk = indata.copy().flatten()
                    with self._buffer_lock:
                        self.test_audio_buffer.extend(audio_chunk)
                        # Garder seulement les dernières 16000 échantillons (1 seconde à 16kHz)
                        if len(self.test_audio_buffer) > 16000:
                            self.test_audio_buffer = self.test_audio_buffer[-16000:]
                except Exception as e:
                    print(f"Erreur dans audio_callback: {e}")
        
        try:
            # Démarrer le stream audio
            sample_rate = 16000
            self.test_stream = sd.InputStream(
                samplerate=sample_rate,
                channels=1,
                device=device_index,
                dtype=np.float32,
                callback=audio_callback,
                blocksize=1024
            )
            self.test_stream.start()
            
            # Démarrer la mise à jour du graphique
            self._update_test_waveform_live()
            
        except Exception as e:
            self.test_is_recording = False
            self.test_button.config(text="Tester le microphone", state="normal")
            self._on_test_error(str(e))
    
    def _stop_test_recording(self):
        """Arrête l'enregistrement du test."""
        import numpy as np
        
        self.test_is_recording = False
        
        if self.test_stream:
            try:
                self.test_stream.stop()
                self.test_stream.close()
            except:
                pass
            self.test_stream = None
        
        # Réactiver le bouton
        self.test_button.config(text="Tester le microphone", state="normal")
        
        # Analyser les données capturées
        if self.test_audio_buffer:
            audio_data = np.array(self.test_audio_buffer)
            max_level = np.max(np.abs(audio_data))
            
            if max_level > 0.001:
                self.test_status_label.config(
                    text=f"[OK] Test termine ! Microphone fonctionnel (Niveau max: {max_level:.3f})",
                    foreground='green'
                )
            else:
                self.test_status_label.config(
                    text="[WARNING] Test termine. Microphone fonctionnel mais aucun signal detecte.",
                    foreground='orange'
                )
        else:
            self.test_status_label.config(
                text="[WARNING] Aucune donnee capturee.",
                foreground='orange'
            )
    
    def _update_test_waveform_live(self):
        """Met à jour le waveform en temps réel."""
        import numpy as np
        
        if not self.test_is_recording:
            self._update_scheduled = False
            return
        
        try:
            # Vérifier que _buffer_lock existe (sécurité)
            if not hasattr(self, '_buffer_lock'):
                self._buffer_lock = threading.Lock()
            
            # Dessiner le waveform avec les données actuelles
            with self._buffer_lock:
                if self.test_audio_buffer:
                    # Copier le buffer pour éviter les problèmes de thread
                    buffer_copy = list(self.test_audio_buffer)
                else:
                    buffer_copy = []
            
            if buffer_copy:
                self._draw_test_waveform_live(np.array(buffer_copy))
            
            # Programmer la prochaine mise à jour (toutes les 100ms pour éviter le freeze)
            if self.test_is_recording and not self._update_scheduled:
                self._update_scheduled = True
                self.root.after(100, lambda: [setattr(self, '_update_scheduled', False), self._update_test_waveform_live()])
        except Exception as e:
            print(f"Erreur dans _update_test_waveform_live: {e}")
            import traceback
            traceback.print_exc()
            # Arrêter la mise à jour en cas d'erreur
            self.test_is_recording = False
            self._update_scheduled = False
    
    def _on_test_error(self, error_msg):
        """Appelé quand le test échoue."""
        # Arrêter l'enregistrement si actif
        self.test_is_recording = False
        if self.test_stream:
            try:
                self.test_stream.stop()
                self.test_stream.close()
            except:
                pass
            self.test_stream = None
        
        # Réactiver le bouton
        self.test_button.config(text="Tester le microphone", state="normal")
        
        # Effacer le canvas
        self.test_waveform_canvas.delete("all")
        self.test_waveform_canvas.create_text(
            200, 50,
            text="Erreur",
            fill='#FF0000',
            font=('Arial', 10, 'bold')
        )
        
        # Afficher l'erreur
        self.test_status_label.config(text=f"[ERREUR] Erreur: {error_msg}", foreground='red')
    
    def _draw_test_waveform_live(self, audio_data):
        """Dessine le waveform en temps réel sur le canvas de test."""
        import numpy as np
        
        self.test_waveform_canvas.delete("all")
        
        if len(audio_data) == 0:
            return
        
        # Normaliser les données audio
        max_val = np.max(np.abs(audio_data))
        if max_val > 0:
            normalized_data = audio_data / max_val
        else:
            normalized_data = audio_data
        
        # Dimensions du canvas
        canvas_width = 400
        canvas_height = 100
        padding = 10
        
        # Dessiner la ligne de référence (zéro)
        center_y = canvas_height // 2
        self.test_waveform_canvas.create_line(
            padding, center_y,
            canvas_width - padding, center_y,
            fill='#666666',
            width=1
        )
        
        # Dessiner le waveform
        num_points = len(normalized_data)
        if num_points > 0:
            # Réduire le nombre de points pour l'affichage (échantillonnage)
            display_width = canvas_width - 2 * padding
            step = max(1, num_points // display_width)
            points = []
            
            for i in range(0, num_points, step):
                x = padding + int((i / num_points) * display_width)
                y = center_y - int(normalized_data[i] * (canvas_height // 2 - padding))
                points.append((x, y))
            
            # Dessiner la ligne du waveform
            if len(points) > 1:
                for i in range(len(points) - 1):
                    self.test_waveform_canvas.create_line(
                        points[i][0], points[i][1],
                        points[i + 1][0], points[i + 1][1],
                        fill='#00FF00',
                        width=2
                    )
        
        # Ajouter un titre et le niveau actuel
        max_level = np.max(np.abs(audio_data))
        title_text = f"Waveform audio (Niveau: {max_level:.3f})"
        self.test_waveform_canvas.create_text(
            canvas_width // 2, 15,
            text=title_text,
            fill='#FFFFFF',
            font=('Arial', 9)
        )
    
    def _update_mode_display(self):
        """Met à jour l'affichage selon le mode sélectionné."""
        if self.mode_var.get() == "local":
            self.api_frame.pack_forget()
            self.whisper_frame.pack(fill=tk.BOTH, expand=True, pady=10)
            self._check_whisper()
            # Mettre à jour l'état du bouton
            self.root.after(100, self._update_load_model_button)
        else:
            # Si on passe en mode API, arrêter le chargement du modèle si en cours
            if self._model_loading_in_progress:
                print("[Configuration] Arrêt du chargement du modèle : passage en mode API")
                # Réinitialiser le flag
                self._model_loading_in_progress = False
                # Mettre à jour le statut immédiatement
                if hasattr(self, 'whisper_status_label'):
                    self.whisper_status_label.config(
                        text="[WARNING] Chargement annule : passage en mode API",
                        foreground='orange'
                    )
                if hasattr(self, 'load_model_button'):
                    self.load_model_button.config(text="❌ Charger le modèle", state="normal")
            
            # Arrêter aussi le chargement dans le service de transcription
            if self.app_instance and self.app_instance.transcription_service:
                if hasattr(self.app_instance.transcription_service, '_loading_in_progress'):
                    if self.app_instance.transcription_service._loading_in_progress:
                        print("[Configuration] Arrêt du chargement dans le service : passage en mode API")
                        self.app_instance.transcription_service._loading_in_progress = False
            
            self.whisper_frame.pack_forget()
            self.api_frame.pack(fill=tk.BOTH, expand=True, pady=10)
            self.whisper_status_label.config(text="")
            # La barre de progression n'est plus utilisée
            # self.whisper_progress.pack_forget()
            # self.whisper_progress.stop()
    
    def _check_whisper(self):
        """Vérifie la disponibilité de Whisper (sans charger le modèle)."""
        print("[Configuration] Vérification de Whisper...")
        service = TranscriptionService(mode="local", whisper_model=self.whisper_model_var.get())
        is_available = service.is_whisper_available()
        
        if is_available:
            print("[Configuration] Whisper est disponible")
            # Ne pas appeler validate_configuration() car cela peut charger le modèle de manière synchrone
            # Juste indiquer que Whisper est disponible
            self.whisper_status_label.config(
                text="[OK] Whisper est disponible. Le modele sera charge automatiquement.",
                foreground='green'
            )
        else:
            print("[Configuration] [ERREUR] Whisper n'est pas installe")
            self.whisper_status_label.config(
                text="[ERREUR] Whisper n'est pas installe. Installez-le avec: pip install openai-whisper",
                foreground='red'
            )
    
    def _load_whisper_model_async(self):
        """Charge le modèle Whisper en arrière-plan sans freeze l'interface."""
        import threading
        
        # Vérifier si un chargement est déjà en cours
        if self._model_loading_in_progress:
            print("[Configuration] Un chargement est déjà en cours, ignoré.")
            return
        
        # Vérifier d'abord si on est toujours en mode local
        if self.mode_var.get() != "local":
            print("[Configuration] Chargement annulé : le mode n'est pas 'local'")
            return
        
        # Vérifier d'abord si Whisper est disponible
        service = TranscriptionService(mode="local", whisper_model=self.whisper_model_var.get())
        if not service.is_whisper_available():
            self.whisper_status_label.config(
                text="[ERREUR] Whisper n'est pas installe. Installez-le avec: pip install openai-whisper",
                foreground='red'
            )
            return
        
        # Vérifier si le modèle est déjà chargé dans le service de l'application
        if (self.app_instance and self.app_instance.transcription_service and
            self.app_instance.transcription_service.mode == "local" and
            self.app_instance.transcription_service.is_model_loaded()):
            print("[Configuration] Le modèle est déjà chargé.")
            self._update_load_model_button()
            return
        
        # Marquer qu'un chargement est en cours
        self._model_loading_in_progress = True
        
        # Désactiver le bouton pendant le chargement
        if hasattr(self, 'load_model_button'):
            self.load_model_button.config(text="⏳ Chargement...", state="disabled")
        
        # Afficher l'indicateur de chargement
        model_name = self.whisper_model_var.get()
        self.whisper_status_label.config(
            text=f"⏳ Chargement du modèle '{model_name}' en cours...",
            foreground='blue'
        )
        # Ne plus afficher la barre de progression, on affiche les Mo téléchargés dans le label
        # self.whisper_progress.pack(anchor=tk.W, pady=5)
        # self.whisper_progress.start(10)  # Animation de la progress bar
        
        def load_model_thread():
            """Charge le modèle dans un thread séparé."""
            try:
                print(f"[Configuration] Début du chargement du modèle '{model_name}' en arrière-plan...")
                
                # Utiliser le service de transcription de l'application si disponible
                if self.app_instance and self.app_instance.transcription_service:
                    service = self.app_instance.transcription_service
                    # Vérifier que le mode est toujours "local"
                    if service.mode != "local":
                        print(f"[Configuration] Chargement annulé : le mode a changé vers '{service.mode}'")
                        self.root.after(0, lambda: self._on_model_loaded(False, model_name, "Mode changé vers API"))
                        return
                    
                    # Callback pour mettre à jour l'interface avec la progression
                    def progress_callback(message):
                        """Met à jour l'interface avec le message de progression."""
                        # Vérifier que le mode est toujours "local" avant de mettre à jour
                        if self.app_instance and self.app_instance.transcription_service:
                            if self.app_instance.transcription_service.mode != "local":
                                return  # Ne pas mettre à jour si le mode a changé
                        self.root.after(0, lambda: self.whisper_status_label.config(
                            text=f"⏳ Téléchargement: {message}",
                            foreground='blue'
                        ))
                    
                    success = service.load_whisper_model(progress_callback=progress_callback)
                else:
                    # Créer un nouveau service pour le test
                    service = TranscriptionService(mode="local", whisper_model=model_name)
                    
                    # Callback pour mettre à jour l'interface avec la progression
                    def progress_callback(message):
                        """Met à jour l'interface avec le message de progression."""
                        self.root.after(0, lambda: self.whisper_status_label.config(
                            text=f"⏳ Téléchargement: {message}",
                            foreground='blue'
                        ))
                    
                    success = service.load_whisper_model(progress_callback=progress_callback)
                    
                    # Si succès, mettre à jour le service de transcription de l'application
                    if success and self.app_instance and self.app_instance.transcription_service:
                        # Vérifier que le mode est toujours "local" avant de mettre à jour
                        if self.app_instance.transcription_service.mode == "local":
                            self.app_instance.transcription_service.whisper_model = model_name
                            self.app_instance.transcription_service.whisper_model_obj = service.whisper_model_obj
                        else:
                            print(f"[Configuration] Chargement terminé mais le mode a changé vers '{self.app_instance.transcription_service.mode}'")
                            success = False
                
                # Mettre à jour l'interface dans le thread principal
                self.root.after(0, lambda: self._on_model_loaded(success, model_name))
            except Exception as e:
                print(f"[Configuration] Erreur lors du chargement du modèle: {e}")
                import traceback
                traceback.print_exc()
                self.root.after(0, lambda: self._on_model_loaded(False, model_name, str(e)))
            finally:
                # Réinitialiser le flag dans le thread principal
                self.root.after(0, lambda: setattr(self, '_model_loading_in_progress', False))
        
        # Lancer le chargement dans un thread séparé
        self._loading_thread = threading.Thread(target=load_model_thread, daemon=True)
        self._loading_thread.start()
    
    def _on_model_loaded(self, success: bool, model_name: str, error: str = None):
        """Appelé quand le chargement du modèle est terminé."""
        # Réinitialiser le flag
        self._model_loading_in_progress = False
        
        # Réactiver le bouton
        if hasattr(self, 'load_model_button'):
            self.load_model_button.config(state="normal")
        
        # La barre de progression n'est plus utilisée, on affiche les Mo dans le label
        # self.whisper_progress.stop()
        # self.whisper_progress.pack_forget()
        
        if success:
            self.whisper_status_label.config(
                text=f"[OK] Modele '{model_name}' charge avec succes !",
                foreground='green'
            )
            print(f"[Configuration] [OK] Modele '{model_name}' charge avec succes dans l'interface")
            # Mettre à jour le bouton
            self._update_load_model_button()
            # Recharger les composants pour mettre à jour le statut
            if self.on_save:
                self.on_save()
            # Mettre à jour le bandeau d'information
            self._update_status_banner()
        else:
            error_msg = error if error else "Erreur inconnue"
            self.whisper_status_label.config(
                text=f"[ERREUR] Erreur lors du chargement du modele '{model_name}': {error_msg}",
                foreground='red'
            )
            print(f"[Configuration] [ERREUR] Erreur lors du chargement du modele '{model_name}': {error_msg}")
            # Mettre à jour le bouton
            self._update_load_model_button()
    
    def _update_load_model_button(self):
        """Met à jour l'état du bouton de chargement du modèle."""
        if not hasattr(self, 'load_model_button'):
            return
        
        try:
            # Vérifier si le modèle est chargé dans le service de transcription de l'application
            if self.app_instance and self.app_instance.transcription_service:
                service = self.app_instance.transcription_service
                if service.mode == "local" and service.is_model_loaded():
                    self.load_model_button.config(text="[OK] Modele charge", state="normal")
                else:
                    self.load_model_button.config(text="❌ Charger le modèle", state="normal")
            else:
                # Si pas d'instance, vérifier avec un nouveau service
                service = TranscriptionService(mode="local", whisper_model=self.whisper_model_var.get())
                if service.is_model_loaded():
                    self.load_model_button.config(text="[OK] Modele charge", state="normal")
                else:
                    self.load_model_button.config(text="❌ Charger le modèle", state="normal")
        except Exception as e:
            print(f"Erreur lors de la mise à jour du bouton: {e}")
            self.load_model_button.config(text="❌ Charger le modèle", state="normal")
    
    def _on_model_changed(self):
        """Appelé quand la taille du modèle change."""
        # Si un chargement est en cours, l'arrêter
        if self._model_loading_in_progress:
            print("[Configuration] Arrêt du chargement : changement de modèle")
            self._model_loading_in_progress = False
            if hasattr(self, 'load_model_button'):
                self.load_model_button.config(text="❌ Charger le modèle", state="normal")
        
        # Mettre à jour l'état du bouton (le modèle précédent n'est plus valide)
        if self.mode_var.get() == "local":
            # Réinitialiser le modèle dans le service de l'application
            if self.app_instance and self.app_instance.transcription_service:
                self.app_instance.transcription_service.whisper_model_obj = None
            self._update_load_model_button()
            # Ne pas charger automatiquement, l'utilisateur doit cliquer sur le bouton
    
    def _test_api(self):
        """Teste la connexion à l'API."""
        url = self.api_url_var.get().strip()
        token = self.api_token_var.get().strip()
        
        if not url:
            messagebox.showerror("Erreur", "Veuillez entrer une URL d'API")
            return
        
        if not token:
            messagebox.showerror("Erreur", "Veuillez entrer un token")
            return
        
        # Test simple (sans fichier audio)
        try:
            import requests
            response = requests.get(url, headers={'Authorization': f'Bearer {token}'}, timeout=5)
            messagebox.showinfo("Test API", f"Connexion réussie (Code: {response.status_code})")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Erreur", f"Impossible de se connecter à l'API:\n{e}")
    
    def _test_with_file(self):
        """Teste la transcription avec le fichier alexa_ciel.wav."""
        from pathlib import Path
        
        # Chercher le fichier alexa_ciel.wav
        test_file = Path("alexa_ciel.wav")
        if not test_file.exists():
            messagebox.showerror("Erreur", f"Fichier de test non trouve: {test_file.absolute()}")
            return
        
        mode = self.mode_var.get()
        
        if mode == "api":
            url = self.api_url_var.get().strip()
            token = self.api_token_var.get().strip()
            
            if not url or not token:
                messagebox.showerror("Erreur", "Veuillez configurer l'URL et le token de l'API")
                return
            
            service = TranscriptionService(mode="api", api_url=url, api_token=token)
        else:
            # Mode local
            whisper_model = self.whisper_model_var.get()
            service = TranscriptionService(mode="local", whisper_model=whisper_model)
        
        # Afficher un message de progression
        progress_window = tk.Toplevel(self.root)
        progress_window.title("Test en cours...")
        progress_window.geometry("400x100")
        progress_label = ttk.Label(progress_window, text="Transcription en cours...")
        progress_label.pack(pady=20)
        progress_window.update()
        
        # Lancer la transcription dans un thread pour ne pas bloquer l'UI
        import threading
        
        def test_transcription():
            try:
                result = service.transcribe(str(test_file))
                progress_window.after(0, lambda: self._show_test_result(result, mode, progress_window))
            except Exception as e:
                progress_window.after(0, lambda: self._show_test_error(str(e), progress_window))
        
        thread = threading.Thread(target=test_transcription, daemon=True)
        thread.start()
    
    def _show_test_result(self, result, mode, progress_window):
        """Affiche le résultat du test."""
        progress_window.destroy()
        
        if result is None:
            messagebox.showerror("Erreur", "Aucun resultat obtenu")
            return
        
        if mode == "api":
            # En mode API, afficher le JSON complet
            import json
            try:
                # Si result est déjà un dict, l'utiliser directement
                if isinstance(result, dict):
                    result_json = result
                else:
                    # Sinon, essayer de parser le JSON
                    result_json = json.loads(result)
                
                message = result_json.get("message", result_json.get("text", ""))
                delay = result_json.get("delay", "N/A")
                result_text = f"Delay: {delay}\n\nMessage:\n{message}"
            except (json.JSONDecodeError, AttributeError):
                # Si ce n'est pas du JSON, afficher le texte directement
                result_text = result
        else:
            # En mode local, afficher juste le texte
            result_text = result
        
        # Créer une fenêtre pour afficher le résultat
        result_window = tk.Toplevel(self.root)
        result_window.title("Resultat du test")
        result_window.geometry("500x300")
        
        text_widget = tk.Text(result_window, wrap=tk.WORD, padx=10, pady=10)
        text_widget.pack(fill=tk.BOTH, expand=True)
        text_widget.insert('1.0', result_text)
        text_widget.config(state=tk.DISABLED)
        
        ttk.Button(result_window, text="Fermer", command=result_window.destroy).pack(pady=10)
    
    def _show_test_error(self, error_msg, progress_window):
        """Affiche une erreur lors du test."""
        progress_window.destroy()
        messagebox.showerror("Erreur", f"Erreur lors du test:\n{error_msg}")
    
    def _on_widget_visible_changed(self):
        """Appelé quand la visibilité du widget change."""
        try:
            visible = bool(self.widget_visible_var.get())
            print(f"[Configuration] Visibilité du widget changée: {visible} (type: {type(visible)})")
            
            self.config.set("widget.visible", visible)
            self.config.save()
            print(f"[Configuration] Configuration sauvegardée: widget.visible={self.config.get('widget.visible')}")
            
            # Mettre à jour le widget immédiatement
            if self.app_instance and self.app_instance.widget:
                try:
                    # Utiliser after() pour s'assurer que l'appel se fait dans le bon thread Tkinter
                    # Même si on est dans le thread principal, on utilise after() pour être sûr
                    self.app_instance.widget.root.after(0, lambda v=visible: self.app_instance.widget.set_visible(v))
                    print(f"[Configuration] Widget mis à jour (visible={visible}) - appelé via after()")
                except Exception as e:
                    print(f"[Configuration] Erreur lors de la mise à jour du widget: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"[Configuration] app_instance={self.app_instance is not None}, widget={self.app_instance.widget if self.app_instance else None}")
            
            # Recharger les composants si callback disponible
            if self.on_save:
                self.on_save()
        except Exception as e:
            print(f"[Configuration] Erreur dans _on_widget_visible_changed: {e}")
            import traceback
            traceback.print_exc()
    
    def _auto_save(self):
        """Sauvegarde automatiquement la configuration."""
        # Sauvegarder le raccourci
        self.config.set("hotkey.ctrl", self.hotkey_vars['ctrl'].get())
        self.config.set("hotkey.alt", self.hotkey_vars['alt'].get())
        self.config.set("hotkey.shift", self.hotkey_vars['shift'].get())
        self.config.set("hotkey.key", self.hotkey_vars['key'].get().lower())
        
        # Sauvegarder le mode
        mode = self.mode_var.get()
        self.config.set("mode", mode)
        
        # Sauvegarder la configuration API
        self.config.set("api.url", self.api_url_var.get().strip())
        self.config.set("api.token", self.api_token_var.get().strip())
        
        # Sauvegarder la configuration Whisper
        self.config.set("whisper.model", self.whisper_model_var.get())
        
        # Sauvegarder la visibilité du widget
        self.config.set("widget.visible", self.widget_visible_var.get())
        
        # Sauvegarder la configuration audio
        if self.use_default_mic_var.get():
            self.config.set("audio.device_index", None)
        else:
            device_name = self.selected_device_var.get()
            if device_name and hasattr(self, 'device_map') and device_name in self.device_map:
                self.config.set("audio.device_index", self.device_map[device_name])
        
        # Sauvegarder
        self.config.save()
        
        # Recharger les composants si callback disponible
        if self.on_save:
            self.on_save()
    
    def _start_hotkey_capture(self):
        """Démarre la capture du raccourci clavier."""
        if self.hotkey_capturing:
            return
        
        self.hotkey_capturing = True
        self.captured_modifiers = []
        self.captured_key = None
        
        # Changer le texte du bouton et enlever le focus
        self.hotkey_change_button.config(text="Appuyez sur les touches...", state="disabled")
        # Enlever le focus du bouton pour éviter que Espace/Entrée l'activent
        try:
            self.root.focus_set()
        except:
            pass
        
        # Mettre à jour l'affichage pour montrer qu'on attend
        self._update_hotkey_display(capturing=True)
        
        # Démarrer le listener dans un thread séparé
        def start_listener():
            self.hotkey_listener = keyboard.Listener(
                on_press=self._on_hotkey_press,
                on_release=self._on_hotkey_release
            )
            self.hotkey_listener.start()
        
        threading.Thread(target=start_listener, daemon=True).start()
    
    def _on_hotkey_press(self, key):
        """Callback appelé quand une touche est pressée pendant la capture."""
        if not self.hotkey_capturing:
            return
        
        try:
            # Identifier les modificateurs
            if key in [Key.ctrl, Key.ctrl_l, Key.ctrl_r]:
                if 'ctrl' not in self.captured_modifiers:
                    self.captured_modifiers.append('ctrl')
            elif key in [Key.alt, Key.alt_l, Key.alt_r]:
                if 'alt' not in self.captured_modifiers:
                    self.captured_modifiers.append('alt')
            elif key in [Key.shift, Key.shift_l, Key.shift_r]:
                if 'shift' not in self.captured_modifiers:
                    self.captured_modifiers.append('shift')
            else:
                # Touche principale
                if isinstance(key, Key):
                    # Touche spéciale
                    key_map = {
                        Key.space: 'space',
                        Key.enter: 'enter',
                        Key.tab: 'tab',
                        Key.esc: 'esc',
                        Key.f1: 'f1', Key.f2: 'f2', Key.f3: 'f3', Key.f4: 'f4',
                        Key.f5: 'f5', Key.f6: 'f6', Key.f7: 'f7', Key.f8: 'f8',
                        Key.f9: 'f9', Key.f10: 'f10', Key.f11: 'f11', Key.f12: 'f12',
                    }
                    self.captured_key = key_map.get(key, None)
                else:
                    # Touche normale
                    if hasattr(key, 'char') and key.char:
                        self.captured_key = key.char.lower()
                    else:
                        try:
                            key_str = str(key).replace("'", "").lower()
                            self.captured_key = key_str
                        except:
                            pass
                
                # Si on a une touche principale, arrêter la capture
                if self.captured_key:
                    self._stop_hotkey_capture()
        except Exception as e:
            print(f"Erreur lors de la capture du raccourci: {e}")
    
    def _on_hotkey_release(self, key):
        """Callback appelé quand une touche est relâchée pendant la capture."""
        # Ne rien faire, on attend juste la touche principale
        pass
    
    def _stop_hotkey_capture(self):
        """Arrête la capture du raccourci clavier."""
        if not self.hotkey_capturing:
            return
        
        self.hotkey_capturing = False
        
        # Arrêter le listener
        if self.hotkey_listener:
            try:
                self.hotkey_listener.stop()
            except:
                pass
            self.hotkey_listener = None
        
        # Mettre à jour les variables si on a capturé quelque chose
        if self.captured_key:
            self.hotkey_vars['ctrl'].set('ctrl' in self.captured_modifiers)
            self.hotkey_vars['alt'].set('alt' in self.captured_modifiers)
            self.hotkey_vars['shift'].set('shift' in self.captured_modifiers)
            self.hotkey_vars['key'].set(self.captured_key)
        
        # Restaurer le bouton
        self.hotkey_change_button.config(text="Changer", state="normal")
        
        # Enlever le focus du bouton pour éviter que Espace/Entrée relancent la capture
        # Utiliser after() pour différer et éviter les conflits avec la touche capturée
        def remove_focus():
            try:
                # Forcer le focus sur la fenêtre principale au lieu du bouton
                self.root.focus_set()
            except:
                pass
        
        self.root.after(100, remove_focus)  # Attendre 100ms avant d'enlever le focus
        
        # Mettre à jour l'affichage
        self._update_hotkey_display()
    
    def _update_hotkey_display(self, capturing=False):
        """Met à jour l'affichage visuel des touches du raccourci."""
        # Nettoyer le frame
        for widget in self.hotkey_keys_frame.winfo_children():
            widget.destroy()
        
        if capturing:
            # Afficher un message pendant la capture
            label = ttk.Label(
                self.hotkey_keys_frame,
                text="Appuyez sur les touches...",
                font=('Arial', 9),
                foreground='blue'
            )
            label.pack(side=tk.LEFT)
        else:
            # Afficher les touches actuelles
            modifiers = []
            if self.hotkey_vars['ctrl'].get():
                modifiers.append('Ctrl')
            if self.hotkey_vars['alt'].get():
                modifiers.append('Alt')
            if self.hotkey_vars['shift'].get():
                modifiers.append('Shift')
            
            key = self.hotkey_vars['key'].get()
            if key:
                # Afficher chaque touche comme un bouton/pilule
                for mod in modifiers:
                    key_label = tk.Label(
                        self.hotkey_keys_frame,
                        text=mod,
                        font=('Arial', 9, 'bold'),
                        bg='#E0E0E0',
                        fg='#333333',
                        relief=tk.RAISED,
                        borderwidth=1,
                        padx=8,
                        pady=4
                    )
                    key_label.pack(side=tk.LEFT, padx=2)
                
                # Afficher la touche principale
                key_display = key.title() if key else "Space"
                key_label = tk.Label(
                    self.hotkey_keys_frame,
                    text=key_display,
                    font=('Arial', 9, 'bold'),
                    bg='#E0E0E0',
                    fg='#333333',
                    relief=tk.RAISED,
                    borderwidth=1,
                    padx=8,
                    pady=4
                )
                key_label.pack(side=tk.LEFT, padx=2)
        # Mettre à jour le bandeau d'information après la sauvegarde
        self._update_status_banner()
    
    def show(self):
        """Affiche la fenêtre de configuration."""
        # Ne pas appeler mainloop() ici car on utilise déjà le mainloop du widget principal
        # Juste afficher la fenêtre
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self._reload_values() # S'assurer que les valeurs sont à jour
        # Mettre à jour le bandeau d'information
        self._update_status_banner()

