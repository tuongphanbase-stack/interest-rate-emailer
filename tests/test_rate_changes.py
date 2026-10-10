"""Run: python -m unittest discover tests

Change badges and email size, checked against a trimmed copy of the real
interest-rate-state last_rates.json from 2026-10-10 (MB Bank cut to its
first 200 rows): BIDV and MB Bank had every table on their pages merged
into one list (BIDV's "3 Tháng" 3 times, MB Bank's "01 tháng" 8 times), and
the email showed ~276 "was X%" badges and was ~356 KiB with nothing changed.
"""
import copy
import json
import os
import re
import sys
import unicodedata
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "last_rates_2026-10-10.json")
sys.path.insert(0, ROOT)

import interest_rate_emailer as emailer  # noqa: E402

# Gmail clips an email whose HTML passes ~102 KB; stay well under it.
MAX_HTML_BYTES = 85_000


def load_state():
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


def results_from_state(state):
    """The results structure collect_rates() would return for the rates in
    a saved state file (the inverse of save_rates).
    """
    def ok(rate):
        return {"ok": True, "rate": rate, "as_of": "2026-10-10"}

    missing = {"ok": False, "error": "not in state"}
    results = {"central_banks": {}, "commercial_banks": {}, "special_products": {}}
    for name, _url in emailer.SOURCES:
        entry = state["central_banks"].get(name, {})
        results["central_banks"][name] = {
            "policy": ok(entry["policy"]) if "policy" in entry else missing,
            "deposit": ok(entry["deposit"]) if "deposit" in entry else missing,
        }
    for name, _url in emailer.COMMERCIAL_BANK_SOURCES:
        terms = state["commercial_banks"].get(name)
        results["commercial_banks"][name] = (
            {"ok": True, "as_of": "2026-10-10", "terms": copy.deepcopy(terms)} if terms else missing
        )
    for name, _url in emailer.SPECIAL_PRODUCT_SOURCES:
        rate = state["special_products"].get(name)
        results["special_products"][name] = ok(rate) if rate else missing
    return results


def badge_counts(results, previous):
    html_body = emailer.format_email_html(results, previous)
    text_body = emailer.format_email_body(results, previous)
    return html_body.count("was "), text_body.count("[was ")


class UnchangedRealState(unittest.TestCase):
    def setUp(self):
        self.state = load_state()
        self.results = results_from_state(self.state)

    def test_no_change_badges(self):
        self.assertEqual(badge_counts(self.results, self.state), (0, 0))
        self.assertFalse(emailer.has_changed(self.results, self.state))

    def test_html_well_under_gmail_clip_limit(self):
        html_body = emailer.format_email_html(self.results, self.state)
        self.assertLess(len(html_body.encode("utf-8")), MAX_HTML_BYTES)

    def test_every_bank_still_shows_its_12_month_rate(self):
        text_body = emailer.format_email_body(self.results, self.state)
        for name, terms in self.state["commercial_banks"].items():
            block = text_body.split(f"\n{name} (as of", 1)[1].split("\n\n", 1)[0]
            labels = [line.split("|")[0].strip() for line in block.splitlines()[2:] if "|" in line]
            twelve = [t for t in terms if emailer.term_months(t["term"]) == 12][0]
            self.assertIn(emailer.term_key(twelve["term"]), [emailer.term_key(l) for l in labels], name)
            self.assertIn(twelve["counter"], block, name)

    def test_rates_rewritten_in_another_format_are_not_a_change(self):
        # "2,1%" (as BIDV's page writes it) vs "2.10%" (as it's saved now).
        for terms in self.results["commercial_banks"]["BIDV"]["terms"], self.results["commercial_banks"]["MB Bank"]["terms"]:
            for t in terms:
                t["counter"] = emailer.normalize_rate(t["counter"])
                t["online"] = emailer.normalize_rate(t["online"])
        self.assertEqual(badge_counts(self.results, self.state), (0, 0))
        self.assertFalse(emailer.has_changed(self.results, self.state))

    def test_first_run_with_first_table_only_against_old_merged_state(self):
        # What the fixed fetchers return (first table only, rates normalized),
        # compared with the merged lists saved by the old version.
        for name, first_table_rows in (("BIDV", 12), ("MB Bank", 22)):
            terms = self.state["commercial_banks"][name][:first_table_rows]
            self.results["commercial_banks"][name]["terms"] = [
                {"term": emailer.term_key(t["term"]), "counter": emailer.normalize_rate(t["counter"]),
                 "online": emailer.normalize_rate(t["online"])}
                for t in terms
            ]
        self.assertEqual(badge_counts(self.results, self.state), (0, 0))

    def test_one_real_change_gets_exactly_one_badge(self):
        mb_terms = self.results["commercial_banks"]["MB Bank"]["terms"]
        first_12m = next(t for t in mb_terms if unicodedata.normalize("NFC", t["term"]) == "12 tháng")
        self.assertEqual(first_12m["counter"], "6.20%")
        first_12m["counter"] = "6.40%"
        html_body = emailer.format_email_html(self.results, self.state)
        text_body = emailer.format_email_body(self.results, self.state)
        self.assertEqual(html_body.count("was "), 1)
        self.assertIn("was 6.20%", html_body)
        self.assertEqual(re.findall(r"\[was [^\]]*\]", text_body), ["[was 6.20%]"])
        self.assertTrue(emailer.has_changed(self.results, self.state))


class Helpers(unittest.TestCase):
    def test_normalize_rate(self):
        self.assertEqual(emailer.normalize_rate("2,1%"), "2.10%")
        self.assertEqual(emailer.normalize_rate("2.10%"), "2.10%")
        self.assertEqual(emailer.normalize_rate("6"), "6.00%")
        self.assertEqual(emailer.normalize_rate("4.725%"), "4.725%")
        self.assertEqual(emailer.normalize_rate("4,750%"), "4.75%")
        self.assertEqual(emailer.normalize_rate("0"), "0.00%")
        self.assertEqual(emailer.normalize_rate("10"), "10.00%")
        self.assertEqual(emailer.normalize_rate("-"), "-")
        self.assertIsNone(emailer.normalize_rate(None))

    def test_repeated_labels_pair_by_position(self):
        prev = [{"term": "3 Tháng", "counter": "2,4%", "online": "2,4%"},
                {"term": "3 Tháng", "counter": "4,75%", "online": "4,75%"}]
        cur = [{"term": "3 Tháng", "counter": "2.40%", "online": "2.40%"},
               {"term": "3 Tháng", "counter": "4.75%", "online": "4.75%"}]
        pairs = emailer.pair_with_previous(cur, prev)
        self.assertEqual([p for _, p in pairs], prev)
        self.assertFalse(any(emailer.term_row_changed(t, p) for t, p in pairs))


class FirstTableOnly(unittest.TestCase):
    PAGE = """
    <table>
      <tr><th>Kỳ hạn</th><th>Lãi suất</th></tr>
      <tr><td>01 tháng</td><td>3,70</td></tr>
      <tr><td>12 tháng</td><td>6,20</td></tr>
    </table>
    <table>
      <tr><td>01 tháng</td><td>0,00</td></tr>
      <tr><td>12 tháng</td><td>4,75%</td></tr>
      <tr><td>Dưới10 triệu</td><td>Từ 10 triệu đếndưới 20 triệu</td></tr>
    </table>"""

    def test_generic_official_table_reads_only_the_first_table(self):
        with mock.patch.object(emailer, "render_js_page", return_value=self.PAGE):
            data = emailer._fetch_generic_official_table("https://example.invalid/")
        self.assertEqual(data["terms"], [
            {"term": "01 tháng", "counter": "3.70%", "online": "3.70%"},
            {"term": "12 tháng", "counter": "6.20%", "online": "6.20%"},
        ])


if __name__ == "__main__":
    unittest.main()
