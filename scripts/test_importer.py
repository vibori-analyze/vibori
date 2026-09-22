"""Regression checks for canonical protocol conversion without network access."""

import unittest

from import_izbirkom_api import report_to_record, vote_count


class ProtocolTests(unittest.TestCase):
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
