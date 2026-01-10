"""
Interface de configuration Tkinter avec thème Sun-Valley-ttk.
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Optional, Callable
import threading
from pynput import keyboard
from pynput.keyboard import Key, Listener
import sv_ttk
import json
import os
from config import Config
from transcription import TranscriptionService
from PIL import Image, ImageTk
try:
    import cairosvg
    HAS_CAIROSVG = True
except ImportError:
    HAS_CAIROSVG = False
try:
    import darkdetect
    HAS_DARKDETECT = True
except ImportError:
    HAS_DARKDETECT = False
try:
    import pywinstyles
    HAS_PYWINSTYLES = True
except ImportError:
    HAS_PYWINSTYLES = False


class LanguageManager:
    """Gestionnaire d'internationalisation."""

    def __init__(self, default_lang="en"):
        self.current_lang = default_lang
        self.translations = {}
        self.load_languages()

    def load_languages(self):
        """Charge toutes les langues disponibles."""
        locales_dir = os.path.join(os.path.dirname(__file__), "locales")
        if not os.path.exists(locales_dir):
            return

        for file in os.listdir(locales_dir):
            if file.endswith(".json"):
                lang_code = file[:-5]  # Remove .json extension
                try:
                    with open(os.path.join(locales_dir, file), 'r', encoding='utf-8') as f:
                        self.translations[lang_code] = json.load(f)
                except Exception as e:
                    print(f"Erreur lors du chargement de la langue {lang_code}: {e}")

    def set_language(self, lang_code):
        """Change la langue actuelle."""
        if lang_code in self.translations:
            self.current_lang = lang_code
            return True
        return False

    def get(self, key, **kwargs):
        """Récupère une traduction."""
        if self.current_lang in self.translations and key in self.translations[self.current_lang]:
            text = self.translations[self.current_lang][key]
            if kwargs:
                return text.format(**kwargs)
            return text
        # Fallback to English if translation not found
        if "en" in self.translations and key in self.translations["en"]:
            text = self.translations["en"][key]
            if kwargs:
                return text.format(**kwargs)
            return text
        # Return key if no translation found
        return key

    def get_available_languages(self):
        """Retourne la liste des langues disponibles."""
        return list(self.translations.keys())


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

        # Initialiser le gestionnaire de langues
        self.lang = LanguageManager()

        # Charger la langue sauvegardée
        saved_language = self.config.get("ui.language", "en")
        self.lang.set_language(saved_language)

        # Utiliser Toplevel au lieu de Tk() pour éviter les conflits avec le widget principal
        # Si app_instance existe et a un widget, utiliser sa fenêtre comme parent
        if app_instance and app_instance.widget and app_instance.widget.root:
            self.root = tk.Toplevel(app_instance.widget.root)
        else:
            # Fallback : créer une nouvelle fenêtre principale (ne devrait pas arriver normalement)
            self.root = tk.Tk()

        self.root.title(self.lang.get("window_title"))
        self.root.geometry("650x800")
        self.root.resizable(True, True)  # Permettre le redimensionnement
        
        # Gérer la fermeture de la fenêtre pour arrêter le monitoring du thème
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)

        # Détecter le thème du système et appliquer le thème approprié
        self._detect_and_apply_theme()

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
        self.whisper_device_var = tk.StringVar(value=self.config.get("whisper.device", "cpu"))
        self.use_default_mic_var = tk.BooleanVar(value=use_default_mic)
        self.selected_device_var = tk.StringVar()
        self.device_map = {}
        self.language_var = tk.StringVar(value=self.lang.current_lang)
        
        print(f"[Configuration] Initialisation - widget_visible={widget_visible} (type: {type(widget_visible)}), use_default_mic={use_default_mic} (type: {type(use_default_mic)})")
        
        # S'assurer que device_combo existe (sera créé dans _create_audio_tab)
        self.device_combo = None
        
        # Flag pour éviter les chargements multiples en parallèle
        self._model_loading_in_progress = False
        self._loading_thread = None
        
        # Thread pour surveiller les changements de thème système
        self._theme_monitor_thread = None
        self._theme_monitor_running = False
        self._start_theme_monitor()
    
    def _detect_and_apply_theme(self):
        """Détecte le thème du système et applique le thème approprié."""
        # Détecter le thème du système
        if HAS_DARKDETECT:
            try:
                is_dark = darkdetect.isDark()
                theme = "dark" if is_dark else "light"
            except:
                # Fallback vers dark si la détection échoue
                theme = "dark"
        else:
            # Fallback vers dark si darkdetect n'est pas disponible
            theme = "dark"
        
        # Appliquer le thème
        sv_ttk.set_theme(theme)
        self.current_theme = theme
        
        # Appliquer le style de la barre de titre selon le thème (Windows uniquement)
        # Utiliser after() pour s'assurer que la fenêtre est complètement créée
        def apply_titlebar_style():
            if HAS_PYWINSTYLES:
                try:
                    import sys
                    if sys.platform == 'win32':
                        # Sauvegarder le titre actuel avant d'appliquer le style
                        current_title = self.root.title()
                        # Appliquer le style de barre de titre sombre si le thème est dark
                        if theme == "dark":
                            pywinstyles.apply_style(self.root, "dark")
                        else:
                            pywinstyles.apply_style(self.root, "light")
                        # Restaurer le titre après l'application du style
                        self.root.after(50, lambda: self.root.title(current_title))
                except Exception as e:
                    print(f"[Configuration] Erreur lors de l'application du style de barre de titre: {e}")
        
        # Appliquer le style après que la fenêtre soit créée
        self.root.after(100, apply_titlebar_style)
        
        print(f"[Configuration] Thème appliqué: {theme}")
    
    def _start_theme_monitor(self):
        """Démarre un thread pour surveiller les changements de thème système."""
        if not HAS_DARKDETECT:
            return
        
        self._theme_monitor_running = True
        
        def monitor_theme():
            """Thread qui surveille les changements de thème."""
            last_theme = getattr(self, 'current_theme', 'dark')
            import time
            
            while self._theme_monitor_running:
                try:
                    if HAS_DARKDETECT:
                        is_dark = darkdetect.isDark()
                        current_theme = "dark" if is_dark else "light"
                        
                        # Si le thème a changé, mettre à jour l'interface
                        if current_theme != last_theme:
                            print(f"[Configuration] Changement de thème détecté: {last_theme} -> {current_theme}")
                            # Mettre à jour dans le thread principal Tkinter
                            self.root.after(0, lambda: self._update_theme(current_theme))
                            last_theme = current_theme
                    
                    # Vérifier toutes les 2 secondes
                    time.sleep(2)
                except Exception as e:
                    print(f"[Configuration] Erreur lors de la surveillance du thème: {e}")
                    time.sleep(2)
        
        self._theme_monitor_thread = threading.Thread(target=monitor_theme, daemon=True)
        self._theme_monitor_thread.start()
    
    def _update_theme(self, new_theme):
        """Met à jour le thème de l'interface."""
        if new_theme == getattr(self, 'current_theme', None):
            return  # Pas de changement
        
        print(f"[Configuration] Mise à jour du thème vers: {new_theme}")
        
        # Appliquer le nouveau thème
        sv_ttk.set_theme(new_theme)
        self.current_theme = new_theme
        
        # Appliquer le style de la barre de titre
        if HAS_PYWINSTYLES:
            try:
                import sys
                if sys.platform == 'win32':
                    if new_theme == "dark":
                        pywinstyles.apply_style(self.root, "dark")
                    else:
                        pywinstyles.apply_style(self.root, "light")
            except Exception as e:
                print(f"[Configuration] Erreur lors de l'application du style de barre de titre: {e}")
        
        # Mettre à jour les couleurs du bandeau de statut
        if hasattr(self, 'status_banner_frame'):
            colors = self._get_theme_colors()
            
            # Mettre à jour le frame et le canvas du bandeau
            self.status_banner_frame.config(bg=colors['bg_banner'])
            self.status_banner_canvas.config(bg=colors['bg_banner'])
            
            # Mettre à jour les labels du bandeau (les couleurs seront mises à jour par _update_status_banner)
            if hasattr(self, 'status_icon_label'):
                self.status_icon_label.config(bg=colors['bg_banner'], fg=colors['fg_icon'])
            if hasattr(self, 'status_banner_label'):
                self.status_banner_label.config(bg=colors['bg_banner'], fg=colors['fg_secondary'])
            
            # Réappliquer le bandeau de statut pour mettre à jour les couleurs
            self._update_status_banner()
    
    def _get_theme_colors(self):
        """Retourne un dictionnaire de couleurs selon le thème actuel."""
        # Utiliser le thème actuel ou dark par défaut
        theme = getattr(self, 'current_theme', 'dark')
        if theme == "light":
            return {
                'bg_main': '#FFFFFF',
                'bg_frame': '#F5F5F5',
                'bg_banner': '#F0F0F0',
                'fg_main': '#000000',
                'fg_secondary': '#333333',
                'fg_icon': '#666666',
                'bg_loading': '#FFF4E6',
                'fg_loading': '#FF8C00',
                'bg_error': '#FFEBEE',
                'fg_error': '#C62828',
                'bg_ok': '#E8F5E9',
                'fg_ok': '#2E7D32',
            }
        else:  # dark
            return {
                'bg_main': '#1E1E1E',
                'bg_frame': '#252525',
                'bg_banner': '#1E1E1E',
                'fg_main': '#E0E0E0',
                'fg_secondary': '#CCCCCC',
                'fg_icon': '#E0E0E0',
                'bg_loading': '#2D2A1E',
                'fg_loading': '#FFB84D',
                'bg_error': '#2D1E1E',
                'fg_error': '#FF6B6B',
                'bg_ok': '#1E2D1E',
                'fg_ok': '#4EC9B0',
            }
    
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
        self.whisper_device_var.set(self.config.get("whisper.device", "cpu"))
        self.use_default_mic_var.set(use_default_mic)

        # Recharger la langue
        saved_language = self.config.get("ui.language", "en")
        self.lang.set_language(saved_language)
        self.language_var.set(saved_language)
        # Mettre à jour l'affichage de la langue si le mapping existe
        if hasattr(self, 'language_code_to_display'):
            if hasattr(self, 'language_display_var'):
                self.language_display_var.set(self.language_code_to_display.get(saved_language, saved_language.upper()))
        
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
        colors = self._get_theme_colors()
        
        # Frame pour le bandeau avec fond moderne
        self.status_banner_frame = tk.Frame(self.root, bg=colors['bg_banner'])
        self.status_banner_frame.pack(fill=tk.X, padx=15, pady=(15, 10))

        # Canvas pour créer un design moderne avec coins arrondis
        self.status_banner_canvas = tk.Canvas(
            self.status_banner_frame,
            height=50,
            bg=colors['bg_banner'],
            highlightthickness=0,
            relief='flat'
        )
        self.status_banner_canvas.pack(fill=tk.X, expand=True)

        # Fonction pour dessiner le fond arrondi
        def draw_rounded_background(canvas, color):
            canvas.delete("bg_rounded")
            width = canvas.winfo_width()
            height = 50
            radius = 10  # Rayon des coins arrondis (augmenté pour plus de modernité)
            
            if width > 1:
                # Dessiner un rectangle arrondi
                # Coin supérieur gauche
                canvas.create_arc(0, 0, radius*2, radius*2, start=90, extent=90, 
                                 fill=color, outline=color, tags="bg_rounded")
                # Coin supérieur droit
                canvas.create_arc(width-radius*2, 0, width, radius*2, start=0, extent=90, 
                                 fill=color, outline=color, tags="bg_rounded")
                # Coin inférieur gauche
                canvas.create_arc(0, height-radius*2, radius*2, height, start=180, extent=90, 
                                 fill=color, outline=color, tags="bg_rounded")
                # Coin inférieur droit
                canvas.create_arc(width-radius*2, height-radius*2, width, height, start=270, extent=90, 
                                 fill=color, outline=color, tags="bg_rounded")
                # Rectangles pour remplir
                canvas.create_rectangle(radius, 0, width-radius, height, 
                                       fill=color, outline=color, tags="bg_rounded")
                canvas.create_rectangle(0, radius, width, height-radius, 
                                       fill=color, outline=color, tags="bg_rounded")
                # Mettre le fond en arrière-plan
                canvas.tag_lower("bg_rounded")

        # Frame interne pour le contenu (fond temporaire, sera mis à jour)
        self.status_banner_content = tk.Frame(
            self.status_banner_canvas,
            bg=colors['bg_banner'],  # Fond temporaire, sera mis à jour avec la couleur du statut
            relief='flat',
            height=50
        )
        # Centrer verticalement dans le canvas
        self.status_banner_window = self.status_banner_canvas.create_window(0, 0, window=self.status_banner_content, anchor="nw")
        
        # Bind pour ajuster la largeur et redessiner
        def configure_banner(event=None):
            canvas_width = self.status_banner_canvas.winfo_width()
            canvas_height = self.status_banner_canvas.winfo_height()
            if canvas_width > 1:
                self.status_banner_canvas.itemconfig(self.status_banner_window, width=canvas_width)
                # Centrer verticalement
                content_height = 50
                y_pos = max(0, (canvas_height - content_height) / 2)
                self.status_banner_canvas.coords(self.status_banner_window, 0, y_pos)
                # Redessiner le fond arrondi avec la couleur actuelle
                if hasattr(self, '_current_banner_bg'):
                    draw_rounded_background(self.status_banner_canvas, self._current_banner_bg)

        self.status_banner_canvas.bind('<Configure>', configure_banner)

        # Label pour l'icône de statut
        self.status_icon_label = tk.Label(
            self.status_banner_content,
            text="",
            font=('Segoe UI', 16),
            bg=colors['bg_banner'],
            fg=colors['fg_icon']
        )
        self.status_icon_label.pack(side=tk.LEFT, padx=(15, 10))

        # Label pour le message de statut
        self.status_banner_label = tk.Label(
            self.status_banner_content,
            text="",
            font=('Segoe UI', 10),
            bg=colors['bg_banner'],
            fg=colors['fg_secondary'],
            wraplength=580,
            justify=tk.LEFT,
            anchor="w"
        )
        self.status_banner_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 15))
        
        # Forcer la hauteur du frame
        self.status_banner_content.pack_propagate(False)
    
    def _update_status_banner(self):
        """Met à jour le bandeau d'information selon le statut de l'application."""
        if not hasattr(self, 'status_banner_label') or not self.app_instance:
            return

        try:
            colors = self._get_theme_colors()
            widget_status = self.app_instance.widget.status if self.app_instance.widget else "ok"
            transcription_service = self.app_instance.transcription_service

            if widget_status == "loading":
                message = self.lang.get("status_loading")
                icon = "⏳"
                bg_color = colors['bg_loading']
                text_color = colors['fg_loading']
                icon_color = colors['fg_loading']
            elif widget_status == "error":
                # Déterminer la raison de l'erreur
                if transcription_service.mode == "local":
                    if not transcription_service.is_whisper_available():
                        message = self.lang.get("status_error_whisper_not_installed")
                    elif not transcription_service.is_model_loaded():
                        if transcription_service.is_model_downloaded():
                            message = self.lang.get("status_error_model_not_loaded_downloaded")
                        else:
                            message = self.lang.get("status_error_model_not_loaded")
                    else:
                        message = self.lang.get("status_error_whisper_config")
                elif transcription_service.mode == "api":
                    if not transcription_service.api_url:
                        message = self.lang.get("status_error_api_url")
                    elif not transcription_service.api_token:
                        message = self.lang.get("status_error_api_token")
                    else:
                        message = self.lang.get("status_error_api_config")
                else:
                    message = self.lang.get("status_error_general")
                icon = "⚠️"
                bg_color = colors['bg_error']
                text_color = colors['fg_error']
                icon_color = colors['fg_error']
            else:  # ok
                message = self.lang.get("status_ok")
                icon = "✓"
                bg_color = colors['bg_ok']
                text_color = colors['fg_ok']
                icon_color = colors['fg_ok']

            # Mettre à jour les couleurs et le contenu (utiliser la couleur du fond arrondi)
            self.status_banner_content.config(bg=bg_color)
            self.status_icon_label.config(text=icon, bg=bg_color, fg=icon_color)
            self.status_banner_label.config(text=message, bg=bg_color, fg=text_color)
            self.status_banner_canvas.config(bg=colors['bg_banner'])
            
            # Stocker la couleur pour redessiner
            self._current_banner_bg = bg_color
            
            # Dessiner le fond arrondi AVANT de mettre à jour le contenu
            self.status_banner_canvas.update_idletasks()
            canvas_width = self.status_banner_canvas.winfo_width()
            canvas_height = self.status_banner_canvas.winfo_height()
            if canvas_width > 1:
                # Dessiner le fond arrondi avec coins arrondis en premier
                radius = 10  # Rayon des coins arrondis
                height = 50
                # Effacer l'ancien fond
                self.status_banner_canvas.delete("bg_rounded")
                # Dessiner les coins arrondis
                self.status_banner_canvas.create_arc(0, 0, radius*2, radius*2, start=90, extent=90, 
                                                   fill=bg_color, outline=bg_color, tags="bg_rounded")
                self.status_banner_canvas.create_arc(canvas_width-radius*2, 0, canvas_width, radius*2, start=0, extent=90, 
                                                   fill=bg_color, outline=bg_color, tags="bg_rounded")
                self.status_banner_canvas.create_arc(0, height-radius*2, radius*2, height, start=180, extent=90, 
                                                   fill=bg_color, outline=bg_color, tags="bg_rounded")
                self.status_banner_canvas.create_arc(canvas_width-radius*2, height-radius*2, canvas_width, height, start=270, extent=90, 
                                                   fill=bg_color, outline=bg_color, tags="bg_rounded")
                # Rectangles pour remplir le centre
                self.status_banner_canvas.create_rectangle(radius, 0, canvas_width-radius, height, 
                                                         fill=bg_color, outline=bg_color, tags="bg_rounded")
                self.status_banner_canvas.create_rectangle(0, radius, canvas_width, height-radius, 
                                                         fill=bg_color, outline=bg_color, tags="bg_rounded")
                # Mettre le fond en arrière-plan
                self.status_banner_canvas.tag_lower("bg_rounded")
                
                # Maintenant mettre à jour le contenu
                self.status_banner_canvas.itemconfig(self.status_banner_window, width=canvas_width)
                # Centrer verticalement
                content_height = 50
                y_pos = max(0, (canvas_height - content_height) / 2)
                self.status_banner_canvas.coords(self.status_banner_window, 0, y_pos)
        except Exception as e:
            print(f"Erreur lors de la mise à jour du bandeau: {e}")
            import traceback
            traceback.print_exc()
    
    def _create_widgets(self):
        """Crée les widgets de l'interface."""
        # Créer un canvas avec scrollbar pour permettre le défilement
        self.main_canvas = tk.Canvas(self.root, highlightthickness=0)
        self.main_scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.main_canvas.yview)
        self.scrollable_frame = ttk.Frame(self.main_canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))
        )

        self.scrollable_frame_id = self.main_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.main_canvas.configure(yscrollcommand=self.main_scrollbar.set)
        
        # Fonction pour ajuster la largeur du scrollable_frame à la largeur du canvas
        def configure_scrollable_frame(event):
            canvas_width = event.width
            self.main_canvas.itemconfig(self.scrollable_frame_id, width=canvas_width)
        
        self.main_canvas.bind('<Configure>', configure_scrollable_frame)

        # Ajouter le support du scroll à la molette
        def _on_mousewheel(event):
            self.main_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        def _bind_to_mousewheel(event):
            self.main_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_from_mousewheel(event):
            self.main_canvas.unbind_all("<MouseWheel>")

        self.main_canvas.bind('<Enter>', _bind_to_mousewheel)
        self.main_canvas.bind('<Leave>', _unbind_from_mousewheel)

        # Pack des éléments avec scrollbar
        self.main_scrollbar.pack(side="right", fill="y")
        self.main_canvas.pack(side="left", fill="both", expand=True, padx=10, pady=(0, 10))

        # Créer les sections dans la frame scrollable
        # Langue en premier
        self._create_language_section(self.scrollable_frame)

        # Séparateur entre les sections
        ttk.Separator(self.scrollable_frame, orient='horizontal').pack(fill=tk.X, pady=20, padx=10)

        self._create_general_tab(self.scrollable_frame)

        # Séparateur entre les sections
        ttk.Separator(self.scrollable_frame, orient='horizontal').pack(fill=tk.X, pady=20, padx=10)

        self._create_audio_tab(self.scrollable_frame)

        # Séparateur entre les sections
        ttk.Separator(self.scrollable_frame, orient='horizontal').pack(fill=tk.X, pady=20, padx=10)

        self._create_interface_tab(self.scrollable_frame)

        # Séparateur entre les sections
        ttk.Separator(self.scrollable_frame, orient='horizontal').pack(fill=tk.X, pady=20, padx=10)

        self._create_processing_mode_section(self.scrollable_frame)

        # Pas de boutons - sauvegarde automatique
    
    def _get_language_name(self, lang_code):
        """Retourne le nom complet de la langue dans sa propre langue."""
        language_names = {
            "en": "English",
            "fr": "Français",
            "es": "Español",
            "de": "Deutsch",
            "it": "Italiano",
            "pt": "Português",
            "ru": "Русский",
            "ja": "日本語",
            "zh": "中文",
            "ko": "한국어",
        }
        return language_names.get(lang_code, lang_code.upper())
    
    def _create_language_section(self, parent):
        """Crée la section de sélection de langue en haut."""
        language_frame = ttk.Frame(parent)
        language_frame.pack(fill=tk.X, padx=10, pady=(10, 0))
        
        # Label et combobox sur une ligne
        language_row = ttk.Frame(language_frame)
        language_row.pack(fill=tk.X)
        
        self.language_label = ttk.Label(language_row, text=self.lang.get("language_label"), font=('Arial', 9, 'bold'))
        self.language_label.pack(side=tk.LEFT, padx=(0, 10))
        
        # Créer les options de langue avec leurs noms complets dans leur propre langue
        language_display_names = []
        language_codes = []
        for lang_code in self.lang.get_available_languages():
            display_name = self._get_language_name(lang_code)
            language_display_names.append(display_name)
            language_codes.append(lang_code)
        
        # Créer un mapping pour retrouver le code depuis le nom affiché
        self.language_display_to_code = dict(zip(language_display_names, language_codes))
        self.language_code_to_display = dict(zip(language_codes, language_display_names))
        
        # Variable pour stocker le nom affiché
        self.language_display_var = tk.StringVar()
        current_lang = self.language_var.get()
        self.language_display_var.set(self.language_code_to_display.get(current_lang, current_lang.upper()))

        language_combo = ttk.Combobox(
            language_row,
            textvariable=self.language_display_var,
            values=language_display_names,
            state="readonly",
            width=20
        )
        language_combo.pack(side=tk.LEFT, padx=(0, 10))
        language_combo.bind('<<ComboboxSelected>>', lambda e: self._on_language_display_changed())

    def _load_refresh_icon(self):
        """Charge l'icône de rafraîchissement et retourne l'image ou None."""
        try:
            svg_path = os.path.join(os.path.dirname(__file__), "refresh.svg")
            if os.path.exists(svg_path) and HAS_CAIROSVG:
                from io import BytesIO
                png_data = cairosvg.svg2png(url=svg_path, output_width=20, output_height=20)
                img = Image.open(BytesIO(png_data))
                return ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"Erreur lors du chargement de l'icône: {e}")
        return None
    
    def _create_general_tab(self, parent):
        """Crée l'onglet Général."""
        # Raccourci clavier sur une ligne : texte -> bouton changer -> affichage
        hotkey_section_frame = ttk.Frame(parent)
        hotkey_section_frame.pack(fill=tk.X, padx=10, pady=(0, 15))
        
        # Frame pour tout mettre sur une ligne
        hotkey_row = ttk.Frame(hotkey_section_frame)
        hotkey_row.pack(fill=tk.X, pady=5)
        
        # Texte descriptif à gauche en gras
        # Utiliser ttk.Label pour la cohérence avec les autres labels en gras
        self.hotkey_title_label = ttk.Label(
            hotkey_row,
            text=self.lang.get("toggle_recording_title"),
            font=('Arial', 9, 'bold')
        )
        self.hotkey_title_label.pack(side=tk.LEFT, padx=(0, 10))
        
        # Bouton "Changer" avec icône
        refresh_icon = self._load_refresh_icon()
        if refresh_icon:
            # Garder une référence pour éviter le garbage collection
            self.hotkey_refresh_icon = refresh_icon
            self.hotkey_change_button = ttk.Button(
                hotkey_row,
                image=refresh_icon,
                command=self._start_hotkey_capture
            )
        else:
            self.hotkey_change_button = ttk.Button(
                hotkey_row,
                text="↻",
                command=self._start_hotkey_capture
            )
        self.hotkey_change_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Frame pour afficher les touches (style pilules)
        self.hotkey_keys_frame = ttk.Frame(hotkey_row)
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
        
        # Configuration Whisper (uniquement visible en mode local) - Fusionnée avec le modèle
        self.whisper_frame = ttk.LabelFrame(parent, text=self.lang.get("whisper_config_frame"), padding=10)
        # Ne pas packer initialement, sera fait par _update_mode_display()

        # Frame pour le label et le combobox sur la même ligne
        model_size_row = ttk.Frame(self.whisper_frame)
        model_size_row.pack(fill=tk.X, pady=2)
        
        self.model_size_label = ttk.Label(model_size_row, text=self.lang.get("model_size_label"))
        self.model_size_label.pack(side=tk.LEFT, padx=(0, 10))
        
        model_combo = ttk.Combobox(
            model_size_row,
            textvariable=self.whisper_model_var,
            values=["tiny", "base", "small", "medium", "large"],
            state="readonly",
            width=15
        )
        model_combo.pack(side=tk.LEFT, padx=(0, 10))
        model_combo.bind('<<ComboboxSelected>>', lambda e: [self._auto_save(), self._on_model_changed()])
        
        # Frame pour l'option CPU/GPU
        device_row = ttk.Frame(self.whisper_frame)
        device_row.pack(fill=tk.X, pady=(10, 2))
        
        self.device_label = ttk.Label(device_row, text=self.lang.get("whisper_device_label"))
        self.device_label.pack(side=tk.LEFT, padx=(0, 10))
        
        # Radio buttons pour CPU/GPU
        device_frame = ttk.Frame(device_row)
        device_frame.pack(side=tk.LEFT)
        
        self.cpu_radio = ttk.Radiobutton(
            device_frame,
            text=self.lang.get("whisper_device_cpu"),
            variable=self.whisper_device_var,
            value="cpu",
            command=lambda: [self._auto_save(), self._on_device_changed()]
        )
        self.cpu_radio.pack(side=tk.LEFT, padx=(0, 15))
        
        self.gpu_radio = ttk.Radiobutton(
            device_frame,
            text=self.lang.get("whisper_device_gpu"),
            variable=self.whisper_device_var,
            value="cuda",
            command=lambda: [self._auto_save(), self._on_device_changed()]
        )
        self.gpu_radio.pack(side=tk.LEFT)
        
        # Bouton pour charger le modèle à côté du combobox
        self.load_model_button = ttk.Button(
            model_size_row,
            text=self.lang.get("load_model_error"),
            command=self._load_whisper_model_async
        )
        self.load_model_button.pack(side=tk.LEFT)
        
        # Mettre à jour l'état du bouton
        self._update_load_model_button()
        
        self.model_note_label = ttk.Label(
            self.whisper_frame,
            text=self.lang.get("model_note"),
            font=('Arial', 8),
            foreground='gray'
        )
        self.model_note_label.pack(anchor=tk.W, pady=5)
        
        # Validation Whisper avec indicateur de chargement
        self.whisper_status_label = ttk.Label(self.whisper_frame, text="", foreground='red')
        self.whisper_status_label.pack(anchor=tk.W, pady=5)
        
        # Progress bar pour le chargement du modèle
        self.whisper_progress = ttk.Progressbar(self.whisper_frame, mode='indeterminate', length=300)
        self.whisper_progress.pack(anchor=tk.W, pady=5)
        self.whisper_progress.pack_forget()  # Caché par défaut
        
        # Configuration API (uniquement visible en mode API)
        self.api_frame = ttk.LabelFrame(parent, text=self.lang.get("api_config_frame"), padding=10)
        # Ne pas packer initialement, sera fait par _update_mode_display()

        self.api_url_label = ttk.Label(self.api_frame, text=self.lang.get("api_url_label"))
        self.api_url_label.pack(anchor=tk.W, pady=2)
        api_url_entry = ttk.Entry(self.api_frame, textvariable=self.api_url_var)
        api_url_entry.pack(fill=tk.X, pady=2)
        api_url_entry.bind('<FocusOut>', lambda e: self._auto_save())

        self.bearer_token_label = ttk.Label(self.api_frame, text=self.lang.get("bearer_token_label"))
        self.bearer_token_label.pack(anchor=tk.W, pady=(10, 2))
        api_token_entry = ttk.Entry(self.api_frame, textvariable=self.api_token_var, show="*")
        api_token_entry.pack(fill=tk.X, pady=2)
        api_token_entry.bind('<FocusOut>', lambda e: self._auto_save())

        # Frame pour le bouton de test et le résultat
        test_api_row = ttk.Frame(self.api_frame)
        test_api_row.pack(fill=tk.X, pady=5)
        
        self.test_with_file_api_button = ttk.Button(test_api_row, text=self.lang.get("test_with_audio_file"), command=self._test_with_file)
        self.test_with_file_api_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Label pour afficher le résultat du test à droite du bouton
        self.test_result_label_api = ttk.Label(
            test_api_row,
            text="",
            foreground='gray',
            wraplength=400
        )
        self.test_result_label_api.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Frame pour le bouton de test et le résultat
        test_row = ttk.Frame(self.whisper_frame)
        test_row.pack(fill=tk.X, pady=10)
        
        # Bouton pour tester avec fichier audio
        self.test_with_file_whisper_button = ttk.Button(test_row, text=self.lang.get("test_with_audio_file"), command=self._test_with_file)
        self.test_with_file_whisper_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Label pour afficher le résultat du test à droite du bouton
        self.test_result_label = ttk.Label(
            test_row,
            text="",
            foreground='gray',
            wraplength=400
        )
        self.test_result_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Initialiser l'affichage selon le mode actuel
        if self.mode_var.get() == "local":
            self._check_whisper()
            # Mettre à jour l'état du bouton après un court délai pour laisser le temps à l'interface de se créer
            self.root.after(100, self._update_load_model_button)
    
    def _create_audio_tab(self, parent):
        """Crée l'onglet Audio."""
        self.audio_section_frame = ttk.Frame(parent)
        self.audio_section_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        self.audio_config_title_label = ttk.Label(self.audio_section_frame, text=self.lang.get("audio_config_title"), font=('Arial', 10, 'bold'))
        self.audio_config_title_label.pack(anchor=tk.W, pady=(0, 10))

        # Case à cocher pour utiliser le microphone par défaut
        self.default_mic_checkbox = ttk.Checkbutton(
            self.audio_section_frame,
            text=self.lang.get("default_mic_checkbox"),
            variable=self.use_default_mic_var,
            command=lambda: self._on_default_mic_changed()
        )
        self.default_mic_checkbox.pack(anchor=tk.W, pady=10)
        
        # Frame pour la sélection manuelle
        self.manual_device_frame = ttk.Frame(self.audio_section_frame)
        self.manual_device_frame.pack(fill=tk.X, pady=5)
        
        # Frame pour la combobox et le bouton actualiser sur la même ligne
        device_row = ttk.Frame(self.manual_device_frame)
        device_row.pack(fill=tk.X, pady=5)
        
        # Liste déroulante des périphériques
        self.device_combo = ttk.Combobox(
            device_row,
            textvariable=self.selected_device_var,
            state="readonly"
        )
        self.device_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.device_combo.bind('<<ComboboxSelected>>', self._on_device_selected)
        
        # Bouton pour actualiser la liste avec icône à droite de la combobox
        refresh_icon = self._load_refresh_icon()
        if refresh_icon:
            # Garder une référence pour éviter le garbage collection
            self.audio_refresh_icon = refresh_icon
            refresh_button = ttk.Button(
                device_row,
                image=refresh_icon,
                command=self._refresh_audio_devices_list
            )
        else:
            refresh_button = ttk.Button(
                device_row,
                text="↻",
                command=self._refresh_audio_devices_list
            )
        refresh_button.pack(side=tk.RIGHT, padx=5)
        
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
        self.interface_section_frame = ttk.Frame(parent)
        self.interface_section_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        self.interface_config_title_label = ttk.Label(self.interface_section_frame, text=self.lang.get("interface_config_title"), font=('Arial', 10, 'bold'))
        self.interface_config_title_label.pack(anchor=tk.W, pady=(0, 10))

        self.widget_checkbox = ttk.Checkbutton(
            self.interface_section_frame,
            text=self.lang.get("show_widget_checkbox"),
            variable=self.widget_visible_var,
            command=lambda: self._on_widget_visible_changed()
        )
        self.widget_checkbox.pack(anchor=tk.W, pady=10)
        
        # Bouton pour réinitialiser la position du widget
        self.reset_widget_position_button = ttk.Button(
            self.interface_section_frame,
            text=self.lang.get("reset_widget_position"),
            command=self._reset_widget_position
        )
        self.reset_widget_position_button.pack(anchor=tk.W, pady=5)

    def _create_processing_mode_section(self, parent):
        """Crée la section Mode de traitement."""
        mode_section_frame = ttk.Frame(parent)
        mode_section_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.processing_mode_label = ttk.Label(mode_section_frame, text=self.lang.get("processing_mode"), font=('Arial', 10, 'bold'))
        self.processing_mode_label.pack(anchor=tk.W, pady=(0, 5))
        
        mode_frame = ttk.Frame(mode_section_frame)
        mode_frame.pack(fill=tk.X, pady=5)
        
        self.local_whisper_radio = ttk.Radiobutton(
            mode_frame,
            text=self.lang.get("local_whisper"),
            variable=self.mode_var,
            value="local",
            command=lambda: [self._update_mode_display(), self._auto_save()]
        )
        self.local_whisper_radio.pack(anchor=tk.W, pady=2)

        self.remote_api_radio = ttk.Radiobutton(
            mode_frame,
            text=self.lang.get("remote_api"),
            variable=self.mode_var,
            value="api",
            command=lambda: [self._update_mode_display(), self._auto_save()]
        )
        self.remote_api_radio.pack(anchor=tk.W, pady=2)

    def _on_language_display_changed(self):
        """Appelé quand la langue change via la combobox."""
        display_name = self.language_display_var.get()
        new_lang = self.language_display_to_code.get(display_name, display_name.lower())
        
        if self.lang.set_language(new_lang):
            # Mettre à jour la variable de code de langue
            self.language_var.set(new_lang)
            
            # Sauvegarder la nouvelle langue
            self.config.set("ui.language", new_lang)
            self.config.save()

            # Mettre à jour le titre de la fenêtre immédiatement
            new_title = self.lang.get("window_title")
            self.root.title(new_title)
            # Forcer la mise à jour de l'affichage
            self.root.update_idletasks()

            # Recharger l'interface pour appliquer les nouvelles traductions
            self._reload_interface_texts()

            # Mettre à jour le bandeau d'information
            self._update_status_banner()
            
            # Réappliquer le titre après un court délai pour s'assurer qu'il n'est pas écrasé par pywinstyles
            def reapply_title():
                self.root.title(new_title)
                self.root.update_idletasks()
            
            self.root.after(200, reapply_title)

            print(f"[Configuration] Langue changée vers: {new_lang}")

    def _reload_interface_texts(self):
        """Recharge tous les textes de l'interface après un changement de langue."""
        # Mettre à jour le titre de la fenêtre
        new_title = self.lang.get("window_title")
        self.root.title(new_title)
        # Forcer la mise à jour de l'affichage
        self.root.update_idletasks()
        
        # Mettre à jour le label du raccourci clavier (conserver la police en gras)
        if hasattr(self, 'hotkey_title_label'):
            self.hotkey_title_label.config(
                text=self.lang.get("toggle_recording_title"),
                font=('Arial', 9, 'bold')  # Utiliser directement la tuple pour garantir l'application
            )
        
        # Mettre à jour les labels du mode de traitement
        if hasattr(self, 'processing_mode_label'):
            self.processing_mode_label.config(text=self.lang.get("processing_mode"))
        if hasattr(self, 'local_whisper_radio'):
            self.local_whisper_radio.config(text=self.lang.get("local_whisper"))
        if hasattr(self, 'remote_api_radio'):
            self.remote_api_radio.config(text=self.lang.get("remote_api"))
        
        # Mettre à jour les frames LabelFrame
        if hasattr(self, 'api_frame'):
            self.api_frame.config(text=self.lang.get("api_config_frame"))
        if hasattr(self, 'whisper_frame'):
            self.whisper_frame.config(text=self.lang.get("whisper_config_frame"))
        
        # Mettre à jour les labels du modèle Whisper
        if hasattr(self, 'model_size_label'):
            self.model_size_label.config(text=self.lang.get("model_size_label"))
        if hasattr(self, 'model_note_label'):
            self.model_note_label.config(text=self.lang.get("model_note"))
        
        # Mettre à jour les labels et boutons API
        if hasattr(self, 'api_url_label'):
            self.api_url_label.config(text=self.lang.get("api_url_label"))
        if hasattr(self, 'bearer_token_label'):
            self.bearer_token_label.config(text=self.lang.get("bearer_token_label"))
        if hasattr(self, 'test_with_file_api_button'):
            self.test_with_file_api_button.config(text=self.lang.get("test_with_audio_file"))
        
        # Mettre à jour les boutons Whisper
        if hasattr(self, 'test_with_file_whisper_button'):
            self.test_with_file_whisper_button.config(text=self.lang.get("test_with_audio_file"))
        
        # Mettre à jour les widgets audio
        if hasattr(self, 'audio_config_title_label'):
            self.audio_config_title_label.config(text=self.lang.get("audio_config_title"))
        if hasattr(self, 'default_mic_checkbox'):
            self.default_mic_checkbox.config(text=self.lang.get("default_mic_checkbox"))
        
        # Mettre à jour les widgets interface
        if hasattr(self, 'interface_config_title_label'):
            self.interface_config_title_label.config(text=self.lang.get("interface_config_title"))
        if hasattr(self, 'widget_checkbox'):
            self.widget_checkbox.config(text=self.lang.get("show_widget_checkbox"))
        if hasattr(self, 'reset_widget_position_button'):
            self.reset_widget_position_button.config(text=self.lang.get("reset_widget_position"))
        
        # Mettre à jour le label de langue
        if hasattr(self, 'language_label'):
            self.language_label.config(text=self.lang.get("language_label"))

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
    
    def _update_mode_display(self):
        """Met à jour l'affichage selon le mode sélectionné."""
        # Vérifier que les frames existent avant de les utiliser
        if not hasattr(self, 'api_frame') or not hasattr(self, 'whisper_frame'):
            return
        
        if self.mode_var.get() == "local":
            # Mode local : afficher Whisper, masquer API
            if hasattr(self, 'api_frame'):
                self.api_frame.pack_forget()
            if hasattr(self, 'whisper_frame'):
                self.whisper_frame.pack(fill=tk.X, padx=10, pady=10)
            self._check_whisper()
            # Mettre à jour l'état du bouton
            self.root.after(100, self._update_load_model_button)
        else:
            # Mode API : afficher API, masquer Whisper
            # Si on passe en mode API, arrêter le chargement du modèle si en cours
            if self._model_loading_in_progress:
                print("[Configuration] Arrêt du chargement du modèle : passage en mode API")
                # Réinitialiser le flag
                self._model_loading_in_progress = False
                # Mettre à jour le statut immédiatement
                if hasattr(self, 'whisper_status_label'):
                    self.whisper_status_label.config(
                        text=self.lang.get("status_cancelled"),
                        foreground='orange'
                    )
                if hasattr(self, 'load_model_button'):
                    self.load_model_button.config(text=self.lang.get("load_model"), state="normal")
            
            # Arrêter aussi le chargement dans le service de transcription
            if self.app_instance and self.app_instance.transcription_service:
                if hasattr(self.app_instance.transcription_service, '_loading_in_progress'):
                    if self.app_instance.transcription_service._loading_in_progress:
                        print("[Configuration] Arrêt du chargement dans le service : passage en mode API")
                        self.app_instance.transcription_service._loading_in_progress = False
            
            if hasattr(self, 'whisper_frame'):
                self.whisper_frame.pack_forget()
            if hasattr(self, 'api_frame'):
                self.api_frame.pack(fill=tk.X, padx=10, pady=10)
            if hasattr(self, 'whisper_status_label'):
                self.whisper_status_label.config(text="")
            # La barre de progression n'est plus utilisée
            # self.whisper_progress.pack_forget()
            # self.whisper_progress.stop()
    
    def _check_whisper(self):
        """Vérifie la disponibilité de Whisper (sans charger le modèle)."""
        print("[Configuration] Vérification de Whisper...")
        service = TranscriptionService(
            mode="local", 
            whisper_model=self.whisper_model_var.get(),
            whisper_device=self.whisper_device_var.get()
        )
        is_available = service.is_whisper_available()
        
        if is_available:
            print("[Configuration] Whisper est disponible")
            # Ne pas appeler validate_configuration() car cela peut charger le modèle de manière synchrone
            # Juste indiquer que Whisper est disponible
            self.whisper_status_label.config(
                text=self.lang.get("status_ok"),
                foreground='#4EC9B0'
            )
        else:
            print("[Configuration] [ERREUR] Whisper n'est pas installe")
            self.whisper_status_label.config(
                text=self.lang.get("status_error_whisper_not_installed"),
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
        service = TranscriptionService(
            mode="local", 
            whisper_model=self.whisper_model_var.get(),
            whisper_device=self.whisper_device_var.get()
        )
        if not service.is_whisper_available():
            self.whisper_status_label.config(
                text=self.lang.get("status_error_whisper_not_installed"),
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
            self.load_model_button.config(text=self.lang.get("load_model_loading"), state="disabled")
        
        # Afficher l'indicateur de chargement
        model_name = self.whisper_model_var.get()
        self.whisper_status_label.config(
            text=self.lang.get("status_loading"),
            foreground='#4EC9B0'
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
                        self.root.after(0, lambda: self._on_model_loaded(False, model_name, self.lang.get("status_cancelled")))
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
                            foreground='#4EC9B0'
                        ))
                    
                    success = service.load_whisper_model(progress_callback=progress_callback)
                else:
                    # Créer un nouveau service pour le test
                    service = TranscriptionService(
                        mode="local", 
                        whisper_model=model_name,
                        whisper_device=self.whisper_device_var.get()
                    )
                    
                    # Callback pour mettre à jour l'interface avec la progression
                    def progress_callback(message):
                        """Met à jour l'interface avec le message de progression."""
                        self.root.after(0, lambda: self.whisper_status_label.config(
                            text=f"⏳ Téléchargement: {message}",
                            foreground='#4EC9B0'
                        ))
                    
                    success = service.load_whisper_model(progress_callback=progress_callback)
                    
                    # Si succès, mettre à jour le service de transcription de l'application
                    if success and self.app_instance and self.app_instance.transcription_service:
                        # Vérifier que le mode est toujours "local" avant de mettre à jour
                        if self.app_instance.transcription_service.mode == "local":
                            self.app_instance.transcription_service.whisper_model = model_name
                            self.app_instance.transcription_service.whisper_device = self.whisper_device_var.get()
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
                text=self.lang.get("status_ok"),
                foreground='#4EC9B0'
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
                text=f"{self.lang.get('status_error_general')}: {error_msg}",
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
                    self.load_model_button.config(text=self.lang.get("load_model_loaded"), state="normal")
                else:
                    self.load_model_button.config(text=self.lang.get("load_model"), state="normal")
            else:
                # Si pas d'instance, vérifier avec un nouveau service
                service = TranscriptionService(mode="local", whisper_model=self.whisper_model_var.get())
                if service.is_model_loaded():
                    self.load_model_button.config(text=self.lang.get("load_model_loaded"), state="normal")
                else:
                    self.load_model_button.config(text=self.lang.get("load_model"), state="normal")
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
    
    def _on_device_changed(self):
        """Appelé quand le device (CPU/GPU) change."""
        # Si un chargement est en cours, l'arrêter
        if self._model_loading_in_progress:
            print("[Configuration] Arrêt du chargement : changement de device")
            self._model_loading_in_progress = False
            if hasattr(self, 'load_model_button'):
                self.load_model_button.config(text="❌ Charger le modèle", state="normal")
        
        # Mettre à jour l'état du bouton (le modèle doit être rechargé avec le nouveau device)
        if self.mode_var.get() == "local":
            # Réinitialiser le modèle dans le service de l'application
            if self.app_instance and self.app_instance.transcription_service:
                self.app_instance.transcription_service.whisper_model_obj = None
                self.app_instance.transcription_service.whisper_device = self.whisper_device_var.get()
            self._update_load_model_button()
            # Ne pas charger automatiquement, l'utilisateur doit cliquer sur le bouton
    
    def _test_with_file(self):
        """Teste la transcription avec le fichier alexa_ciel.wav."""
        from pathlib import Path
        
        # Chercher le fichier alexa_ciel.wav
        test_file = Path("alexa_ciel.wav")
        if not test_file.exists():
            messagebox.showerror("Erreur", self.lang.get("test_file_not_found", file=str(test_file.absolute())))
            return
        
        mode = self.mode_var.get()
        
        if mode == "api":
            url = self.api_url_var.get().strip()
            token = self.api_token_var.get().strip()
            
            if not url or not token:
                messagebox.showerror("Erreur", self.lang.get("api_config_required"))
                return
            
            service = TranscriptionService(mode="api", api_url=url, api_token=token)
            result_label = self.test_result_label_api if hasattr(self, 'test_result_label_api') else None
        else:
            # Mode local
            whisper_model = self.whisper_model_var.get()
            whisper_device = self.whisper_device_var.get()
            service = TranscriptionService(
                mode="local", 
                whisper_model=whisper_model,
                whisper_device=whisper_device
            )
            result_label = self.test_result_label if hasattr(self, 'test_result_label') else None
        
        # Afficher un message de progression dans le label
        if result_label:
            result_label.config(text=self.lang.get("transcription_progress"), foreground='#4EC9B0')
        
        # Lancer la transcription dans un thread pour ne pas bloquer l'UI
        import threading
        
        def test_transcription():
            try:
                result = service.transcribe(str(test_file))
                self.root.after(0, lambda: self._show_test_result(result, mode, result_label))
            except Exception as e:
                self.root.after(0, lambda: self._show_test_error(str(e), result_label))
        
        thread = threading.Thread(target=test_transcription, daemon=True)
        thread.start()
    
    def _show_test_result(self, result, mode, result_label):
        """Affiche le résultat du test dans le label."""
        if result_label is None:
            # Fallback si le label n'existe pas
            if result is None:
                messagebox.showerror("Erreur", self.lang.get("no_result"))
            else:
                messagebox.showinfo("Résultat", str(result))
            return
        
        if result is None:
            result_label.config(text=self.lang.get("no_result"), foreground='red')
        else:
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
                    result_text = f"Delay: {delay} | Message: {message}"
                except (json.JSONDecodeError, AttributeError):
                    # Si ce n'est pas du JSON, afficher le texte directement
                    result_text = str(result)
            else:
                # En mode local, afficher juste le texte
                result_text = str(result)
            
            result_label.config(text=result_text, foreground='#4EC9B0')
    
    def _show_test_error(self, error_msg, result_label):
        """Affiche une erreur lors du test dans le label."""
        if result_label is None:
            # Fallback si le label n'existe pas
            messagebox.showerror("Erreur", self.lang.get("transcription_error", error=error_msg))
            return
        
        result_label.config(text=f"{self.lang.get('transcription_error', error=error_msg)}", foreground='red')
    
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
    
    def _reset_widget_position(self):
        """Réinitialise la position du widget à la position par défaut."""
        try:
            # Position par défaut
            default_x, default_y = 50, 50
            
            # Sauvegarder la nouvelle position dans la configuration
            self.config.set_widget_position(default_x, default_y)
            print(f"[Configuration] Position du widget réinitialisée à ({default_x}, {default_y})")
            
            # Mettre à jour le widget si disponible
            if self.app_instance and self.app_instance.widget:
                try:
                    # Utiliser after() pour s'assurer que l'appel se fait dans le bon thread Tkinter
                    self.app_instance.widget.root.after(0, lambda: self.app_instance.widget.set_position(default_x, default_y))
                    print(f"[Configuration] Widget déplacé à ({default_x}, {default_y})")
                except Exception as e:
                    print(f"[Configuration] Erreur lors du déplacement du widget: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Afficher un message de confirmation
            messagebox.showinfo(
                self.lang.get("window_title"),
                self.lang.get("widget_position_reset")
            )
        except Exception as e:
            print(f"[Configuration] Erreur dans _reset_widget_position: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror(
                "Erreur",
                f"Erreur lors de la réinitialisation de la position: {e}"
            )
    
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
        self.config.set("whisper.device", self.whisper_device_var.get())
        
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
        
        # Changer le bouton et enlever le focus
        self.hotkey_change_button.config(state="disabled")
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
        
        # Restaurer le bouton (avec icône si disponible)
        if hasattr(self, 'hotkey_refresh_icon'):
            self.hotkey_change_button.config(image=self.hotkey_refresh_icon, state="normal")
        else:
            self.hotkey_change_button.config(text="↻", state="normal")
        
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
                text=self.lang.get("press_keys"),
                font=('Arial', 9),
                foreground='#4EC9B0'
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
                    key_label = ttk.Button(
                        self.hotkey_keys_frame,
                        text=mod,
                        style="Accent.TButton"
                    )
                    key_label.pack(side=tk.LEFT, padx=2)
                    key_label.config(state="disabled")  # Désactiver pour qu'il ressemble à une étiquette

                # Afficher la touche principale
                key_display = key.title() if key else "Space"
                key_label = ttk.Button(
                    self.hotkey_keys_frame,
                    text=key_display,
                    style="Accent.TButton"
                )
                key_label.pack(side=tk.LEFT, padx=2)
                key_label.config(state="disabled")  # Désactiver pour qu'il ressemble à une étiquette
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
        
        # Réappliquer le style de la barre de titre au cas où il n'aurait pas été appliqué
        if HAS_PYWINSTYLES:
            try:
                import sys
                if sys.platform == 'win32':
                    theme = getattr(self, 'current_theme', 'dark')
                    if theme == "dark":
                        pywinstyles.apply_style(self.root, "dark")
                    else:
                        pywinstyles.apply_style(self.root, "light")
            except Exception as e:
                print(f"[Configuration] Erreur lors de l'application du style de barre de titre: {e}")
    
    def _on_window_close(self):
        """Gère la fermeture de la fenêtre."""
        # Arrêter le monitoring du thème
        self._theme_monitor_running = False
        # Masquer la fenêtre au lieu de la détruire (pour pouvoir la rouvrir)
        self.root.withdraw()

