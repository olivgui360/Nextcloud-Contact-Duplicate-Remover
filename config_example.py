#!/usr/bin/env python3
"""
Fichier de configuration d'exemple pour Nextcloud Contact Duplicate Remover

Copiez ce fichier vers 'config.py' et ajustez les valeurs selon vos besoins.
ATTENTION: N'ajoutez jamais ce fichier à un système de contrôle de version
si vous y mettez des mots de passe !
"""

# Configuration Nextcloud
NEXTCLOUD_CONFIG = {
    # URL de votre instance Nextcloud (avec https://)
    'server_url': 'https://votre-nextcloud.com',
    
    # Nom d'utilisateur Nextcloud
    'username': 'votre_nom_utilisateur',
    
    # Mot de passe (laisser vide pour saisie interactive)
    # ATTENTION: Ne pas stocker de mots de passe en clair !
    'password': '',
    
    # Seuil de similarité pour la détection des noms similaires (0-100)
    # 85 est une valeur équilibrée
    # - Plus élevé = plus strict (moins de faux positifs)
    # - Plus bas = plus permissif (plus de doublons détectés)
    'similarity_threshold': 85,
}

# Configuration du logging
LOGGING_CONFIG = {
    # Niveau de log: 'DEBUG', 'INFO', 'WARNING', 'ERROR'
    'level': 'INFO',
    
    # Format des messages de log
    'format': '%(asctime)s - %(levelname)s - %(message)s',
    
    # Fichier de log (optionnel, laisser vide pour affichage console uniquement)
    'log_file': '',
}

# Configuration de la détection des doublons
DUPLICATE_DETECTION_CONFIG = {
    # Critères de détection des doublons (True = activer, False = désactiver)
    'detect_by_email': True,        # Même adresse email
    'detect_by_phone': True,        # Même numéro de téléphone
    'detect_by_name_similarity': True,  # Noms similaires
    
    # Normalisation des numéros de téléphone
    'normalize_phone_numbers': True,
    
    # Ignorer la casse pour les emails
    'ignore_email_case': True,
}

# Configuration de sélection du meilleur contact
CONTACT_SELECTION_CONFIG = {
    # Pondération pour choisir le meilleur contact parmi les doublons
    # Plus la valeur est élevée, plus le critère est important
    'weights': {
        'email_count': 2,       # Nombre d'adresses email
        'phone_count': 2,       # Nombre de numéros de téléphone
        'has_full_name': 5,     # Présence d'un nom complet
        'vcard_richness': 1,    # Richesse des informations vCard
        'has_organization': 3,  # Présence d'une organisation
        'has_address': 3,       # Présence d'une adresse
        'has_birthday': 2,      # Présence d'une date de naissance
    }
}

# Configuration de sécurité
SECURITY_CONFIG = {
    # Toujours demander confirmation avant suppression
    'require_confirmation': True,
    
    # Mode dry-run par défaut (recommandé)
    'default_dry_run': True,
    
    # Créer une sauvegarde automatique avant suppression
    'auto_backup': True,
    
    # Répertoire pour les sauvegardes
    'backup_directory': './backups',
}

# Configuration avancée
ADVANCED_CONFIG = {
    # Timeout pour les requêtes réseau (secondes)
    'network_timeout': 30,
    
    # Nombre maximum de tentatives de reconnexion
    'max_retry_attempts': 3,
    
    # Délai entre les tentatives (secondes)
    'retry_delay': 2,
    
    # Traitement par lot (nombre de contacts à traiter en une fois)
    'batch_size': 50,
}


def load_config():
    """
    Charge la configuration depuis ce fichier.
    
    Usage dans le script principal:
        try:
            from config import load_config
            config = load_config()
        except ImportError:
            # Utiliser la configuration par défaut
            config = default_config
    """
    return {
        'nextcloud': NEXTCLOUD_CONFIG,
        'logging': LOGGING_CONFIG,
        'duplicate_detection': DUPLICATE_DETECTION_CONFIG,
        'contact_selection': CONTACT_SELECTION_CONFIG,
        'security': SECURITY_CONFIG,
        'advanced': ADVANCED_CONFIG,
    }


def validate_config(config):
    """
    Valide la configuration chargée.
    
    Args:
        config: Configuration à valider
        
    Returns:
        bool: True si valide, False sinon
        
    Raises:
        ValueError: Si la configuration est invalide
    """
    
    # Vérifier l'URL Nextcloud
    server_url = config['nextcloud']['server_url']
    if not server_url.startswith(('http://', 'https://')):
        raise ValueError("L'URL du serveur doit commencer par http:// ou https://")
    
    # Vérifier le nom d'utilisateur
    username = config['nextcloud']['username']
    if not username or not username.strip():
        raise ValueError("Le nom d'utilisateur ne peut pas être vide")
    
    # Vérifier le seuil de similarité
    threshold = config['nextcloud']['similarity_threshold']
    if not isinstance(threshold, int) or not 0 <= threshold <= 100:
        raise ValueError("Le seuil de similarité doit être un entier entre 0 et 100")
    
    # Vérifier le niveau de logging
    valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    if config['logging']['level'] not in valid_log_levels:
        raise ValueError(f"Niveau de log invalide. Doit être un de: {valid_log_levels}")
    
    return True


if __name__ == "__main__":
    """Test de la configuration"""
    try:
        config = load_config()
        validate_config(config)
        print("✅ Configuration valide !")
        
        print("\n📋 Résumé de la configuration:")
        print(f"   Serveur: {config['nextcloud']['server_url']}")
        print(f"   Utilisateur: {config['nextcloud']['username']}")
        print(f"   Seuil similarité: {config['nextcloud']['similarity_threshold']}%")
        print(f"   Niveau de log: {config['logging']['level']}")
        
    except Exception as e:
        print(f"❌ Erreur de configuration: {e}")
        exit(1)
