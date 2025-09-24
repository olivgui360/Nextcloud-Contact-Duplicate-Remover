# Nextcloud Contact Duplicate Remover

Ce script Python permet de supprimer automatiquement les contacts en doublon dans Nextcloud. Il offre deux modes d'utilisation selon vos préférences.

## 🚀 Installation

1. **Cloner ou télécharger ce répertoire**

2. **Installer les dépendances Python :**
   ```bash
   pip install -r requirements.txt
   ```

## 📋 Fonctionnalités

- ✅ **Deux modes d'utilisation** : API CardDAV directe ou traitement de fichier vCard
- ✅ **Détection intelligente des doublons** : par email, téléphone ou similarité de nom
- ✅ **Mode dry-run** : visualiser les doublons avant suppression
- ✅ **Choix automatique du meilleur contact** : garde le contact le plus complet
- ✅ **Logging détaillé** : suivi complet des opérations
- ✅ **Gestion sécurisée des mots de passe** : saisie masquée

## 🛠️ Utilisation

### Mode 1 : API CardDAV (Recommandé)

Ce mode se connecte directement à votre instance Nextcloud via l'API CardDAV.

**Étape 1 - Visualiser les doublons (dry-run) :**
```bash
python nextcloud_duplicate_remover.py api https://votre-nextcloud.com votre_nom_utilisateur
```

**Étape 2 - Supprimer les doublons :**
```bash
python nextcloud_duplicate_remover.py api https://votre-nextcloud.com votre_nom_utilisateur --delete
```

**Options avancées :**
```bash
# Ajuster le seuil de similarité des noms (par défaut : 85%)
python nextcloud_duplicate_remover.py api https://votre-nextcloud.com votre_nom_utilisateur --threshold 90 --delete
```

### Mode 2 : Fichier vCard

Ce mode traite un fichier vCard exporté depuis Nextcloud.

**Étape 1 - Exporter vos contacts depuis Nextcloud :**
- Allez dans l'application Contacts de Nextcloud
- Cliquez sur l'icône ⚙️ en bas à gauche
- Choisissez "Télécharger" pour exporter au format vCard

**Étape 2 - Traiter le fichier :**
```bash
python nextcloud_duplicate_remover.py file contacts_exportes.vcf contacts_sans_doublons.vcf
```

**Étape 3 - Réimporter le fichier nettoyé :**
- Retournez dans l'application Contacts de Nextcloud
- Supprimez l'ancien carnet d'adresses (optionnel)
- Importez le fichier `contacts_sans_doublons.vcf`

## 🔍 Comment ça marche ?

Le script détecte les doublons selon plusieurs critères :

1. **Email identique** : Deux contacts avec le même email sont considérés comme doublons
2. **Téléphone identique** : Deux contacts avec le même numéro (après nettoyage)
3. **Nom similaire** : Utilise un algorithme de similarité pour détecter les noms proches

Quand des doublons sont trouvés, le script :
- Garde automatiquement le contact le plus complet (plus d'informations)
- Supprime les autres contacts du groupe
- Affiche un résumé des opérations

## ⚙️ Configuration

### Variables d'environnement (optionnel)

Vous pouvez définir ces variables pour éviter de saisir les informations à chaque fois :

```bash
export NEXTCLOUD_URL="https://votre-nextcloud.com"
export NEXTCLOUD_USER="votre_nom_utilisateur"
```

### Personnalisation du seuil de similarité

Le paramètre `--threshold` contrôle la sensibilité de détection des noms similaires :
- **90-100** : Très strict (noms quasi-identiques seulement)
- **85** (défaut) : Équilibré (recommandé)
- **70-84** : Plus permissif (risque de faux positifs)

## 🛡️ Sécurité et Sauvegardes

⚠️ **IMPORTANT** : Toujours faire une sauvegarde avant utilisation !

1. **Sauvegarde manuelle :**
   - Exportez vos contacts depuis Nextcloud avant d'utiliser le script

2. **Test en dry-run :**
   - Utilisez toujours le mode dry-run d'abord pour vérifier les doublons détectés

3. **Mot de passe :**
   - Le script demande le mot de passe de manière sécurisée (saisie masquée)
   - Aucun mot de passe n'est stocké dans le script

## 📊 Exemple de sortie

```
2024-01-15 10:30:15 - INFO - Connexion à https://mon-nextcloud.com/remote.php/dav/addressbooks/users/simon/...
2024-01-15 10:30:16 - INFO - Connecté au carnet d'adresses: Contacts
2024-01-15 10:30:17 - INFO - Récupération de tous les contacts...
2024-01-15 10:30:18 - INFO - Récupération terminée: 248 contacts trouvés
2024-01-15 10:30:19 - INFO - Recherche des doublons...
2024-01-15 10:30:20 - INFO - Trouvé 12 groupes de doublons
2024-01-15 10:30:20 - INFO - Contacts à supprimer: 18
2024-01-15 10:30:20 - INFO - === MODE DRY-RUN : Aucune suppression effectuée ===

group_0:
  [GARDER] Jean Dupont (jean.dupont@email.com, jean@work.com)
  [SUPPRIMER] Jean Dupont (jean.dupont@email.com)
  [SUPPRIMER] J. Dupont (jean.dupont@email.com)

group_1:
  [GARDER] Marie Martin (marie.martin@company.fr, +33123456789)
  [SUPPRIMER] Marie Martin (marie.martin@company.fr)

...

ℹ️  Mode dry-run: 30 doublons trouvés (utilisez --delete pour les supprimer)
```

## ❓ Dépannage

### Erreur de connexion
```
ERREUR: Impossible de se connecter à Nextcloud
```
- Vérifiez l'URL de votre Nextcloud (avec https://)
- Vérifiez vos identifiants
- Assurez-vous que l'application Contacts est activée dans Nextcloud

### Bibliothèques manquantes
```
ERREUR: La bibliothèque caldav n'est pas installée
```
- Exécutez : `pip install -r requirements.txt`

### Aucun doublon trouvé
- Ajustez le seuil avec `--threshold` (valeur plus faible)
- Vérifiez que vos contacts ont bien des informations communes (email, nom)

## 📝 Notes importantes

- Le script fonctionne avec Nextcloud 20+ (testé avec les versions récentes)
- Compatible Python 3.6+
- Les suppressions sont définitives (d'où l'importance du dry-run)
- Le script respecte la structure des carnets d'adresses Nextcloud
- Fonctionne aussi avec d'autres serveurs CardDAV compatibles

## 🤝 Contribution

N'hésitez pas à signaler des bugs ou proposer des améliorations !

## 📄 Licence

Ce script est fourni tel quel, à des fins éducatives et d'usage personnel. Utilisez-le à vos propres risques.
