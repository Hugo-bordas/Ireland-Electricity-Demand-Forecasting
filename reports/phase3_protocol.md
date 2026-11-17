# Protocole fixé avant l'entraînement

## Prévision directe

Une origine T correspond à une mesure y(T) déjà disponible. On prédit les
24 demandes y(T+1), ..., y(T+24). Chaque famille comprend 24 modèles indépendants.
Aucune prédiction n'est réinjectée comme observation pour produire l'horizon suivant.
Une nouvelle prévision est simulée chaque heure, en recevant les mesures réelles
devenues disponibles à cette nouvelle origine. Le délai de publication n'est pas
modélisé : l'usage de y(T) suppose qu'elle a déjà été reçue.

La construction repart de la série horaire brute, sans retirer de lignes avant
les décalages. Les variables de phase 2 ne sont pas reprises telles quelles.
À l'origine T, pour l'horizon h :

| Variable | Date ou intervalle utilisé |
| --- | --- |
| Heure, jour de semaine, mois, weekend cibles | Calendrier UTC de T+h, connu à l'avance |
| Demande à l'origine | T |
| Demandes retardées depuis l'origine | T-24 et T-168 |
| Moyenne des 24 dernières heures | T-23 à T, 24 valeurs obligatoires |
| Moyenne des 168 dernières heures | T-167 à T, 168 valeurs obligatoires |
| Référence du jour précédent | T+h-24, donc au plus T |
| Référence de la semaine précédente | T+h-168, donc au plus T-144 |

Il y a 11 colonnes avant encodage. Pour h=24, la référence journalière est y(T).
La cible d'entraînement est y(T+h), obtenue par décalage négatif dans une table
distincte qui n'entre jamais dans les variables explicatives.

## Périodes et exclusions

Les bornes sont en UTC et les fins sont exclusives :

| Ensemble | Origines candidates | Dernière origine permise après purge |
| --- | --- | --- |
| Entraînement | 2015-01-01 à 2019-01-01 exclu | 2018-12-30 23 h |
| Validation | 2019-01-01 à 2020-01-01 exclu | 2019-12-30 23 h |
| Test final | 2020-01-01 à 2020-07-01 exclu | 2020-06-29 23 h |

On exige T+24 strictement avant la fin de chaque période. Les 24 dernières
origines sont donc exclues pour garder toutes leurs cibles dans la même période.
Les historiques de validation et de test peuvent utiliser les périodes antérieures.
Il n'y a ni mélange aléatoire des périodes, ni normalisation sur les données futures.

Un exemple est conservé seulement si les 24 cibles, toutes les variables des
24 horizons et les deux baselines sont disponibles. Toutes les méthodes sont
évaluées sur les mêmes origines. L'exclusion complète d'une origine est une règle
conservatrice qui simplifie la comparaison ; aucune imputation n'est appliquée.

Le journal par origine garde les drapeaux détaillés et une raison exclusive, dans
l'ordre : frontière, historique trop court, variable indisponible, cible indisponible.
Les drapeaux peuvent se recouper ; les totaux des raisons exclusives sont additifs.
Les premières origines demandent au moins 168 heures d'historique, car y(T-168)
est requise.

## Modèles et sélection

- Ridge : alpha=10, calendrier encodé en indicatrices, variables numériques
  standardisées dans une pipeline ajustée sur l'entraînement seulement.
- RandomForestRegressor : 80 arbres, profondeur maximale 14, au moins 5 exemples
  par feuille, graine 42, deux tâches parallèles.
- HistGradientBoostingRegressor : 150 itérations, 15 feuilles au maximum,
  learning_rate=0,1, régularisation L2=1, graine 42. L'arrêt anticipé est désactivé
  pour éviter le sous-échantillon aléatoire de validation interne par défaut.

Les baselines prédisent respectivement y(T+h-24) et y(T+h-168).
Une seule configuration par famille est essayée. Le meilleur modèle ML est celui
qui minimise la MAE globale en validation 2019, avec RMSE puis nom comme critères
de départage. Le classement des baselines est présenté séparément ; une baseline
plus performante devra être signalée. Aucun réentraînement sur 2019 n'est effectué
dans cette version : on conserve exactement les modèles sélectionnés et déjà évalués.

La MAE est la moyenne des erreurs absolues sur toutes les paires (T,h). Le RMSE
est la racine de la moyenne des erreurs au carré sur ces mêmes paires, et non la
moyenne des RMSE par horizon. Les MAE par horizon sont également enregistrées.
Les origines horaires se chevauchent : plusieurs prévisions peuvent concerner
la même heure cible avec des horizons différents. Ces erreurs sont corrélées.

## Test final et sauvegarde

L'entraînement et la sélection ne construisent leurs cibles qu'avant 2020.
Le fichier de sélection et les modèles sont sauvegardés avant le test. Une
commande distincte charge le modèle choisi et évalue une seule fois janvier-juin
2020, avec les deux baselines sur les mêmes exemples. Les modèles non sélectionnés
ne sont pas évalués sur ce test. Un marqueur empêche de relancer involontairement
le test ou l'entraînement après son ouverture.

La période illustrée sur le test est fixée avant son ouverture : les sept premières
origines complètes de janvier à 23 h UTC, avec leurs 24 prévisions assemblées.
La sélection dépend du calendrier et de la disponibilité, jamais de la qualité
des prédictions. Les graphiques et métriques proviennent des prévisions enregistrées.

Les modèles restent locaux, avec versions des dépendances, schéma des variables,
paramètres, bornes temporelles et empreinte du CSV. Ni API, ni dashboard, ni publication
ne sont réalisés à cette phase.
