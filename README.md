# 2FEXC

2FEXC est une application Streamlit de type terminal financier avec accès protégé.

## Fonctionnalités
- Interface sombre inspirée d'un terminal de marché
- Connexion utilisateur
- Inscription avec code d'invitation
- Stockage local des utilisateurs dans SQLite
- Mot de passe hashé
- Session utilisateur et logout
- Watchlist, graphiques Plotly, news simulées

## Structure
- `app.py` : application principale
- `data/users.db` : base SQLite créée automatiquement au premier lancement
- `.streamlit/config.toml` : thème sombre

## Lancement local
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Déploiement Streamlit Community Cloud
1. Pousse le repo sur GitHub.
2. Déploie le repo sur Streamlit Community Cloud.
3. Choisis `app.py` comme fichier principal.

## Identifiants et sécurité
- Les comptes sont créés via le formulaire d'inscription.
- Le code d'invitation par défaut est `2FEXC2026`.
- Les mots de passe sont hashés avant stockage.
- Pour une vraie production multi-utilisateur, prévois PostgreSQL ou Supabase.

## Limites
- SQLite convient pour une V1 ou un petit volume.
- Les données marché affichées sont simulées.
- Cette base n'est pas un service d'authentification enterprise.
