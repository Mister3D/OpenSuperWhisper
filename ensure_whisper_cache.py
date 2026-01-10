"""
Script utilitaire pour s'assurer que le cache Whisper fonctionne correctement
dans l'exécutable. Ce script peut être inclus dans l'exécutable pour vérifier
que le répertoire de cache existe et est accessible.
"""
import os
from pathlib import Path


def ensure_whisper_cache_dir():
    """
    S'assure que le répertoire de cache Whisper existe et est accessible.
    Retourne le chemin du répertoire de cache.
    """
    # Whisper utilise ~/.cache/whisper/ par défaut
    # Sur Windows: %USERPROFILE%\.cache\whisper\
    cache_dir = Path.home() / ".cache" / "whisper"
    
    try:
        # Créer le répertoire s'il n'existe pas
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Vérifier que le répertoire est accessible en écriture
        test_file = cache_dir / ".test_write"
        try:
            test_file.write_text("test")
            test_file.unlink()
        except Exception as e:
            print(f"[Cache] [WARNING] Le répertoire de cache n'est pas accessible en écriture: {e}")
            print(f"[Cache] [WARNING] Chemin: {cache_dir}")
            return None
        
        return str(cache_dir)
    except Exception as e:
        print(f"[Cache] [ERREUR] Impossible de créer le répertoire de cache: {e}")
        print(f"[Cache] [ERREUR] Chemin: {cache_dir}")
        return None


if __name__ == "__main__":
    cache_path = ensure_whisper_cache_dir()
    if cache_path:
        print(f"[Cache] [OK] Répertoire de cache Whisper: {cache_path}")
    else:
        print("[Cache] [ERREUR] Le répertoire de cache Whisper n'est pas accessible")
