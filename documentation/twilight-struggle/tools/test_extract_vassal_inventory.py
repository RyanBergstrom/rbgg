from __future__ import annotations

import unittest
import json

from country_reference import REFERENCE_PATH, load_country_reference
from extract_vassal_inventory import ROOT, extract


class VassalInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inventory = extract()

    def test_extracts_country_layout_positions_without_claiming_rules(self) -> None:
        countries = self.inventory["countries"]
        self.assertEqual(len(countries), 85)
        canada = next(country for country in countries if country["name"] == "Canada")
        self.assertEqual((canada["map_x"], canada["map_y"]), (937, 794))
        self.assertEqual(canada["adjacency_status"], "not_encoded_in_xml")
        self.assertEqual(canada["stability"], 4)
        self.assertEqual(canada["trait_region"], "Europe")
        self.assertNotIn("scoring_regions", canada)
        self.assertFalse(canada["battleground"])
        self.assertEqual(
            canada["attributes_source"],
            "VASSAL influence trait; verify against board/rulebook",
        )
        france = next(country for country in countries if country["name"] == "France")
        self.assertEqual(france["stability"], 3)
        self.assertTrue(france["battleground"])
        mapped = [country for country in countries if "battleground" in country]
        self.assertGreaterEqual(len(mapped), 80)
        self.assertGreater(sum(country["battleground"] for country in mapped), 0)

    def test_extracts_card_metadata_and_preserves_unimplemented_effect_status(self) -> None:
        cards = self.inventory["cards"]
        self.assertEqual(len(cards), 110)
        self.assertEqual(len({card["card_id"] for card in cards}), 110)
        self.assertEqual({card["card_id"] for card in cards}, set(range(1, 111)))
        self.assertTrue(
            all((ROOT / card["card_face_asset"]).is_file() for card in cards)
        )
        self.assertTrue(all(card["card_face_text_node_count"] > 0 for card in cards))
        asia = next(card for card in cards if card["name"] == "Asia Scoring")
        self.assertEqual(asia["operations"], 0)
        self.assertTrue(asia["scoring_flag"])
        self.assertTrue(asia["card_face_asset"].endswith("TNRnTS-01.svg"))
        self.assertGreater(asia["card_face_text_node_count"], 0)
        self.assertEqual(asia["rules_effect_status"], "not_encoded_in_extracted_fields")
        china = next(card for card in cards if card["name"] == "The China Card")
        self.assertEqual(china["operations"], 4)

    def test_country_review_draft_covers_all_map_spaces_and_keeps_graph_open(self) -> None:
        draft_path = ROOT / "country-map-draft.json"
        draft = json.loads(draft_path.read_text(encoding="utf-8"))
        country_names = {country["name"] for country in self.inventory["countries"]}
        draft_names = {record[0] for record in draft["countries"]}
        self.assertEqual(draft["status"], "provisional_review_draft")
        self.assertEqual(len(draft["countries"]), 85)
        self.assertEqual(draft_names, country_names)
        extracted_by_name = {
            country["name"]: country for country in self.inventory["countries"]
        }
        self.assertEqual(draft["scoring_region_memberships"], "same_as_trait_region")
        self.assertEqual(
            draft["scoring_region_status"], "user_confirmed_vassal_region_values"
        )
        for name, map_x, map_y, stability, trait_region, battleground in draft["countries"]:
            extracted = extracted_by_name[name]
            self.assertEqual((map_x, map_y), (extracted["map_x"], extracted["map_y"]))
            self.assertEqual(stability, extracted.get("stability"))
            self.assertEqual(trait_region, extracted.get("trait_region"))
            self.assertEqual(battleground, extracted.get("battleground"))
        self.assertEqual(set(draft["adjacency"]), country_names)
        self.assertTrue(all(not neighbors for neighbors in draft["adjacency"].values()))
        self.assertEqual(len(draft["country_fields"]), 6)

    def test_larger_map_adjacency_candidates_are_valid_separate_graph(self) -> None:
        draft = json.loads((ROOT / "country-map-draft.json").read_text(encoding="utf-8"))
        candidates = json.loads(
            (ROOT / "country-adjacency-candidates.json").read_text(encoding="utf-8")
        )
        country_names = {record[0] for record in draft["countries"]}
        edges = candidates["country_edges"]
        edge_keys = [frozenset((edge[0], edge[1])) for edge in edges]
        self.assertTrue(edges)
        self.assertEqual(len(edge_keys), len(set(edge_keys)))
        for a, b, confidence in edges:
            self.assertIn(a, country_names)
            self.assertIn(b, country_names)
            self.assertNotEqual(a, b)
            self.assertIn(confidence, {"high", "medium"})
        self.assertTrue(all(not neighbors for neighbors in draft["adjacency"].values()))
        self.assertIn("reference-only", candidates["purpose"].casefold())

    def test_user_country_reference_loads_as_symmetric_editable_config(self) -> None:
        config = load_country_reference()
        countries = config["countries"]
        adjacency = config["adjacency"]
        self.assertEqual(REFERENCE_PATH.name, "countryreference.md")
        self.assertEqual(len(countries), 87)
        self.assertEqual(countries["Canada"]["region"], "Europe")
        self.assertEqual(countries["Canada"]["stability"], 4)
        self.assertEqual(countries["China"]["stability"], None)
        self.assertIn("Dominican Rep", countries)
        self.assertNotIn("Dominican Republic", countries)
        self.assertTrue(
            any("United States" in edge for edge in config["superpower_adjacency"])
        )
        for country, neighbors in adjacency.items():
            for neighbor in neighbors:
                self.assertIn(country, adjacency[neighbor])
        self.assertIn("asymmetric_source_entries", config)


if __name__ == "__main__":
    unittest.main()
