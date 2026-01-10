"""
Module de traitement intelligent du texte transcrit.
Gère la capitalisation, les points, et les remplacements de mots-clés.
"""
import time
import re
from typing import Optional, Dict, List, Tuple


class TextProcessor:
    """Gestionnaire de traitement intelligent du texte."""
    
    def __init__(self, keywords: Optional[Dict[str, str]] = None):
        """
        Initialise le processeur de texte.
        
        Args:
            keywords: Dictionnaire de mots-clés et leurs remplacements
        """
        self.keywords = keywords or {}
        self.last_transcription_time = None
        self.last_transcription_text = ""
        self.timeout_seconds = 120  # 2 minutes
    
    def process(self, text: str) -> str:
        """
        Traite le texte transcrit avec toutes les règles intelligentes.
        
        Args:
            text: Texte brut de la transcription
        
        Returns:
            Texte traité et formaté
        """
        if not text:
            return ""
        
        # Sauvegarder le texte original pour vérifier les mots-clés
        original_text = text
        
        # Vérifier si un mot-clé qui produit un point a été utilisé (avant remplacement)
        has_explicit_period_keyword = False
        for keyword, replacement in self.keywords.items():
            if '.' in replacement:
                # Vérifier si le mot-clé est présent dans le texte original
                if re.search(r'\b' + re.escape(keyword) + r'\b', original_text, re.IGNORECASE):
                    has_explicit_period_keyword = True
                    break
        
        # Appliquer les remplacements de mots-clés
        text = self._apply_keyword_replacements(text)
        
        # Supprimer les points en fin de phrase (sauf si dicté explicitement via mot-clé)
        if not has_explicit_period_keyword:
            text = text.rstrip('.')
        
        # Gérer la capitalisation
        text = self._apply_smart_capitalization(text)
        
        # Mettre à jour l'historique
        self.last_transcription_time = time.time()
        self.last_transcription_text = text
        
        return text
    
    def _apply_keyword_replacements(self, text: str) -> str:
        """
        Applique les remplacements de mots-clés.
        
        Args:
            text: Texte à traiter
        
        Returns:
            Texte avec remplacements appliqués
        """
        if not self.keywords:
            return text
        
        # Trier les mots-clés par longueur décroissante pour éviter les remplacements partiels
        sorted_keywords = sorted(self.keywords.items(), key=lambda x: len(x[0]), reverse=True)
        
        result = text
        for keyword, replacement in sorted_keywords:
            # Utiliser une regex pour remplacer le mot-clé (insensible à la casse, mais respecter les limites de mots)
            pattern = r'\b' + re.escape(keyword) + r'\b'
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        
        return result
    
    
    def _apply_smart_capitalization(self, text: str) -> str:
        """
        Applique la capitalisation intelligente.
        
        Règles:
        - Pas de majuscule si la transcription précédente se terminait par une virgule
        - Majuscule si plus de 2 minutes se sont écoulées depuis la dernière transcription
        - Majuscule en début de phrase normale
        
        Args:
            text: Texte à traiter
        
        Returns:
            Texte avec capitalisation appliquée
        """
        if not text:
            return text
        
        # Vérifier si on doit mettre une majuscule
        should_capitalize = False
        
        # Règle 1: Si plus de 2 minutes se sont écoulées, mettre une majuscule
        if self.last_transcription_time is None:
            should_capitalize = True
        else:
            elapsed = time.time() - self.last_transcription_time
            if elapsed > self.timeout_seconds:
                should_capitalize = True
        
        # Règle 2: Si la dernière transcription se terminait par une virgule, pas de majuscule
        if self.last_transcription_text and self.last_transcription_text.rstrip().endswith(','):
            should_capitalize = False
        
        # Appliquer la capitalisation
        if should_capitalize and text:
            # Mettre la première lettre en majuscule
            text = text[0].upper() + text[1:] if len(text) > 1 else text.upper()
        
        return text
    
    def update_keywords(self, keywords: Dict[str, str]):
        """
        Met à jour la liste des mots-clés.
        
        Args:
            keywords: Nouveau dictionnaire de mots-clés
        """
        self.keywords = keywords.copy() if keywords else {}
    
    def reset_history(self):
        """Réinitialise l'historique des transcriptions."""
        self.last_transcription_time = None
        self.last_transcription_text = ""
