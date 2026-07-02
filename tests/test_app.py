import copy
import unittest
from datetime import date

import app


def sample_data():
    return {
        "bookings": [],
        "clients": [
            {
                "id": "c_1",
                "first_name": "Mario",
                "last_name": "Rossi",
                "phone": "333",
                "email": "mario@example.com",
                "notes": "",
                "birth_date": "",
                "created_at": "",
            }
        ],
        "settlements": [],
        "audit_log": [],
    }


def paid_booking():
    return {
        "id": "b_1",
        "client_id": "c_1",
        "date": date.today().isoformat(),
        "time": "09:30",
        "name": "Rossi Mario",
        "phone": "333",
        "email": "mario@example.com",
        "note": "",
        "status": "Confermata",
        "amount": 30.0,
        "paid": True,
        "gift": False,
        "paid_to_gym_at": "2026-01-01T10:00:00",
        "paid_to_gym_by": "bodycenter",
        "settlement_id": "",
        "instructor": "Grazia",
        "created_by": "bodycenter",
    }


class BookingAccountingTests(unittest.TestCase):
    def setUp(self):
        self.original_current_user = app.current_user
        self.original_instructor_share = app.instructor_share
        self.original_gym_share = app.gym_share
        app.current_user = lambda: "tester"
        app.instructor_share = lambda: 0.40
        app.gym_share = lambda: 0.60

    def tearDown(self):
        app.current_user = self.original_current_user
        app.instructor_share = self.original_instructor_share
        app.gym_share = self.original_gym_share

    def test_create_booking_gift_has_zero_amount_and_audit(self):
        data = sample_data()
        booking = app.create_booking(data, "c_1", date.today(), "09:30", 30, False, "Grazia", "", True)

        self.assertTrue(booking["gift"])
        self.assertEqual(booking["amount"], 0.0)
        self.assertTrue(booking["paid"])
        self.assertEqual(booking["paid_to_gym_at"], "")
        self.assertEqual(data["audit_log"][-1]["action"], "create_booking")

    def test_mark_gift_clears_amount_and_prevents_cash(self):
        data = sample_data()
        booking = paid_booking()
        data["bookings"].append(booking)

        ok, _ = app.mark_gift(data, "b_1", "prova")

        self.assertTrue(ok)
        self.assertTrue(booking["gift"])
        self.assertEqual(booking["amount"], 0.0)
        self.assertEqual(booking["paid_to_gym_at"], "")
        self.assertEqual(data["audit_log"][-1]["action"], "mark_gift")

    def test_unmark_gift_restores_amount_and_paid_state(self):
        data = sample_data()
        booking = paid_booking()
        app.mark_gift({"bookings": [booking], "audit_log": []}, "b_1")
        data["bookings"].append(booking)

        ok, _ = app.unmark_gift(data, "b_1", 35, True, "pagata")

        self.assertTrue(ok)
        self.assertFalse(booking["gift"])
        self.assertEqual(booking["amount"], 35.0)
        self.assertTrue(booking["paid"])
        self.assertTrue(booking["paid_to_gym_at"])
        self.assertEqual(data["audit_log"][-1]["action"], "unmark_gift")

    def test_mark_paid_rejects_gift_and_accepts_regular_booking(self):
        data = sample_data()
        regular = paid_booking()
        regular["paid"] = False
        gift = copy.deepcopy(regular)
        gift["id"] = "b_2"
        gift["gift"] = True
        gift["amount"] = 0.0
        data["bookings"].extend([regular, gift])

        ok_regular, _ = app.mark_paid(data, "b_1")
        ok_gift, _ = app.mark_paid(data, "b_2")

        self.assertTrue(ok_regular)
        self.assertTrue(regular["paid"])
        self.assertFalse(ok_gift)

    def test_mark_share_creates_40_60_settlement(self):
        data = sample_data()
        booking = paid_booking()
        data["bookings"].append(booking)

        ok, _ = app.mark_share(data, "b_1")

        self.assertTrue(ok)
        self.assertEqual(len(data["settlements"]), 1)
        self.assertEqual(data["settlements"][0]["instructor_amount"], 12.0)
        self.assertEqual(data["settlements"][0]["gym_amount"], 18.0)
        self.assertEqual(booking["settlement_id"], data["settlements"][0]["id"])
        self.assertEqual(data["audit_log"][-1]["action"], "mark_share")

    def test_update_client_updates_linked_bookings_and_audit(self):
        data = sample_data()
        booking = paid_booking()
        data["bookings"].append(booking)

        ok, _ = app.update_client(data, "c_1", "Luigi", "Verdi", "444", "luigi@example.com", "", "nota")

        self.assertTrue(ok)
        self.assertEqual(booking["name"], "Verdi Luigi")
        self.assertEqual(booking["phone"], "444")
        self.assertEqual(booking["email"], "luigi@example.com")
        self.assertEqual(data["audit_log"][-1]["action"], "update_client")


if __name__ == "__main__":
    unittest.main()
