# Mes logements à Marseille

Application de suivi de recherche de logement à Marseille : annonces SeLoger / agences, caractéristiques (T1/T2, parking, balcon/terrasse), état des démarches, commentaires, tableau de bord et carte des arrondissements.

- Site : https://louiscaro13.github.io/mes-logements-marseille/
- Données partagées dans Supabase (connexion par e-mail + mot de passe ; les comptes sont créés dans le tableau de bord Supabase).
- La clé Supabase présente dans `index.html` est la clé publique (« publishable ») : l'accès aux données est protégé par la connexion (Row Level Security).
- Carte : contours des communes d'après france-geojson (gregoiredavid), arrondissements et lieux approximatifs.
