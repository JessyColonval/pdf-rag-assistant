import pytest
 
from src.describe import parse_type
 
 
@pytest.mark.parametrize(
    "reply, expected",
    [
        pytest.param("TYPE: schema\nRESUME: un schéma", "schema", id="cas_nominal"),
        pytest.param("TYPE: capture_ecran", "capture_ecran", id="type_avec_underscore"),
        pytest.param("TYPE: decoratif", "decoratif", id="decoratif_seul"),
        pytest.param("  \nTYPE: graphique", "graphique", id="espaces_avant_TYPE"),
        pytest.param("type: Tableau", "tableau", id="casse_ignoree_et_mise_en_minuscules"),
        pytest.param("TYPE:autre", "autre", id="sans_espace_apres_les_deux_points"),
        pytest.param("TYPE: schema | graphique", "schema", id="s_arrete_au_premier_mot"),
        pytest.param("RESUME: x\nTYPE: schema", "inconnu", id="TYPE_pas_en_premiere_ligne"),
        pytest.param("Voici la description de la figure.", "inconnu", id="pas_de_ligne_TYPE"),
        pytest.param("", "inconnu", id="reponse_vide"),
    ],
)
def test_parse_type(reply, expected):
    assert parse_type(reply) == expected
