#!/usr/bin/env python3
"""
Script de test pour vérifier l'installation des dépendances
"""

import sys

def test_dependencies():
    """Tester la disponibilité des dépendances"""
    
    print("🔍 Test des dépendances Python...")
    print("=" * 50)
    
    errors = []
    warnings = []
    
    # Test caldav
    try:
        import caldav
        print("✅ caldav: OK")
    except ImportError:
        errors.append("caldav")
        print("❌ caldav: MANQUANT")
    
    # Test vobject
    try:
        import vobject
        print("✅ vobject: OK")
    except ImportError:
        errors.append("vobject")
        print("❌ vobject: MANQUANT")
    
    # Test fuzzywuzzy (optionnel)
    try:
        from fuzzywuzzy import fuzz
        print("✅ fuzzywuzzy: OK")
    except ImportError:
        warnings.append("fuzzywuzzy")
        print("⚠️  fuzzywuzzy: MANQUANT (optionnel)")
    
    # Test python-Levenshtein (optionnel)
    try:
        import Levenshtein
        print("✅ python-Levenshtein: OK")
    except ImportError:
        warnings.append("python-Levenshtein")
        print("⚠️  python-Levenshtein: MANQUANT (optionnel)")
    
    # Test des modules standards
    standard_modules = ['argparse', 'getpass', 're', 'sys', 'urllib.parse', 'logging', 'io', 'collections']
    
    for module in standard_modules:
        try:
            __import__(module)
        except ImportError:
            errors.append(module)
            print(f"❌ {module}: MANQUANT (module standard)")
    
    print("\n" + "=" * 50)
    print("📊 Résumé du test:")
    
    if not errors:
        print("🎉 Toutes les dépendances critiques sont installées !")
        
        if warnings:
            print(f"⚠️  {len(warnings)} dépendance(s) optionnelle(s) manquante(s):")
            for warning in warnings:
                print(f"   - {warning}")
            print("\nNote: Les modules optionnels améliorent la détection des doublons")
            print("mais ne sont pas critiques pour le fonctionnement de base.")
        
        print("\n✅ Votre installation est prête à être utilisée !")
        return True
    else:
        print(f"❌ {len(errors)} dépendance(s) critique(s) manquante(s):")
        for error in errors:
            print(f"   - {error}")
        
        print("\n🛠️  Pour installer les dépendances manquantes:")
        print("   pip install -r requirements.txt")
        print("\n   Ou utilisez le script d'installation:")
        print("   ./install.sh")
        
        return False

def test_script_syntax():
    """Tester la syntaxe du script principal"""
    
    print("\n🔍 Test de la syntaxe du script principal...")
    print("=" * 50)
    
    try:
        import nextcloud_duplicate_remover
        print("✅ Script principal: Syntaxe OK")
        return True
    except SyntaxError as e:
        print(f"❌ Erreur de syntaxe: {e}")
        return False
    except ImportError as e:
        print(f"⚠️  Dépendances manquantes mais syntaxe OK: {e}")
        return True
    except Exception as e:
        print(f"⚠️  Autre erreur: {e}")
        return True

def main():
    """Fonction principale de test"""
    
    print("🧪 Test de l'installation Nextcloud Contact Duplicate Remover")
    print("=" * 60)
    print(f"🐍 Version Python: {sys.version}")
    print("=" * 60)
    
    deps_ok = test_dependencies()
    syntax_ok = test_script_syntax()
    
    print("\n" + "=" * 60)
    print("🏁 RÉSULTAT FINAL:")
    
    if deps_ok and syntax_ok:
        print("🎉 SUCCÈS: Installation complète et fonctionnelle !")
        print("\n🚀 Vous pouvez maintenant utiliser le script:")
        print("   python3 nextcloud_duplicate_remover.py --help")
        return 0
    elif syntax_ok:
        print("⚠️  PARTIEL: Le script fonctionne mais des dépendances sont manquantes")
        print("   Exécutez: ./install.sh")
        return 1
    else:
        print("❌ ÉCHEC: Problèmes critiques détectés")
        return 2

if __name__ == "__main__":
    sys.exit(main())
