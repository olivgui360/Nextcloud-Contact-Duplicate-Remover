#!/usr/bin/env python3
"""
Nextcloud Contact & Calendar Duplicate Remover
===============================================

Ce script permet de supprimer les doublons dans Nextcloud :
- Contacts en doublon via CardDAV
- Événements d'agenda en doublon via CalDAV

Modes d'utilisation :
1. Mode API : Connexion directe (recommandé)
2. Mode fichier : Traitement de fichiers exportés (contacts seulement)

Auteur: Assistant IA
Date: 2024
"""

import argparse
import getpass
import re
import sys
import urllib.parse
from typing import Dict, List, Tuple, Optional, Set
from collections import defaultdict
import logging
import io

try:
    import caldav
    from caldav.elements import dav, cdav
    CALDAV_AVAILABLE = True
except ImportError:
    CALDAV_AVAILABLE = False

try:
    import vobject
    VOBJECT_AVAILABLE = True
except ImportError:
    VOBJECT_AVAILABLE = False

try:
    from fuzzywuzzy import fuzz
    FUZZYWUZZY_AVAILABLE = True
except ImportError:
    FUZZYWUZZY_AVAILABLE = False


class NextcloudContactManager:
    """Gestionnaire des contacts Nextcloud via CardDAV"""
    
    def __init__(self, server_url: str, username: str, password: str):
        if not CALDAV_AVAILABLE:
            raise ImportError("La bibliothèque caldav n'est pas disponible. Installez-la avec: pip install caldav")
        
        self.server_url = server_url.rstrip('/')
        self.username = username
        self.password = password
        self.client = None
        self.addressbook = None
        
        # Configuration du logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
    
    def connect(self) -> bool:
        """Établir la connexion avec Nextcloud"""
        try:
            # URL CardDAV pour Nextcloud
            cardav_url = f"{self.server_url}/remote.php/dav/addressbooks/users/{self.username}/"
            
            self.logger.info(f"Connexion à {cardav_url}...")
            
            self.client = caldav.DAVClient(
                url=cardav_url,
                username=self.username,
                password=self.password
            )
            
            # Tester la connexion et obtenir le principal
            self.logger.info("Test de la connexion...")
            principal = self.client.principal()
            self.logger.info(f"Principal URL: {principal.url}")
            
            # Debug : lister toutes les collections
            try:
                collections = principal.collections()
                self.logger.info(f"Collections trouvées: {len(collections)}")
                for i, coll in enumerate(collections):
                    self.logger.info(f"Collection {i+1}: {coll.url}")
                    try:
                        props = coll.get_properties(['{DAV:}displayname', '{DAV:}resourcetype'])
                        self.logger.info(f"  - Nom: {props.get('{DAV:}displayname', 'N/A')}")
                        self.logger.info(f"  - Type: {props.get('{DAV:}resourcetype', 'N/A')}")
                    except:
                        pass
            except Exception as e:
                self.logger.warning(f"Impossible de lister les collections: {e}")
            
            # Méthode compatible avec caldav 2.x
            addressbooks = []
            try:
                # Version récente de caldav (2.x)
                addressbooks = principal.calendars(comp_filter="VCARD")
                self.logger.debug("Utilisation de l'API caldav 2.x")
                if addressbooks:
                    self.logger.info(f"Trouvé {len(addressbooks)} carnet(s) avec calendars()")
            except (AttributeError, TypeError) as e:
                self.logger.debug(f"Échec API 2.x: {e}")
                
            if not addressbooks:
                try:
                    # Fallback pour les versions plus anciennes
                    addressbooks = principal.addressbooks()
                    self.logger.debug("Utilisation de l'API caldav 1.x")
                    if addressbooks:
                        self.logger.info(f"Trouvé {len(addressbooks)} carnet(s) avec addressbooks()")
                except AttributeError as e:
                    self.logger.debug(f"Échec API 1.x: {e}")
                    
            if not addressbooks:
                # Méthode alternative pour certaines versions
                self.logger.info("Recherche manuelle des carnets d'adresses...")
                
                # Essayer de trouver les carnets d'adresses manuellement
                try:
                    from caldav.elements import dav, cdav
                    collections = principal.collections()
                    for collection in collections:
                        try:
                            # Vérifier si c'est un carnet d'adresses
                            props = collection.get_properties([
                                '{DAV:}resourcetype',
                                '{urn:ietf:params:xml:ns:carddav}addressbook',
                                '{DAV:}displayname'
                            ])
                            
                            resource_type = props.get('{DAV:}resourcetype', '')
                            if 'addressbook' in str(resource_type).lower():
                                addressbooks.append(collection)
                                self.logger.info(f"Carnet d'adresses trouvé: {collection.url}")
                        except Exception as e3:
                            self.logger.debug(f"Erreur inspection collection: {e3}")
                            continue
                except Exception as e2:
                    self.logger.debug(f"Erreur lors de la recherche manuelle: {e2}")
            
            # Essayer une approche directe si aucun carnet trouvé
            if not addressbooks:
                self.logger.info("Tentative d'accès direct au carnet d'adresses...")
                try:
                    # Créer directement un objet addressbook avec l'URL complète
                    direct_addressbook_url = f"{self.server_url}/remote.php/dav/addressbooks/users/{self.username}/contacts/"
                    self.logger.info(f"Test URL directe: {direct_addressbook_url}")
                    
                    # Créer un client pour l'URL directe
                    direct_client = caldav.DAVClient(
                        url=direct_addressbook_url,
                        username=self.username,
                        password=self.password
                    )
                    
                    # Essayer d'accéder directement au carnet
                    # Créer un carnet d'adresses avec la nouvelle API 2.x
                    from caldav.objects import Calendar
                    direct_addressbook = Calendar(client=direct_client, url=direct_addressbook_url)
                    
                    # Tester s'il y a des contacts
                    test_objects = direct_addressbook.objects()
                    self.logger.info(f"Carnet d'adresses direct accessible, objets trouvés: {len(list(test_objects))}")
                    
                    addressbooks = [direct_addressbook]
                    self.client = direct_client
                    
                except Exception as e_direct:
                    self.logger.debug(f"Accès direct échoué: {e_direct}")
                    
                    # Essayer avec "personal" au lieu de "contacts"
                    try:
                        direct_addressbook_url = f"{self.server_url}/remote.php/dav/addressbooks/users/{self.username}/personal/"
                        self.logger.info(f"Test URL personnelle: {direct_addressbook_url}")
                        
                        direct_client = caldav.DAVClient(
                            url=direct_addressbook_url,
                            username=self.username,
                            password=self.password
                        )
                        
                        # Créer un carnet d'adresses avec la nouvelle API 2.x
                        from caldav.objects import Calendar
                        direct_addressbook = Calendar(client=direct_client, url=direct_addressbook_url)
                        
                        test_objects = direct_addressbook.objects()
                        self.logger.info(f"Carnet personnel accessible, objets trouvés: {len(list(test_objects))}")
                        
                        addressbooks = [direct_addressbook]
                        self.client = direct_client
                        
                    except Exception as e_personal:
                        self.logger.debug(f"Accès personnel échoué: {e_personal}")
                        
                        # Dernière tentative avec auto-découverte
                        try:
                            self.logger.info("Tentative d'auto-découverte CardDAV...")
                            root_url = f"{self.server_url}/remote.php/dav/"
                            discovery_client = caldav.DAVClient(
                                url=root_url,
                                username=self.username,
                                password=self.password
                            )
                            
                            # Tenter de trouver les carnets d'adresses via PROPFIND
                            from caldav.lib.url import URL
                            from caldav.lib import vcal
                            import requests
                            
                            # Requête PROPFIND pour découvrir les carnets d'adresses
                            propfind_url = f"{self.server_url}/remote.php/dav/addressbooks/users/{self.username}/"
                            auth = (self.username, self.password)
                            
                            headers = {
                                'Content-Type': 'application/xml',
                                'Depth': '1'
                            }
                            
                            propfind_body = '''<?xml version="1.0" encoding="utf-8"?>
<d:propfind xmlns:d="DAV:" xmlns:card="urn:ietf:params:xml:ns:carddav">
  <d:prop>
    <d:displayname />
    <d:resourcetype />
    <card:addressbook />
  </d:prop>
</d:propfind>'''
                            
                            response = requests.request('PROPFIND', propfind_url, 
                                                      data=propfind_body, headers=headers, auth=auth)
                            
                            if response.status_code == 207:  # Multi-Status
                                self.logger.info("PROPFIND réussi, analyse de la réponse...")
                                self.logger.debug(f"Réponse PROPFIND: {response.text}")
                                
                                # Parser la réponse pour trouver les carnets d'adresses
                                import xml.etree.ElementTree as ET
                                root = ET.fromstring(response.text)
                                
                                for response_elem in root.findall('.//{DAV:}response'):
                                    href_elem = response_elem.find('.//{DAV:}href')
                                    if href_elem is not None:
                                        href = href_elem.text
                                        if href.endswith('/') and 'addressbooks' in href and href != f"/remote.php/dav/addressbooks/users/{self.username}/":
                                            # Éviter l'URL racine, chercher les sous-carnets
                                            full_url = f"{self.server_url}{href}" if not href.startswith('http') else href
                                            self.logger.info(f"Carnet d'adresses trouvé: {full_url}")
                                            
                                            try:
                                                # Créer un carnet d'adresses pour cette URL
                                                found_client = caldav.DAVClient(url=full_url, username=self.username, password=self.password)
                                                from caldav.objects import Calendar
                                                found_addressbook = Calendar(client=found_client, url=full_url)
                                                
                                                # Tester l'accès
                                                test_objects = list(found_addressbook.objects())
                                                self.logger.info(f"Carnet fonctionnel avec {len(test_objects)} objets")
                                                
                                                addressbooks.append(found_addressbook)
                                                self.client = found_client
                                                
                                            except Exception as e_test:
                                                self.logger.debug(f"Erreur test carnet {full_url}: {e_test}")
                                        elif href.endswith('/') and 'addressbooks' in href:
                                            # C'est probablement le dossier racine, faire un PROPFIND plus profond
                                            self.logger.debug(f"Dossier racine trouvé: {href}")
                                            
                                            # PROPFIND pour trouver les carnets dans ce dossier
                                            sub_propfind_url = f"{self.server_url}{href}"
                                            sub_response = requests.request('PROPFIND', sub_propfind_url, 
                                                                          data=propfind_body, headers=headers, auth=auth)
                                            
                                            if sub_response.status_code == 207:
                                                self.logger.debug(f"Sous-PROPFIND réponse: {sub_response.text}")
                                                sub_root = ET.fromstring(sub_response.text)
                                                
                                                for sub_response_elem in sub_root.findall('.//{DAV:}response'):
                                                    sub_href_elem = sub_response_elem.find('.//{DAV:}href')
                                                    if sub_href_elem is not None:
                                                        sub_href = sub_href_elem.text
                                                        if sub_href.endswith('/') and sub_href != href and 'addressbooks' in sub_href:
                                                            sub_full_url = f"{self.server_url}{sub_href}" if not sub_href.startswith('http') else sub_href
                                                            self.logger.info(f"Sous-carnet d'adresses trouvé: {sub_full_url}")
                                                            
                                                            try:
                                                                sub_client = caldav.DAVClient(url=sub_full_url, username=self.username, password=self.password)
                                                                from caldav.objects import Calendar
                                                                sub_addressbook = Calendar(client=sub_client, url=sub_full_url)
                                                                
                                                                # Tester l'accès
                                                                sub_test_objects = list(sub_addressbook.objects())
                                                                self.logger.info(f"Sous-carnet fonctionnel avec {len(sub_test_objects)} objets")
                                                                
                                                                addressbooks.append(sub_addressbook)
                                                                self.client = sub_client
                                                                
                                                            except Exception as e_sub_test:
                                                                self.logger.debug(f"Erreur test sous-carnet {sub_full_url}: {e_sub_test}")
                            else:
                                self.logger.debug(f"PROPFIND échoué: {response.status_code}")
                                
                        except Exception as e_discovery:
                            self.logger.debug(f"Auto-découverte échouée: {e_discovery}")
            
            if not addressbooks:
                self.logger.error("Aucun carnet d'adresses trouvé")
                self.logger.info("Vérifiez que l'application Contacts est activée dans Nextcloud")
                return False
            
            # Prendre le premier carnet d'adresses
            self.addressbook = addressbooks[0]
            
            # Essayer d'obtenir le nom du carnet d'adresses
            try:
                addressbook_name = self.addressbook.name
            except:
                try:
                    addressbook_name = getattr(self.addressbook, 'displayname', 'Inconnu')
                except:
                    addressbook_name = "Carnet d'adresses principal"
            
            self.logger.info(f"Connecté au carnet d'adresses: {addressbook_name}")
            self.logger.info(f"Nombre de carnets d'adresses trouvés: {len(addressbooks)}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur de connexion: {e}")
            self.logger.debug("Détails de l'erreur:", exc_info=True)
            
            # Suggestions de dépannage
            self.logger.info("Suggestions de dépannage:")
            self.logger.info("1. Vérifiez l'URL de votre Nextcloud")
            self.logger.info("2. Vérifiez vos identifiants")
            self.logger.info("3. Assurez-vous que l'application Contacts est activée")
            self.logger.info("4. Vérifiez que l'accès CardDAV est autorisé")
            
            return False
    
    def get_all_contacts(self) -> List[Dict]:
        """Récupérer tous les contacts du carnet d'adresses"""
        if not self.addressbook:
            raise Exception("Pas de connexion établie")
        
        self.logger.info("Récupération de tous les contacts...")
        contacts_data = []
        
        try:
            # Méthode compatible avec les différentes versions de caldav
            try:
                # Pour les carnets d'adresses, utiliser directement objects()
                contacts = self.addressbook.objects()
                self.logger.debug("Utilisation de la méthode objects() directe")
            except Exception as e:
                self.logger.debug(f"Erreur avec objects(): {e}")
                try:
                    # Méthode alternative pour certaines versions
                    contacts = self.addressbook.search(comp_class="VCARD")
                    self.logger.debug("Utilisation de la méthode search() alternative")
                except Exception as e2:
                    self.logger.debug(f"Erreur avec search(): {e2}")
                    # Dernier recours : obtenir tous les objets via children
                    contacts = list(getattr(self.addressbook, 'children', []))
                    self.logger.debug("Utilisation de la méthode children")
            
            for contact in contacts:
                try:
                    # Dans caldav 2.x, les données peuvent être accessibles différemment
                    vcard_data = None
                    
                    # Essayer différentes méthodes pour obtenir les données vCard
                    if hasattr(contact, 'data') and contact.data:
                        vcard_data = contact.data
                    elif hasattr(contact, 'load') and callable(contact.load):
                        contact.load()
                        if hasattr(contact, 'data') and contact.data:
                            vcard_data = contact.data
                    elif hasattr(contact, 'get_data') and callable(contact.get_data):
                        vcard_data = contact.get_data()
                    elif hasattr(contact, 'icalendar_component'):
                        # Pour certaines versions, les données sont dans icalendar_component
                        vcard_data = str(contact.icalendar_component)
                    elif hasattr(contact, 'vobject_instance'):
                        # Pour d'autres versions
                        vcard_data = str(contact.vobject_instance)
                    
                    if not vcard_data:
                        self.logger.debug(f"Aucune donnée vCard trouvée pour {contact}")
                        continue
                    
                    # Si c'est un objet bytes, le décoder
                    if isinstance(vcard_data, bytes):
                        vcard_data = vcard_data.decode('utf-8')
                    
                    parsed_vcard = vobject.readOne(vcard_data)
                    
                    contact_info = {
                        'uid': contact.id,
                        'vcard_object': contact,
                        'parsed_vcard': parsed_vcard,
                        'raw_data': vcard_data
                    }
                    
                    # Extraire les informations principales
                    if hasattr(parsed_vcard, 'fn'):
                        contact_info['full_name'] = parsed_vcard.fn.value
                    
                    if hasattr(parsed_vcard, 'n'):
                        n = parsed_vcard.n.value
                        contact_info['family_name'] = n.family
                        contact_info['given_name'] = n.given
                    
                    # Emails
                    emails = []
                    for email in parsed_vcard.contents.get('email', []):
                        emails.append(email.value.lower())
                    contact_info['emails'] = emails
                    
                    # Téléphones
                    phones = []
                    for tel in parsed_vcard.contents.get('tel', []):
                        # Nettoyer le numéro de téléphone
                        phone_clean = re.sub(r'[^\d+]', '', tel.value)
                        phones.append(phone_clean)
                    contact_info['phones'] = phones
                    
                    contacts_data.append(contact_info)
                    
                except Exception as e:
                    self.logger.warning(f"Erreur lors du parsing d'un contact: {e}")
                    continue
            
            self.logger.info(f"Récupération terminée: {len(contacts_data)} contacts trouvés")
            return contacts_data
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des contacts: {e}")
            return []
    
    def find_duplicates(self, contacts: List[Dict], similarity_threshold: int = 85) -> Dict[str, List[Dict]]:
        """
        Identifier les contacts en doublon
        
        Args:
            contacts: Liste des contacts
            similarity_threshold: Seuil de similarité pour considérer deux contacts comme doublons (0-100)
        
        Returns:
            Dictionnaire avec les groupes de doublons
        """
        if not FUZZYWUZZY_AVAILABLE:
            self.logger.warning("fuzzywuzzy non disponible, utilisation d'une méthode de comparaison simple")
            return self._find_duplicates_simple(contacts)
        
        self.logger.info("Recherche des doublons...")
        
        duplicate_groups = defaultdict(list)
        processed = set()
        
        for i, contact1 in enumerate(contacts):
            if i in processed:
                continue
                
            group_key = f"group_{len(duplicate_groups)}"
            duplicates = [contact1]
            processed.add(i)
            
            for j, contact2 in enumerate(contacts[i+1:], start=i+1):
                if j in processed:
                    continue
                
                if self._are_duplicates(contact1, contact2, similarity_threshold):
                    duplicates.append(contact2)
                    processed.add(j)
            
            if len(duplicates) > 1:
                duplicate_groups[group_key] = duplicates
        
        self.logger.info(f"Trouvé {len(duplicate_groups)} groupes de doublons")
        return dict(duplicate_groups)
    
    def _find_duplicates_simple(self, contacts: List[Dict]) -> Dict[str, List[Dict]]:
        """Méthode simple de détection des doublons sans fuzzywuzzy"""
        duplicate_groups = defaultdict(list)
        processed = set()
        
        # Grouper par email exact ou nom exact
        email_groups = defaultdict(list)
        name_groups = defaultdict(list)
        
        for i, contact in enumerate(contacts):
            if i in processed:
                continue
            
            # Grouper par email
            for email in contact.get('emails', []):
                if email:
                    email_groups[email].append((i, contact))
            
            # Grouper par nom complet
            full_name = contact.get('full_name', '').strip().lower()
            if full_name:
                name_groups[full_name].append((i, contact))
        
        # Créer les groupes de doublons
        group_counter = 0
        
        # Doublons par email
        for email, contacts_list in email_groups.items():
            if len(contacts_list) > 1:
                group_key = f"group_{group_counter}"
                duplicates = []
                for idx, contact in contacts_list:
                    if idx not in processed:
                        duplicates.append(contact)
                        processed.add(idx)
                if len(duplicates) > 1:
                    duplicate_groups[group_key] = duplicates
                    group_counter += 1
        
        # Doublons par nom (pour ceux non encore traités)
        for name, contacts_list in name_groups.items():
            if len(contacts_list) > 1:
                group_key = f"group_{group_counter}"
                duplicates = []
                for idx, contact in contacts_list:
                    if idx not in processed:
                        duplicates.append(contact)
                        processed.add(idx)
                if len(duplicates) > 1:
                    duplicate_groups[group_key] = duplicates
                    group_counter += 1
        
        return dict(duplicate_groups)
    
    def _are_duplicates(self, contact1: Dict, contact2: Dict, threshold: int) -> bool:
        """Déterminer si deux contacts sont des doublons"""
        
        # Vérification par email exact
        emails1 = set(contact1.get('emails', []))
        emails2 = set(contact2.get('emails', []))
        if emails1 and emails2 and emails1.intersection(emails2):
            return True
        
        # Vérification par téléphone exact
        phones1 = set(contact1.get('phones', []))
        phones2 = set(contact2.get('phones', []))
        if phones1 and phones2 and phones1.intersection(phones2):
            return True
        
        # Vérification par similarité de nom
        name1 = contact1.get('full_name', '').strip()
        name2 = contact2.get('full_name', '').strip()
        
        if name1 and name2:
            similarity = fuzz.ratio(name1.lower(), name2.lower())
            if similarity >= threshold:
                return True
        
        return False
    
    def choose_best_contact(self, duplicates: List[Dict]) -> Dict:
        """
        Choisir le meilleur contact parmi les doublons
        Critères : plus d'informations, plus récent, etc.
        """
        if len(duplicates) == 1:
            return duplicates[0]
        
        # Scorer chaque contact
        scored_contacts = []
        
        for contact in duplicates:
            score = 0
            
            # Points pour les informations disponibles
            if contact.get('emails'):
                score += len(contact['emails']) * 2
            if contact.get('phones'):
                score += len(contact['phones']) * 2
            if contact.get('full_name'):
                score += 5
            
            # Points pour la richesse du vCard
            vcard_str = contact.get('raw_data', '')
            score += len(vcard_str.split('\n')) * 1
            
            scored_contacts.append((score, contact))
        
        # Retourner le contact avec le meilleur score
        scored_contacts.sort(key=lambda x: x[0], reverse=True)
        best_contact = scored_contacts[0][1]
        
        self.logger.debug(f"Contact choisi: {best_contact.get('full_name', 'Sans nom')} (score: {scored_contacts[0][0]})")
        
        return best_contact
    
    def delete_contact(self, contact: Dict) -> bool:
        """Supprimer un contact"""
        try:
            vcard_object = contact['vcard_object']
            vcard_object.delete()
            self.logger.debug(f"Contact supprimé: {contact.get('full_name', contact['uid'])}")
            return True
        except Exception as e:
            self.logger.error(f"Erreur lors de la suppression du contact {contact.get('full_name', contact['uid'])}: {e}")
            return False
    
    def remove_duplicates(self, dry_run: bool = True) -> Tuple[int, int]:
        """
        Supprimer les contacts en doublon
        
        Args:
            dry_run: Si True, ne fait que simuler les suppressions
        
        Returns:
            Tuple (nombre_de_doublons_trouvés, nombre_de_contacts_supprimés)
        """
        contacts = self.get_all_contacts()
        if not contacts:
            return 0, 0
        
        duplicate_groups = self.find_duplicates(contacts)
        
        if not duplicate_groups:
            self.logger.info("Aucun doublon trouvé !")
            return 0, 0
        
        total_duplicates = sum(len(group) for group in duplicate_groups.values())
        total_to_delete = total_duplicates - len(duplicate_groups)  # On garde un contact par groupe
        
        self.logger.info(f"Trouvé {len(duplicate_groups)} groupes de doublons ({total_duplicates} contacts)")
        self.logger.info(f"Contacts à supprimer: {total_to_delete}")
        
        if dry_run:
            self.logger.info("=== MODE DRY-RUN : Aucune suppression effectuée ===")
            for group_name, duplicates in duplicate_groups.items():
                best = self.choose_best_contact(duplicates)
                self.logger.info(f"\n{group_name}:")
                for contact in duplicates:
                    status = "GARDER" if contact == best else "SUPPRIMER"
                    name = contact.get('full_name', 'Sans nom')
                    emails = ', '.join(contact.get('emails', []))
                    self.logger.info(f"  [{status}] {name} ({emails})")
            return total_duplicates, 0
        
        # Suppression réelle
        deleted_count = 0
        for group_name, duplicates in duplicate_groups.items():
            best = self.choose_best_contact(duplicates)
            
            for contact in duplicates:
                if contact != best:
                    if self.delete_contact(contact):
                        deleted_count += 1
        
        self.logger.info(f"Suppression terminée: {deleted_count} contacts supprimés")
        return total_duplicates, deleted_count


class VCardFileProcessor:
    """Processeur de fichiers vCard pour la suppression de doublons"""
    
    def __init__(self):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
    
    def process_vcf_file(self, input_file: str, output_file: str) -> int:
        """
        Traiter un fichier vCard pour supprimer les doublons exacts
        
        Args:
            input_file: Chemin vers le fichier d'entrée
            output_file: Chemin vers le fichier de sortie
        
        Returns:
            Nombre de doublons supprimés
        """
        if not VOBJECT_AVAILABLE:
            raise ImportError("La bibliothèque vobject n'est pas disponible. Installez-la avec: pip install vobject")
        
        self.logger.info(f"Traitement du fichier: {input_file}")
        
        # Pattern pour identifier les vCards
        rec = re.compile(r'(^BEGIN:VCARD.*?^END:VCARD)([\x0d\x0a]*)', re.M | re.S)
        
        unique_contacts = set()
        duplicates_removed = 0
        
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            with open(output_file, 'w', encoding='utf-8') as g:
                position = 0
                
                while True:
                    match = rec.search(content, position)
                    if not match:
                        # Écrire le reste du fichier
                        g.write(content[position:])
                        break
                    
                    # Écrire le contenu avant la vCard
                    g.write(content[position:match.start(1)])
                    
                    vcard_content = match.group(1)
                    
                    if vcard_content not in unique_contacts:
                        # Nouveau contact, l'ajouter
                        g.write(vcard_content)
                        g.write(match.group(2))  # Retours à la ligne
                        unique_contacts.add(vcard_content)
                    else:
                        # Doublon détecté
                        duplicates_removed += 1
                        self.logger.debug(f"Doublon supprimé (contact #{duplicates_removed})")
                    
                    position = match.end(2)
            
            self.logger.info(f"Traitement terminé: {duplicates_removed} doublons supprimés")
            self.logger.info(f"Fichier de sortie: {output_file}")
            
            return duplicates_removed
            
        except Exception as e:
            self.logger.error(f"Erreur lors du traitement du fichier: {e}")
            raise


class NextcloudCalendarManager:
    """Gestionnaire des calendriers/événements Nextcloud via CalDAV"""
    
    def __init__(self, server_url: str, username: str, password: str):
        if not CALDAV_AVAILABLE:
            raise ImportError("La bibliothèque caldav n'est pas disponible. Installez-la avec: pip install caldav")
        
        self.server_url = server_url.rstrip('/')
        self.username = username
        self.password = password
        self.client = None
        self.calendars = []
        
        # Configuration du logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
    
    def connect(self) -> bool:
        """Établir la connexion avec Nextcloud pour les calendriers"""
        try:
            # URL CalDAV pour Nextcloud
            caldav_url = f"{self.server_url}/remote.php/dav/calendars/{self.username}/"
            
            self.logger.info(f"Connexion aux calendriers : {caldav_url}...")
            
            self.client = caldav.DAVClient(
                url=caldav_url,
                username=self.username,
                password=self.password
            )
            
            # Tester la connexion
            self.logger.info("Test de la connexion aux calendriers...")
            principal = self.client.principal()
            self.logger.info(f"Principal URL: {principal.url}")
            
            # Obtenir tous les calendriers
            try:
                calendars = principal.calendars()
                self.logger.info(f"Calendriers trouvés via API standard: {len(calendars)}")
                self.calendars = calendars
            except Exception as e:
                self.logger.debug(f"Erreur API standard: {e}")
                
                # Méthode alternative pour découvrir les calendriers
                self.logger.info("Tentative de découverte manuelle des calendriers...")
                try:
                    import requests
                    
                    # PROPFIND pour découvrir les calendriers
                    propfind_url = caldav_url
                    auth = (self.username, self.password)
                    
                    headers = {
                        'Content-Type': 'application/xml',
                        'Depth': '1'
                    }
                    
                    propfind_body = '''<?xml version="1.0" encoding="utf-8"?>
<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
  <d:prop>
    <d:displayname />
    <d:resourcetype />
    <c:calendar />
  </d:prop>
</d:propfind>'''
                    
                    response = requests.request('PROPFIND', propfind_url, 
                                              data=propfind_body, headers=headers, auth=auth)
                    
                    if response.status_code == 207:  # Multi-Status
                        self.logger.info("PROPFIND réussi, analyse des calendriers...")
                        
                        # Parser la réponse pour trouver les calendriers
                        import xml.etree.ElementTree as ET
                        root = ET.fromstring(response.text)
                        
                        for response_elem in root.findall('.//{DAV:}response'):
                            href_elem = response_elem.find('.//{DAV:}href')
                            if href_elem is not None:
                                href = href_elem.text
                                if href.endswith('/') and href != f"/remote.php/dav/calendars/{self.username}/":
                                    # C'est probablement un calendrier
                                    full_url = f"{self.server_url}{href}" if not href.startswith('http') else href
                                    
                                    try:
                                        cal_client = caldav.DAVClient(url=full_url, username=self.username, password=self.password)
                                        from caldav.objects import Calendar
                                        calendar = Calendar(client=cal_client, url=full_url)
                                        
                                        # Récupérer le nom du calendrier
                                        try:
                                            name_elem = response_elem.find('.//{DAV:}displayname')
                                            calendar_name = name_elem.text if name_elem is not None else "Sans nom"
                                        except:
                                            calendar_name = href.split('/')[-2] if '/' in href else "Inconnu"
                                        
                                        calendar.name = calendar_name
                                        self.calendars.append(calendar)
                                        self.logger.info(f"Calendrier trouvé: {calendar_name}")
                                        
                                    except Exception as e_cal:
                                        self.logger.debug(f"Erreur création calendrier {full_url}: {e_cal}")
                    
                except Exception as e_discovery:
                    self.logger.debug(f"Auto-découverte échouée: {e_discovery}")
            
            if not self.calendars:
                self.logger.error("Aucun calendrier trouvé")
                self.logger.info("Vérifiez que l'application Calendrier est activée dans Nextcloud")
                return False
            
            self.logger.info(f"Connexion réussie : {len(self.calendars)} calendrier(s) trouvé(s)")
            for cal in self.calendars:
                cal_name = getattr(cal, 'name', 'Inconnu')
                self.logger.info(f"  - {cal_name}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur de connexion aux calendriers: {e}")
            return False
    
    def get_calendar_by_name(self, calendar_name: str):
        """Obtenir un calendrier spécifique par son nom"""
        for calendar in self.calendars:
            cal_name = getattr(calendar, 'name', 'Inconnu')
            if cal_name.lower() == calendar_name.lower():
                return calendar
        return None
    
    def get_all_events(self, calendar_name: str = None) -> List[Dict]:
        """Récupérer tous les événements d'un calendrier ou de tous les calendriers"""
        if not self.calendars:
            raise Exception("Pas de connexion établie")
        
        # Sélectionner le calendrier
        if calendar_name:
            target_calendars = [self.get_calendar_by_name(calendar_name)]
            if not target_calendars[0]:
                self.logger.error(f"Calendrier '{calendar_name}' non trouvé")
                available_names = [getattr(cal, 'name', 'Inconnu') for cal in self.calendars]
                self.logger.info(f"Calendriers disponibles: {available_names}")
                return []
        else:
            target_calendars = self.calendars
        
        all_events = []
        
        for calendar in target_calendars:
            if not calendar:
                continue
                
            cal_name = getattr(calendar, 'name', 'Inconnu')
            self.logger.info(f"Récupération des événements du calendrier: {cal_name}")
            
            try:
                # Obtenir tous les événements
                events = calendar.events()
                self.logger.info(f"Trouvé {len(events)} événement(s) dans {cal_name}")
                
                for event in events:
                    try:
                        # Obtenir les données iCal de l'événement
                        ical_data = None
                        
                        if hasattr(event, 'data') and event.data:
                            ical_data = event.data
                        elif hasattr(event, 'load') and callable(event.load):
                            event.load()
                            if hasattr(event, 'data') and event.data:
                                ical_data = event.data
                        
                        if not ical_data:
                            self.logger.debug(f"Aucune donnée iCal trouvée pour l'événement")
                            continue
                        
                        # Parser l'événement iCal
                        if isinstance(ical_data, bytes):
                            ical_data = ical_data.decode('utf-8')
                        
                        parsed_event = vobject.readOne(ical_data)
                        
                        event_info = {
                            'uid': getattr(event, 'id', 'unknown'),
                            'calendar_name': cal_name,
                            'calendar_object': calendar,
                            'event_object': event,
                            'parsed_event': parsed_event,
                            'raw_data': ical_data
                        }
                        
                        # Extraire les informations principales
                        if hasattr(parsed_event, 'vevent'):
                            vevent = parsed_event.vevent
                            
                            # Titre
                            if hasattr(vevent, 'summary'):
                                event_info['title'] = vevent.summary.value
                            
                            # Description
                            if hasattr(vevent, 'description'):
                                event_info['description'] = vevent.description.value
                            
                            # Date de début
                            if hasattr(vevent, 'dtstart'):
                                event_info['start_date'] = vevent.dtstart.value
                            
                            # Date de fin
                            if hasattr(vevent, 'dtend'):
                                event_info['end_date'] = vevent.dtend.value
                                
                            # Récurrence
                            if hasattr(vevent, 'rrule'):
                                event_info['rrule'] = str(vevent.rrule.value)
                        
                        all_events.append(event_info)
                        
                    except Exception as e:
                        self.logger.warning(f"Erreur lors du parsing d'un événement: {e}")
                        continue
                        
            except Exception as e:
                self.logger.error(f"Erreur lors de la récupération des événements de {cal_name}: {e}")
                continue
        
        self.logger.info(f"Récupération terminée: {len(all_events)} événement(s) au total")
        return all_events
    
    def find_event_duplicates(self, events: List[Dict], similarity_threshold: int = 85) -> Dict[str, List[Dict]]:
        """Identifier les événements en doublon"""
        self.logger.info("Recherche des doublons d'événements...")
        
        duplicate_groups = defaultdict(list)
        processed = set()
        
        for i, event1 in enumerate(events):
            if i in processed:
                continue
                
            group_key = f"event_group_{len(duplicate_groups)}"
            duplicates = [event1]
            processed.add(i)
            
            for j, event2 in enumerate(events[i+1:], start=i+1):
                if j in processed:
                    continue
                
                if self._are_events_duplicates(event1, event2, similarity_threshold):
                    duplicates.append(event2)
                    processed.add(j)
            
            if len(duplicates) > 1:
                duplicate_groups[group_key] = duplicates
        
        self.logger.info(f"Trouvé {len(duplicate_groups)} groupes de doublons d'événements")
        return dict(duplicate_groups)
    
    def _are_events_duplicates(self, event1: Dict, event2: Dict, threshold: int) -> bool:
        """Déterminer si deux événements sont des doublons"""
        
        # Vérification par titre avec similarité
        title1 = event1.get('title', '').strip()
        title2 = event2.get('title', '').strip()
        
        if title1 and title2:
            if title1.lower() == title2.lower():
                # Titres identiques, vérifier la date
                date1 = event1.get('start_date')
                date2 = event2.get('start_date')
                
                if date1 and date2:
                    # Comparer les dates
                    try:
                        # Convertir en chaînes pour comparaison
                        date1_str = str(date1).split()[0] if hasattr(date1, 'date') else str(date1)[:10]
                        date2_str = str(date2).split()[0] if hasattr(date2, 'date') else str(date2)[:10]
                        
                        if date1_str == date2_str:
                            return True
                    except:
                        # Si erreur de conversion de date, considérer comme doublon si même titre
                        return True
                        
            elif FUZZYWUZZY_AVAILABLE and len(title1) > 3 and len(title2) > 3:
                # Similarité de titre
                similarity = fuzz.ratio(title1.lower(), title2.lower())
                if similarity >= threshold:
                    # Titres similaires, vérifier la date
                    date1 = event1.get('start_date')
                    date2 = event2.get('start_date')
                    
                    if date1 and date2:
                        try:
                            date1_str = str(date1).split()[0] if hasattr(date1, 'date') else str(date1)[:10]
                            date2_str = str(date2).split()[0] if hasattr(date2, 'date') else str(date2)[:10]
                            
                            if date1_str == date2_str:
                                return True
                        except:
                            pass
        
        return False
    
    def choose_best_event(self, duplicates: List[Dict]) -> Dict:
        """Choisir le meilleur événement parmi les doublons"""
        if len(duplicates) == 1:
            return duplicates[0]
        
        # Scorer chaque événement
        scored_events = []
        
        for event in duplicates:
            score = 0
            
            # Points pour les informations disponibles
            if event.get('description'):
                score += len(event['description']) * 0.1
            if event.get('title'):
                score += len(event['title']) * 0.2
            
            # Points pour la richesse des données iCal
            raw_data = event.get('raw_data', '')
            score += len(raw_data.split('\n')) * 0.5
            
            # Préférer les événements avec plus de propriétés
            parsed_event = event.get('parsed_event')
            if parsed_event and hasattr(parsed_event, 'vevent'):
                vevent = parsed_event.vevent
                # Compter les propriétés
                properties = [attr for attr in dir(vevent) if not attr.startswith('_') and hasattr(vevent, attr)]
                score += len(properties) * 0.3
            
            scored_events.append((score, event))
        
        # Retourner l'événement avec le meilleur score
        scored_events.sort(key=lambda x: x[0], reverse=True)
        best_event = scored_events[0][1]
        
        title = best_event.get('title', 'Sans titre')
        self.logger.debug(f"Événement choisi: {title} (score: {scored_events[0][0]:.1f})")
        
        return best_event
    
    def delete_event(self, event: Dict) -> bool:
        """Supprimer un événement"""
        try:
            event_object = event['event_object']
            event_object.delete()
            title = event.get('title', event['uid'])
            self.logger.debug(f"Événement supprimé: {title}")
            return True
        except Exception as e:
            title = event.get('title', event['uid'])
            self.logger.error(f"Erreur lors de la suppression de l'événement {title}: {e}")
            return False
    
    def remove_event_duplicates(self, calendar_name: str = None, dry_run: bool = True) -> Tuple[int, int]:
        """Supprimer les événements en doublon"""
        events = self.get_all_events(calendar_name)
        if not events:
            return 0, 0
        
        duplicate_groups = self.find_event_duplicates(events)
        
        if not duplicate_groups:
            self.logger.info("Aucun doublon d'événement trouvé !")
            return 0, 0
        
        total_duplicates = sum(len(group) for group in duplicate_groups.values())
        total_to_delete = total_duplicates - len(duplicate_groups)  # On garde un événement par groupe
        
        self.logger.info(f"Trouvé {len(duplicate_groups)} groupes de doublons ({total_duplicates} événements)")
        self.logger.info(f"Événements à supprimer: {total_to_delete}")
        
        if dry_run:
            self.logger.info("=== MODE DRY-RUN : Aucune suppression effectuée ===")
            for group_name, duplicates in duplicate_groups.items():
                best = self.choose_best_event(duplicates)
                self.logger.info(f"\n{group_name}:")
                for event in duplicates:
                    status = "GARDER" if event == best else "SUPPRIMER"
                    title = event.get('title', 'Sans titre')
                    date_obj = event.get('start_date')
                    if date_obj:
                        try:
                            date_str = str(date_obj).split()[0] if hasattr(date_obj, 'date') else str(date_obj)[:10]
                        except:
                            date_str = 'Sans date'
                    else:
                        date_str = 'Sans date'
                    calendar = event.get('calendar_name', 'Inconnu')
                    self.logger.info(f"  [{status}] {title} ({date_str}) - {calendar}")
            return total_duplicates, 0
        
        # Suppression réelle
        deleted_count = 0
        for group_name, duplicates in duplicate_groups.items():
            best = self.choose_best_event(duplicates)
            
            for event in duplicates:
                if event != best:
                    if self.delete_event(event):
                        deleted_count += 1
        
        self.logger.info(f"Suppression terminée: {deleted_count} événements supprimés")
        return total_duplicates, deleted_count
    
    def sync_birthday_calendar(self, contact_manager, calendar_name: str = "Anniversaire", dry_run: bool = True) -> Tuple[int, int, int]:
        """
        Synchroniser le calendrier d'anniversaires avec les dates de naissance des contacts
        
        Args:
            contact_manager: Instance de NextcloudContactManager
            calendar_name: Nom du calendrier d'anniversaires
            dry_run: Si True, ne fait que simuler les changements
        
        Returns:
            Tuple (événements_orphelins_trouvés, événements_supprimés, événements_créés)
        """
        self.logger.info(f"🎂 Synchronisation du calendrier '{calendar_name}' avec les contacts...")
        
        # 1. Récupérer tous les contacts avec dates de naissance
        self.logger.info("📇 Récupération des contacts et de leurs dates de naissance...")
        contacts_with_birthdays = self._get_contacts_with_birthdays(contact_manager)
        
        if not contacts_with_birthdays:
            self.logger.info("Aucun contact avec date de naissance trouvé")
            return 0, 0, 0
        
        self.logger.info(f"Trouvé {len(contacts_with_birthdays)} contact(s) avec date de naissance")
        
        # 2. Récupérer tous les événements du calendrier d'anniversaires
        birthday_events = self.get_all_events(calendar_name)
        if not birthday_events:
            self.logger.info(f"Aucun événement trouvé dans le calendrier '{calendar_name}'")
            return 0, 0, 0
        
        self.logger.info(f"Trouvé {len(birthday_events)} événement(s) dans le calendrier '{calendar_name}'")
        
        # 3. Faire la correspondance
        matched_events, orphan_birthday_events, non_birthday_events, missing_birthdays = self._match_birthdays_and_events(
            contacts_with_birthdays, birthday_events
        )
        
        self.logger.info(f"📊 Résultats de la correspondance:")
        self.logger.info(f"  - Événements correspondant aux contacts: {len(matched_events)}")
        self.logger.info(f"  - Événements d'anniversaire orphelins (à supprimer): {len(orphan_birthday_events)}")
        self.logger.info(f"  - Événements NON-anniversaires (à conserver): {len(non_birthday_events)}")
        self.logger.info(f"  - Anniversaires manquants (à créer): {len(missing_birthdays)}")
        
        if dry_run:
            self.logger.info("=== MODE DRY-RUN : Aucun changement effectué ===")
            
            if non_birthday_events:
                self.logger.info(f"\n⚠️  ATTENTION: {len(non_birthday_events)} événements NON-anniversaires détectés:")
                self.logger.info("    Ces événements seront CONSERVÉS et ne seront PAS supprimés:")
                for event in non_birthday_events:
                    title = event.get('title', 'Sans titre')
                    date_obj = event.get('start_date')
                    date_str = self._format_date_for_display(date_obj)
                    self.logger.info(f"  - ✅ {title} ({date_str})")
            
            if orphan_birthday_events:
                self.logger.info(f"\n🗑️  Événements d'anniversaire à SUPPRIMER ({len(orphan_birthday_events)} orphelins):")
                for event in orphan_birthday_events:
                    title = event.get('title', 'Sans titre')
                    date_obj = event.get('start_date')
                    date_str = self._format_date_for_display(date_obj)
                    self.logger.info(f"  - {title} ({date_str})")
            
            if missing_birthdays:
                self.logger.info(f"\n➕ Anniversaires à CRÉER ({len(missing_birthdays)} manquants):")
                for contact_name, birthday_date in missing_birthdays:
                    self.logger.info(f"  - {contact_name} ({birthday_date})")
            
            return len(orphan_birthday_events), 0, 0
        
        # 4. Suppressions réelles
        deleted_count = 0
        if orphan_birthday_events:
            self.logger.info(f"🗑️  Suppression de {len(orphan_birthday_events)} événement(s) d'anniversaire orphelin(s)...")
            for event in orphan_birthday_events:
                if self.delete_event(event):
                    deleted_count += 1
        
        # 5. Créations réelles
        created_count = 0
        if missing_birthdays:
            self.logger.info(f"➕ Création de {len(missing_birthdays)} événement(s) d'anniversaire manquant(s)...")
            calendar = self.get_calendar_by_name(calendar_name)
            if calendar:
                for contact_name, birthday_date in missing_birthdays:
                    if self._create_birthday_event(calendar, contact_name, birthday_date):
                        created_count += 1
        
        self.logger.info(f"✅ Synchronisation terminée: {deleted_count} supprimés, {created_count} créés")
        return len(orphan_birthday_events), deleted_count, created_count
    
    def _get_contacts_with_birthdays(self, contact_manager) -> List[Tuple[str, str]]:
        """Récupérer tous les contacts avec leurs dates de naissance"""
        contacts_with_birthdays = []
        
        try:
            # Utiliser la méthode existante pour récupérer tous les contacts
            all_contacts = contact_manager.get_all_contacts()
            
            for contact_info in all_contacts:
                try:
                    # Extraire le nom du contact
                    contact_name = contact_info.get('name', '')
                    raw_vcard_data = contact_info.get('raw_data', '')
                    
                    # Si pas de nom, essayer d'extraire depuis les données vCard brutes
                    if not contact_name and raw_vcard_data:
                        import re
                        # Chercher FN: (Full Name)
                        fn_match = re.search(r'FN[^:]*:([^\r\n]+)', raw_vcard_data)
                        if fn_match:
                            contact_name = fn_match.group(1).strip()
                    
                    if not contact_name:
                        contact_name = 'Contact sans nom'
                    
                    # Chercher la date de naissance directement dans les données vCard brutes
                    birthday_str = None
                    
                    # Méthode 1: Chercher avec l'objet parsé vobject
                    if 'parsed_contact' in contact_info:
                        parsed_contact = contact_info['parsed_contact']
                        if hasattr(parsed_contact, 'bday'):
                            try:
                                birthday = parsed_contact.bday.value
                                if hasattr(birthday, 'strftime'):
                                    birthday_str = birthday.strftime('%m-%d')
                                elif hasattr(birthday, 'month') and hasattr(birthday, 'day'):
                                    birthday_str = f"{birthday.month:02d}-{birthday.day:02d}"
                                else:
                                    bday_str = str(birthday)
                                    if len(bday_str) >= 8:  # Format YYYYMMDD ou YYYY-MM-DD
                                        if '-' in bday_str:
                                            parts = bday_str.split('-')
                                            if len(parts) >= 3:
                                                birthday_str = f"{parts[1]}-{parts[2]}"
                                        else:
                                            # Format YYYYMMDD
                                            birthday_str = f"{bday_str[4:6]}-{bday_str[6:8]}"
                            except Exception as e:
                                self.logger.debug(f"Erreur parsing bday objet vobject: {e}")
                    
                    # Méthode 2: Chercher directement dans le texte vCard brut
                    if not birthday_str and raw_vcard_data:
                        import re
                        # Rechercher BDAY: suivi de la date
                        bday_match = re.search(r'BDAY[^:]*:([^\r\n]+)', raw_vcard_data)
                        if bday_match:
                            bday_value = bday_match.group(1).strip()
                            self.logger.debug(f"BDAY trouvé dans vCard brut: '{bday_value}'")
                            
                            # Parser différents formats de date
                            if len(bday_value) >= 8:
                                if '-' in bday_value:
                                    # Format YYYY-MM-DD
                                    parts = bday_value.split('-')
                                    if len(parts) >= 3:
                                        try:
                                            month = int(parts[1])
                                            day = int(parts[2])
                                            birthday_str = f"{month:02d}-{day:02d}"
                                        except ValueError:
                                            pass
                                elif len(bday_value) == 8 and bday_value.isdigit():
                                    # Format YYYYMMDD
                                    try:
                                        month = int(bday_value[4:6])
                                        day = int(bday_value[6:8])
                                        birthday_str = f"{month:02d}-{day:02d}"
                                    except ValueError:
                                        pass
                    
                    if birthday_str:
                        contacts_with_birthdays.append((contact_name, birthday_str))
                        self.logger.info(f"📅 Contact avec anniversaire: {contact_name} -> {birthday_str}")
                    
                except Exception as e:
                    self.logger.debug(f"Erreur lors de l'extraction de la date de naissance pour {contact_name}: {e}")
                    continue
        
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des contacts: {e}")
        
        return contacts_with_birthdays
    
    def _match_birthdays_and_events(self, contacts_with_birthdays: List[Tuple[str, str]], events: List[Dict]) -> Tuple[List[Dict], List[Dict], List[Dict], List[Tuple[str, str]]]:
        """
        Faire la correspondance entre contacts et événements d'anniversaire
        
        Retourne:
        - matched_events: Événements d'anniversaire qui correspondent à des contacts
        - orphan_birthday_events: Événements d'anniversaire orphelins (sans contact correspondant)
        - non_birthday_events: Événements qui ne sont PAS des anniversaires
        - missing_birthdays: Contacts sans événement d'anniversaire
        """
        matched_events = []
        orphan_birthday_events = []
        non_birthday_events = []
        contacts_dict = {name.lower(): (name, date) for name, date in contacts_with_birthdays}
        
        # Vérifier chaque événement
        for event in events:
            event_title = event.get('title', '')
            event_date = event.get('start_date')
            
            # D'abord, déterminer si c'est un événement d'anniversaire
            if not self._is_birthday_event(event_title):
                non_birthday_events.append(event)
                self.logger.debug(f"Événement non-anniversaire: {event_title}")
                continue
            
            # Si c'est un événement d'anniversaire, vérifier les correspondances
            event_title_lower = event_title.lower()
            contact_name_from_event = self._extract_contact_name_from_birthday_event(event_title_lower)
            
            # Chercher une correspondance
            found_match = False
            
            for contact_name_lower, (original_name, birthday_date) in contacts_dict.items():
                # Correspondance par nom
                if (contact_name_from_event.lower() in contact_name_lower or 
                    contact_name_lower in contact_name_from_event.lower() or
                    self._names_are_similar(contact_name_from_event, contact_name_lower)):
                    
                    # Vérifier aussi la date si possible
                    event_date_str = self._format_date_for_comparison(event_date)
                    if event_date_str and event_date_str == birthday_date:
                        matched_events.append(event)
                        found_match = True
                        self.logger.debug(f"Correspondance trouvée: {event_title} <-> {original_name}")
                        break
                    elif not event_date_str:  # Si on n'arrive pas à extraire la date de l'événement
                        # On fait confiance au nom seulement
                        matched_events.append(event)
                        found_match = True
                        self.logger.debug(f"Correspondance par nom: {event_title} <-> {original_name}")
                        break
            
            if not found_match:
                orphan_birthday_events.append(event)
                self.logger.debug(f"Événement d'anniversaire orphelin: {event_title}")
        
        # Trouver les anniversaires manquants
        matched_contact_names = set()
        for event in matched_events:
            event_title = event.get('title', '').lower()
            contact_name_from_event = self._extract_contact_name_from_birthday_event(event_title)
            
            # Trouver le contact correspondant
            for contact_name_lower, (original_name, _) in contacts_dict.items():
                if (contact_name_from_event.lower() in contact_name_lower or 
                    contact_name_lower in contact_name_from_event.lower() or
                    self._names_are_similar(contact_name_from_event, contact_name_lower)):
                    matched_contact_names.add(original_name)
                    break
        
        # Contacts sans événement d'anniversaire
        missing_birthdays = []
        for contact_name, birthday_date in contacts_with_birthdays:
            if contact_name not in matched_contact_names:
                missing_birthdays.append((contact_name, birthday_date))
        
        return matched_events, orphan_birthday_events, non_birthday_events, missing_birthdays
    
    def _is_birthday_event(self, event_title: str) -> bool:
        """Déterminer si un événement est probablement un anniversaire"""
        title_lower = event_title.lower().strip()
        
        # Mots-clés qui indiquent un anniversaire
        birthday_keywords = [
            'anniversaire', 'birthday', 'naissance', 'date de naissance',
            'bday', 'né le', 'née le', 'born on', 'anniversary'
        ]
        
        # Mots-clés qui indiquent que ce N'EST PAS un anniversaire
        non_birthday_keywords = [
            'réunion', 'meeting', 'rendez-vous', 'rdv', 'déjeuner', 'dîner',
            'restaurant', 'coupole', 'déménagement', 'visite', 'leçon',
            'championnat', 'résilier', 'ramener', 'manette', 'cheveux',
            'barbe', 'circulation', 'datascientest', 'surprise', 'fête'
        ]
        
        # Si l'événement contient des mots-clés non-anniversaire, ce n'est pas un anniversaire
        if any(keyword in title_lower for keyword in non_birthday_keywords):
            return False
        
        # Vérifier si l'événement contient des mots-clés d'anniversaire
        return any(keyword in title_lower for keyword in birthday_keywords)
    
    def _extract_contact_name_from_birthday_event(self, event_title: str) -> str:
        """Extraire le nom du contact d'un titre d'événement d'anniversaire"""
        # Supprimer les préfixes courants
        prefixes_to_remove = [
            'anniversaire de ', 'anniversary of ', 'birthday of ',
            'anniversaire ', 'birthday ', 'anniversary ', 'date de naissance : '
        ]
        
        name = event_title.lower().strip()
        for prefix in prefixes_to_remove:
            if name.startswith(prefix):
                name = name[len(prefix):].strip()
                break
        
        return name
    
    def _names_are_similar(self, name1: str, name2: str) -> bool:
        """Vérifier si deux noms sont similaires"""
        if not FUZZYWUZZY_AVAILABLE:
            return False
        
        # Nettoyer les noms
        name1_clean = ''.join(c.lower() for c in name1 if c.isalnum() or c.isspace()).strip()
        name2_clean = ''.join(c.lower() for c in name2 if c.isalnum() or c.isspace()).strip()
        
        similarity = fuzz.ratio(name1_clean, name2_clean)
        return similarity >= 80  # Seuil de similarité pour les noms
    
    def _format_date_for_comparison(self, date_obj) -> str:
        """Formater une date pour la comparaison (MM-DD)"""
        if not date_obj:
            return ""
        
        try:
            if hasattr(date_obj, 'month') and hasattr(date_obj, 'day'):
                return f"{date_obj.month:02d}-{date_obj.day:02d}"
            elif hasattr(date_obj, 'strftime'):
                return date_obj.strftime('%m-%d')
            else:
                date_str = str(date_obj)
                if len(date_str) >= 10:  # Format YYYY-MM-DD
                    return date_str[5:10]  # Extraire MM-DD
        except:
            pass
        
        return ""
    
    def _format_date_for_display(self, date_obj) -> str:
        """Formater une date pour l'affichage"""
        if not date_obj:
            return 'Sans date'
        
        try:
            if hasattr(date_obj, 'strftime'):
                return date_obj.strftime('%d/%m/%Y')
            else:
                return str(date_obj)[:10]
        except:
            return 'Date invalide'
    
    def _create_birthday_event(self, calendar, contact_name: str, birthday_date: str) -> bool:
        """Créer un événement d'anniversaire pour un contact"""
        try:
            # Créer l'événement iCal
            from datetime import datetime
            import uuid
            
            # Parser la date MM-DD
            month, day = birthday_date.split('-')
            current_year = datetime.now().year
            
            # Créer l'événement pour cette année
            event_date = datetime(current_year, int(month), int(day))
            
            # Générer un UID unique
            event_uid = str(uuid.uuid4())
            
            # Format iCal
            ical_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Nextcloud Duplicate Remover//FR
BEGIN:VEVENT
UID:{event_uid}
DTSTART;VALUE=DATE:{event_date.strftime('%Y%m%d')}
DTEND;VALUE=DATE:{event_date.strftime('%Y%m%d')}
SUMMARY:Anniversaire de {contact_name}
RRULE:FREQ=YEARLY
BEGIN:VALARM
ACTION:DISPLAY
DESCRIPTION:Anniversaire de {contact_name}
TRIGGER:-P1D
END:VALARM
END:VEVENT
END:VCALENDAR"""
            
            # Ajouter l'événement au calendrier
            calendar.add_event(ical_content)
            self.logger.debug(f"Événement créé: Anniversaire de {contact_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la création de l'événement pour {contact_name}: {e}")
            return False


def main():
    """Fonction principale"""
    
    parser = argparse.ArgumentParser(
        description="Supprimer les doublons dans Nextcloud (contacts et calendriers)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples d'utilisation:

1. Contacts - Mode API (recommandé):
   python nextcloud_duplicate_remover.py api https://mon-nextcloud.com mon_utilisateur --type contacts

2. Calendriers - Mode API (recommandé):
   python nextcloud_duplicate_remover.py api https://mon-nextcloud.com mon_utilisateur --type calendars

3. Calendrier spécifique:
   python nextcloud_duplicate_remover.py api https://mon-nextcloud.com mon_utilisateur --type calendars --calendar "Anniversaire"

4. Synchronisation anniversaires (recommandé pour Android):
   python nextcloud_duplicate_remover.py api https://mon-nextcloud.com mon_utilisateur --type calendars --sync-birthdays

5. Synchronisation anniversaires avec suppression réelle:
   python nextcloud_duplicate_remover.py api https://mon-nextcloud.com mon_utilisateur --type calendars --sync-birthdays --delete

6. Avec suppression réelle:
   python nextcloud_duplicate_remover.py api https://mon-nextcloud.com mon_utilisateur --type calendars --delete

7. Mode fichier vCard (contacts seulement):
   python nextcloud_duplicate_remover.py file contacts.vcf contacts_clean.vcf

Note: Le mode API nécessite les bibliothèques caldav et vobject.
Pour les installer: pip install -r requirements.txt
        """
    )
    
    subparsers = parser.add_subparsers(dest='mode', help='Mode d\'utilisation')
    
    # Mode API
    api_parser = subparsers.add_parser('api', help='Mode API CardDAV/CalDAV')
    api_parser.add_argument('server_url', help='URL du serveur Nextcloud (ex: https://mon-nextcloud.com)')
    api_parser.add_argument('username', help='Nom d\'utilisateur Nextcloud')
    api_parser.add_argument('--type', choices=['contacts', 'calendars'], default='contacts',
                           help='Type d\'éléments à traiter (défaut: contacts)')
    api_parser.add_argument('--calendar', help='Nom du calendrier spécifique (seulement avec --type calendars)')
    api_parser.add_argument('--sync-birthdays', action='store_true', 
                           help='Synchroniser le calendrier d\'anniversaires avec les dates de naissance des contacts (seulement avec --type calendars)')
    api_parser.add_argument('--delete', action='store_true', help='Effectuer les suppressions (par défaut: dry-run)')
    api_parser.add_argument('--threshold', type=int, default=85, 
                           help='Seuil de similarité pour les doublons (0-100, défaut: 85)')
    
    # Mode fichier
    file_parser = subparsers.add_parser('file', help='Mode fichier vCard')
    file_parser.add_argument('input_file', help='Fichier vCard d\'entrée')
    file_parser.add_argument('output_file', help='Fichier vCard de sortie')
    
    args = parser.parse_args()
    
    if not args.mode:
        parser.print_help()
        return 1
    
    try:
        if args.mode == 'api':
            if not CALDAV_AVAILABLE:
                print("ERREUR: La bibliothèque caldav n'est pas installée.")
                print("Installez-la avec: pip install caldav")
                return 1
            
            if not VOBJECT_AVAILABLE:
                print("ERREUR: La bibliothèque vobject n'est pas installée.")
                print("Installez-la avec: pip install vobject")
                return 1
            
            # Validation des arguments
            if args.calendar and args.type != 'calendars':
                print("ERREUR: --calendar ne peut être utilisé qu'avec --type calendars")
                return 1
            
            if hasattr(args, 'sync_birthdays') and args.sync_birthdays and args.type != 'calendars':
                print("ERREUR: --sync-birthdays ne peut être utilisé qu'avec --type calendars")
                return 1
            
            # Demander le mot de passe de manière sécurisée
            password = getpass.getpass(f"Mot de passe pour {args.username}: ")
            
            if args.type == 'contacts':
                # Gestion des contacts (code existant)
                manager = NextcloudContactManager(args.server_url, args.username, password)
                
                if not manager.connect():
                    print("ERREUR: Impossible de se connecter à Nextcloud pour les contacts")
                    return 1
                
                duplicates_found, deleted_count = manager.remove_duplicates(dry_run=not args.delete)
                
                if args.delete:
                    print(f"✅ Suppression de contacts terminée: {deleted_count} contacts supprimés sur {duplicates_found} doublons trouvés")
                else:
                    print(f"ℹ️  Mode dry-run (contacts): {duplicates_found} doublons trouvés (utilisez --delete pour les supprimer)")
            
            elif args.type == 'calendars':
                # Gestion des calendriers (nouveau code)
                calendar_manager = NextcloudCalendarManager(args.server_url, args.username, password)
                
                if not calendar_manager.connect():
                    print("ERREUR: Impossible de se connecter à Nextcloud pour les calendriers")
                    return 1
                
                # Vérifier si on doit faire la synchronisation des anniversaires
                if hasattr(args, 'sync_birthdays') and args.sync_birthdays:
                    # Mode synchronisation anniversaires
                    print("🎂 Mode synchronisation des anniversaires activé")
                    
                    # Il faut aussi connecter aux contacts pour récupérer les dates de naissance
                    contact_manager = NextcloudContactManager(args.server_url, args.username, password)
                    if not contact_manager.connect():
                        print("ERREUR: Impossible de se connecter aux contacts pour la synchronisation")
                        return 1
                    
                    # Utiliser le calendrier spécifié ou "Anniversaire" par défaut
                    calendar_name = args.calendar if args.calendar else "Anniversaire"
                    
                    orphans_found, deleted_count, created_count = calendar_manager.sync_birthday_calendar(
                        contact_manager, 
                        calendar_name=calendar_name,
                        dry_run=not args.delete
                    )
                    
                    if args.delete:
                        print(f"✅ Synchronisation terminée dans '{calendar_name}': {deleted_count} événements supprimés, {created_count} créés")
                    else:
                        print(f"ℹ️  Mode dry-run (synchronisation): {orphans_found} orphelins trouvés dans '{calendar_name}' (utilisez --delete pour synchroniser)")
                
                else:
                    # Mode suppression de doublons classique
                    # Afficher les calendriers disponibles si aucun spécifique n'est demandé
                    if not args.calendar:
                        available_calendars = [getattr(cal, 'name', 'Inconnu') for cal in calendar_manager.calendars]
                        print(f"📅 Calendriers disponibles: {', '.join(available_calendars)}")
                        if len(available_calendars) > 1:
                            print("💡 Utilisez --calendar \"Nom du calendrier\" pour traiter un calendrier spécifique")
                    
                    duplicates_found, deleted_count = calendar_manager.remove_event_duplicates(
                        calendar_name=args.calendar,
                        dry_run=not args.delete
                    )
                    
                    if args.delete:
                        calendar_info = f" dans le calendrier '{args.calendar}'" if args.calendar else ""
                        print(f"✅ Suppression d'événements terminée: {deleted_count} événements supprimés sur {duplicates_found} doublons trouvés{calendar_info}")
                    else:
                        calendar_info = f" dans le calendrier '{args.calendar}'" if args.calendar else ""
                        print(f"ℹ️  Mode dry-run (calendriers): {duplicates_found} doublons trouvés{calendar_info} (utilisez --delete pour les supprimer)")
        
        elif args.mode == 'file':
            processor = VCardFileProcessor()
            removed = processor.process_vcf_file(args.input_file, args.output_file)
            print(f"✅ Fichier traité: {removed} doublons supprimés")
            print(f"📁 Fichier de sortie: {args.output_file}")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n❌ Opération annulée par l'utilisateur")
        return 1
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
