"""
Module d'insertion automatique de texte.
"""
import time
from pynput.keyboard import Key, Controller
from typing import Optional
import pyperclip


class TextInserter:
    """Gestionnaire d'insertion de texte."""
    
    def __init__(self):
        """Initialise le gestionnaire d'insertion de texte."""
        self.keyboard = Controller()
    
    def insert_text(self, text: str) -> bool:
        """
        Insère du texte à l'emplacement du curseur.
        
        Args:
            text: Texte à insérer
        
        Returns:
            True si l'insertion a réussi, False sinon
        """
        if not text:
            return False
        
        try:
            # Méthode 1: Simulation de frappe caractère par caractère
            # Cette méthode fonctionne avec la plupart des applications
            for char in text:
                if char == '\n':
                    self.keyboard.press(Key.enter)
                    self.keyboard.release(Key.enter)
                elif char == '\t':
                    self.keyboard.press(Key.tab)
                    self.keyboard.release(Key.tab)
                else:
                    self.keyboard.type(char)
                # Petit délai pour éviter les problèmes de timing
                time.sleep(0.01)
            
            return True
            
        except Exception as e:
            print(f"Erreur lors de l'insertion de texte: {e}")
            # Fallback: copier dans le presse-papiers
            try:
                pyperclip.copy(text)
                return False  # Indique qu'on a utilisé le fallback
            except Exception:
                return False
    
    def insert_text_via_clipboard(self, text: str) -> bool:
        """
        Insère du texte via le presse-papiers (Ctrl+V).
        Cette méthode peut être plus fiable dans certains cas.
        
        Args:
            text: Texte à insérer
        
        Returns:
            True si l'insertion a réussi, False sinon
        """
        if not text:
            return False
        
        try:
            # Sauvegarder le contenu actuel du presse-papiers
            old_clipboard = None
            try:
                old_clipboard = pyperclip.paste()
            except Exception:
                pass
            
            # Copier le nouveau texte
            pyperclip.copy(text)
            
            # Coller avec Ctrl+V
            self.keyboard.press(Key.ctrl)
            self.keyboard.press('v')
            self.keyboard.release('v')
            self.keyboard.release(Key.ctrl)
            
            # Restaurer l'ancien contenu après un court délai
            if old_clipboard is not None:
                time.sleep(0.1)
                try:
                    pyperclip.copy(old_clipboard)
                except Exception:
                    pass
            
            return True
            
        except Exception as e:
            print(f"Erreur lors de l'insertion via presse-papiers: {e}")
            return False
    
    def insert_text_smart(self, text: str) -> bool:
        """
        Tente d'insérer le texte avec plusieurs méthodes.
        
        Args:
            text: Texte à insérer
        
        Returns:
            True si l'insertion a réussi, False sinon
        """
        # Essayer d'abord la méthode standard
        if self.insert_text(text):
            return True
        
        # Si échec, essayer via presse-papiers
        if self.insert_text_via_clipboard(text):
            return True
        
        # Dernier recours: copier dans le presse-papiers
        try:
            pyperclip.copy(text)
            return False  # Indique qu'on a utilisé le fallback
        except Exception:
            return False

