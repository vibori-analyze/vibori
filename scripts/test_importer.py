"""Regression checks for canonical protocol conversion without network access."""

import unittest

from import_izbirkom_api import (
    PARTY_LOGOS,
    candidate_record,
    party_id,
    report_to_record,
    vote_count,
)


class ProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        PARTY_LOGOS[:] = [
            {"id": "party-example", "patterns": ["EXAMPLE PARTY"]},
        ]

    def tearDown(self) -> None:
        PARTY_LOGOS.clear()

    def test_party_identifiers_deduplicate_regional_names(self) -> None:
        self.assertEqual(party_id("Example Party"), "party-example")
        self.assertEqual(party_id("Regional branch of Example Party"), "party-example")

    def test_invalid_counts_are_not_official_zeroes(self) -> None:
        for value in (None, "", -1, "1.5", True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                vote_count(value)
        self.assertEqual(vote_count("0"), 0)

    def test_missing_turnout_rejects_protocol(self) -> None:
        with self.assertRaises(ValueError):
            report_to_record(
                "https://example.org",
                {},
                {},
                [],
                1,
                {"body": {"records": [{"infoText": "Candidate", "value": "10"}]}},
            )

    def test_complete_protocol_retains_provenance(self) -> None:
        record = report_to_record(
            "https://example.org",
            {"id": 1, "name": "Election", "votingDate": "2026-01-01"},
            {"externalId": "precinct", "name": "Precinct", "type": 5},
            [],
            1,
            {
                "body": {
                    "records": [
                        {"category": "records", "infoPrintNum": key, "value": "0"}
                        for key in ("1", "3", "4", "5", "9", "10")
                    ]
                    + [{"infoText": "Candidate", "value": "0"}]
                }
            },
        )
        assert record is not None
        self.assertIn("retrieved_at", record["source"])
        self.assertIn("commissionClassifierId=precinct", record["source"]["url"])
        self.assertEqual(record["results"][0]["votes"], 0)

    def test_candidate_profile_retains_party_and_provenance(self) -> None:
        record = candidate_record(
            "https://example.org",
            {"id": 42},
            {
                "id": "candidate-id",
                "fullName": "Candidate Name",
                "electionAssociation": "Example Party",
                "districtNum": 7,
            },
            {"body": {"birthDate": "2000-01-02", "education": "University"}},
            1,
        )
        self.assertEqual(record["standard"], "vibori-candidate/v1")
        self.assertEqual(record["election_id"], "izbirkom-42-p1")
        self.assertEqual(record["party"]["name"], "Example Party")
        self.assertIn("candidateId=candidate-id", record["source"]["url"])

    def test_self_nomination_is_not_a_party(self) -> None:
        record = candidate_record(
            "https://example.org",
            {"id": 42},
            {
                "id": "candidate-id",
                "fullName": "Candidate Name",
                "electionAssociation": " самовыдвижение ",
            },
            {"body": {}},
            1,
        )
        self.assertIsNone(record["party"])

    def test_protocol_uses_official_candidate_id_and_party(self) -> None:
        candidate = {
            "id": "official-id",
            "name": "Candidate",
            "district_number": 3,
            "party": {"id": "party-id", "name": "Party"},
        }
        record = report_to_record(
            "https://example.org",
            {"id": 1, "name": "Election", "votingDate": "2026-01-01"},
            {"externalId": "precinct", "name": "Precinct", "type": 5},
            [
                {
                    "externalId": "district",
                    "name": "District",
                    "type": 3,
                    "number": "3",
                },
                {"externalId": "precinct", "name": "Precinct", "type": 5},
            ],
            1,
            {
                "body": {
                    "records": [
                        *[
                            {"category": "records", "infoPrintNum": key, "value": "0"}
                            for key in ("1", "3", "4", "5", "9", "10")
                        ],
                        {"infoText": "Candidate", "value": "1"},
                    ]
                }
            },
            {"Candidate": [candidate]},
        )
        assert record is not None
        self.assertEqual(record["results"][0]["entity"]["id"], "official-id")
        self.assertEqual(record["results"][0]["entity"]["party_id"], "party-id")
