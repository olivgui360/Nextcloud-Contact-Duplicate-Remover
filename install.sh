#!/bin/bash

# Script d'installation pour Nextcloud Contact Duplicate Remover
# Ce script installe automatiquement les dépendances nécessaires

echo "🚀 Installation de Nextcloud Contact Duplicate Remover"
echo "=================================================="

# Vérifier que Python 3 est installé
if ! command -v python3 &> /dev/null; then
    echo "❌ Erreur: Python 3 n'est pas installé."
    echo "   Installez Python 3 avant de continuer."
    exit 1
fi

echo "✅ Python 3 détecté: $(python3 --version)"

# Vérifier que pip est installé
if ! command -v pip3 &> /dev/null && ! command -v pip &> /dev/null; then
    echo "❌ Erreur: pip n'est pas installé."
    echo "   Installez pip avant de continuer:"
    echo "   sudo apt install python3-pip   # Ubuntu/Debian"
    echo "   sudo yum install python3-pip   # CentOS/RHEL"
    exit 1
fi

# Utiliser pip3 si disponible, sinon pip
PIP_CMD="pip3"
if ! command -v pip3 &> /dev/null; then
    PIP_CMD="pip"
fi

echo "✅ pip détecté: $($PIP_CMD --version)"

# Créer un environnement virtuel (optionnel mais recommandé)
read -p "🤔 Voulez-vous créer un environnement virtuel Python ? (recommandé) [Y/n]: " create_venv
create_venv=${create_venv:-Y}

if [[ $create_venv =~ ^[Yy]$ ]]; then
    echo "📦 Création de l'environnement virtuel..."
    python3 -m venv venv
    
    if [ $? -eq 0 ]; then
        echo "✅ Environnement virtuel créé"
        echo "📋 Pour l'activer à l'avenir, utilisez:"
        echo "   source venv/bin/activate"
        echo ""
        
        # Activer l'environnement virtuel
        source venv/bin/activate
        PIP_CMD="pip"  # Dans le venv, on utilise pip directement
    else
        echo "⚠️  Impossible de créer l'environnement virtuel, installation globale..."
    fi
fi

# Installer les dépendances
echo "📚 Installation des dépendances Python..."
$PIP_CMD install -r requirements.txt

if [ $? -eq 0 ]; then
    echo "✅ Dépendances installées avec succès !"
else
    echo "❌ Erreur lors de l'installation des dépendances."
    exit 1
fi

# Rendre le script principal exécutable
chmod +x nextcloud_duplicate_remover.py

echo ""
echo "🎉 Installation terminée avec succès !"
echo "=================================================="
echo ""
echo "🚀 Utilisation :"
echo ""

if [[ $create_venv =~ ^[Yy]$ ]] && [ -d "venv" ]; then
    echo "1️⃣  Activez l'environnement virtuel :"
    echo "   source venv/bin/activate"
    echo ""
fi

echo "2️⃣  Mode dry-run (recommandé en premier) :"
echo "   python3 nextcloud_duplicate_remover.py api https://votre-nextcloud.com votre_utilisateur"
echo ""
echo "3️⃣  Suppression réelle des doublons :"
echo "   python3 nextcloud_duplicate_remover.py api https://votre-nextcloud.com votre_utilisateur --delete"
echo ""
echo "4️⃣  Aide complète :"
echo "   python3 nextcloud_duplicate_remover.py --help"
echo ""
echo "📖 Consultez le README.md pour plus de détails et d'exemples."
echo ""
echo "⚠️  IMPORTANT: Faites toujours une sauvegarde de vos contacts avant utilisation !"
