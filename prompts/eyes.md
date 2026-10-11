Tu analyses une figure extraite de la documentation d'une application. Il peut s'agir d'une capture d'écran de l'application, d'un schéma (architecture, flux), d'un graphique, d'un tableau sous forme d'image, ou d'une image décorative.

Contexte (texte qui précède la figure dans le document) :
{context}

Légende :
{caption}

Réponds en français, exactement dans le format suivant :

TYPE: <capture_ecran | schema | graphique | tableau | decoratif | autre>

TEXTE_VISIBLE: <texte lisible présent dans l'image, recopié aussi fidèlement que possible et séparé par " | " : titres, menus, boutons, champs, noms des blocs, étiquettes des flèches, axes, légendes, valeurs et unités>

STRUCTURE: <description structurée selon le type :

* capture_ecran : principaux éléments visibles et leurs relations spatiales ou fonctionnelles ; préciser les éléments entourés, surlignés ou fléchés, sinon "aucun"
* schema : relations entre les éléments, une par ligne, sous la forme "A -> B (étiquette)" uniquement si le lien est visuellement identifiable
* graphique : type de graphique, grandeurs représentées sur les axes, unités et tendances directement observables
* tableau : organisation générale, en-têtes et relations importantes entre les lignes et les colonnes
* autre : description de la structure visible
* si aucune structure pertinente n'est identifiable : "aucune">

RESUME: <1 à 2 phrases décrivant le sujet de la figure, son objectif apparent et, pour une capture d'écran, l'action illustrée si elle est identifiable>

MOTS_CLES: <termes et expressions utiles pour retrouver cette figure à partir d'une question utilisateur : fonctionnalités, actions, noms de menus, concepts techniques et synonymes pertinents. Utiliser uniquement des termes justifiés par l'image ou son contexte. Séparer par " | ">

INCERTITUDES: <éléments illisibles, ambigus ou relations impossibles à déterminer ; écrire "aucune" si rien de notable>

Règles :

* Ne recopie dans TEXTE_VISIBLE que le texte réellement présent et lisible dans l'image. N'y ajoute pas de texte provenant du contexte ou de la légende.
* Le contexte et la légende peuvent aider à comprendre la figure, mais ne prouvent pas ce qui est visuellement représenté.
* N'invente aucun libellé, aucune valeur chiffrée, aucun lien, aucune étape de procédure ni aucun comportement de l'application.
* Si une information attendue est illisible, indique "illisible" uniquement lorsque cela est pertinent.
* Distingue les observations visuelles des interprétations. Si une interprétation reste incertaine, signale-le dans INCERTITUDES.
* Ne déduis pas qu'une action fonctionne simplement parce qu'un bouton correspondant est visible.
* Ne suppose pas que la figure décrit la version actuelle de l'application ni que la procédure illustrée est correcte.
* Évite les répétitions entre les champs. Privilégie les informations spécifiques et utiles pour la recherche documentaire.
* Si la figure est purement décorative (logo, bandeau, icône sans information fonctionnelle), réponds uniquement : TYPE: decoratif

Retourne uniquement le résultat dans le format demandé, sans introduction ni commentaire.
