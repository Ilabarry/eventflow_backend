"""
Nettoyage du HTML fourni par les utilisateurs.

Les descriptions d'événements sont du rich text produit par l'éditeur du
frontend. Elles sont ensuite rendues dans une page publique : sans liste
blanche stricte, un organisateur pourrait injecter du JavaScript (XSS
stockée) et cibler tous les visiteurs, y compris les administrateurs.

On applique donc une double défense :
    - backend : ce module nettoie le HTML à l'écriture ;
    - frontend : Angular sanitise de nouveau avant [innerHTML].
"""

import bleach

# Balises autorisées dans une description d'événement.
ALLOWED_TAGS = {
    "p", "br", "hr",
    "strong", "b", "em", "i", "u", "s", "del",
    "ul", "ol", "li",
    "h2", "h3", "h4",
    "blockquote", "code", "pre",
    "a", "span", "div",
}

# Attributs autorisés, par balise. Pas de `style`, pas de `class`, pas
# d'attribut événementiel (`onclick`, ...), pas de `target` (tabnabbing).
ALLOWED_ATTRIBUTES = {
    "a": ["href", "title"],
}

ALLOWED_PROTOCOLS = {"http", "https", "mailto"}


def sanitize_rich_text(value: str | None) -> str | None:
    """Retourne le HTML nettoyé, ou la valeur telle quelle si elle est vide."""
    if not value:
        return value

    return bleach.clean(
        value,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
        strip_comments=True,
    )
