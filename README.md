# Mes logements à Marseille

Application de suivi de recherche de logement à Marseille : annonces SeLoger / agences, caractéristiques (T1/T2, parking, balcon/terrasse), état des démarches, commentaires, tableau de bord et carte des arrondissements.

- Site : https://louiscaro13.github.io/mes-logements-marseille/
- Données partagées dans Supabase (connexion par e-mail + mot de passe ; les comptes sont créés dans le tableau de bord Supabase).
- La clé Supabase présente dans `index.html` est la clé publique (« publishable ») : l'accès aux données est protégé par la connexion (Row Level Security).
- Carte : contours des communes d'après france-geojson (gregoiredavid), arrondissements et lieux approximatifs.

## Recherche quotidienne (tools/scan.py)

Chaque jour à 17 h, une tâche planifiée lit les annonces Bien'ici et Le Figaro Immobilier,
applique les critères (T2/T3, 900 € CC max, balcon/terrasse, parking/box, arrondissements
préférés 6e, 5e, 10e, 4e, 9e, 3e, 2e, 8e) et produit un top 10, sans les annonces déjà
présentes sur le site. `data/propositions.json` garde la date de première proposition.
SeLoger, Leboncoin, PAP et Logic-Immo bloquent la lecture automatique : ils ne sont pas lus.
