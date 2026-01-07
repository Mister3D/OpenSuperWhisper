"""
Script de test pour vérifier que tous les modules fonctionnent correctement.
"""
import sys
import traceback

def test_imports():
    """Teste l'importation de tous les modules."""
    print("Test d'importation des modules...")
    modules = [
        'config',
        'audio_feedback',
        'audio_recorder',
        'transcription',
        'text_inserter',
        'widget',
        'system_tray',
        'config_ui',
        'main'
    ]
    
    failed = []
    for module in modules:
        try:
            __import__(module)
            print(f"  [OK] {module}")
        except Exception as e:
            print(f"  [FAIL] {module}: {e}")
            failed.append(module)
            traceback.print_exc()
    
    if failed:
        print(f"\n[ERROR] {len(failed)} module(s) ont echoue")
        return False
    else:
        print("\n[OK] Tous les modules sont importables")
        return True

def test_config():
    """Teste le module de configuration."""
    print("\nTest du module de configuration...")
    try:
        from config import Config
        config = Config()
        print(f"  [OK] Configuration chargee")
        print(f"  [OK] Mode: {config.get('mode')}")
        print(f"  [OK] Raccourci: {config.get_hotkey_string()}")
        return True
    except Exception as e:
        print(f"  [FAIL] Erreur: {e}")
        traceback.print_exc()
        return False

def test_audio_recorder():
    """Teste le module d'enregistrement audio."""
    print("\nTest du module d'enregistrement audio...")
    try:
        from audio_recorder import AudioRecorder
        recorder = AudioRecorder()
        devices = recorder.list_devices()
        print(f"  [OK] {len(devices)} peripherique(s) audio detecte(s)")
        return True
    except Exception as e:
        print(f"  [FAIL] Erreur: {e}")
        traceback.print_exc()
        return False

def test_transcription():
    """Teste le module de transcription."""
    print("\nTest du module de transcription...")
    try:
        from transcription import TranscriptionService
        service = TranscriptionService(mode="api")
        is_available = service.is_whisper_available()
        print(f"  [OK] Whisper disponible: {is_available}")
        return True
    except Exception as e:
        print(f"  [FAIL] Erreur: {e}")
        traceback.print_exc()
        return False

def main():
    """Lance tous les tests."""
    print("=" * 50)
    print("Tests des modules OpenSuperWhisper")
    print("=" * 50)
    
    results = []
    results.append(("Imports", test_imports()))
    results.append(("Configuration", test_config()))
    results.append(("Enregistrement audio", test_audio_recorder()))
    results.append(("Transcription", test_transcription()))
    
    print("\n" + "=" * 50)
    print("Résultats:")
    print("=" * 50)
    
    for name, result in results:
        status = "[OK]" if result else "[FAIL]"
        print(f"{status} {name}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print("\n[OK] Tous les tests sont passes!")
        return 0
    else:
        print("\n[ERROR] Certains tests ont echoue")
        return 1

if __name__ == "__main__":
    sys.exit(main())

