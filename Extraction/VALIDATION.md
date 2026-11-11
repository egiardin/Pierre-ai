# État de vérification de la livraison

- 8 tests unitaires hors navigateur : réussis.
- Syntaxe Python : vérifiée par compileall.
- Syntaxe JavaScript : vérifiée avec node --check.
- Test d'intégration Chromium fourni : non validé. Le lancement initial a échoué
  faute de navigateur, et le téléchargement Chromium a échoué dans l'environnement
  de développement (archive reçue tronquée/invalide).
- Aucun résultat réel sur 5terres-hotel.fr n'est revendiqué pour cette version.
- Aucun email, upload R2 ou changement Sacha effectué.

Après installation sur Mac, lancer :

```bash
python -m unittest discover -s tests -v
```

Puis l'extraction de l'hôtel. Comparer la galerie et le rapport au site.
Le critère de validation est la récupération de photos auparavant absentes,
avec leurs sources et au maximum 99 fichiers, sans promesse d'exhaustivité.
