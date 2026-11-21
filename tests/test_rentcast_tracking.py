"""Offline tests for tracking and quota protections. No RentCast API requests."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from scripts import fetch_rentcast as mod
from scripts.unit_filter import room_rental_reason
from scripts.areas import classify_area, polygons, NTA_TO_AREA

NOW = datetime.now(timezone.utc).isoformat()
def fixture(identifier, price, latitude=40.808, longitude=-73.96, state="NY"):
    return {
        "id": identifier, "price": price, "bedrooms": 1, "status": "Active",
        "latitude": latitude, "longitude": longitude, "state": state,
        "city": "New York", "formattedAddress": "Test address for "+identifier,
        "lastSeenDate": "2026-11-21T09:00:00Z"
    }

class RentcastTrackingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.ledger_patch = patch.object(mod, "LEDGER", root/"budget.json")
        self.output_patch = patch.object(mod, "OUTPUT", root/"rentcast.json")
        self.ledger_patch.start();self.output_patch.start()
        self.addCleanup(self.ledger_patch.stop)
        self.addCleanup(self.output_patch.stop)
        self.env = patch.dict(os.environ, {"GITHUB_RUN_ID": "test-123", "GITHUB_RUN_ATTEMPT": "1", "RENTCAST_API_KEY": "mock-not-real"}, clear=False)
        self.env.start();self.addCleanup(self.env.stop)
        mod.LEDGER.write_text(json.dumps({"entries": [{"run":"test-123-1","at": NOW,"calls":mod.CALLS_PER_RUN}]}))

    def test_two_searches_and_change_detection(self):
        previous = {
            "source": "RentCast rental listings API",
            "checked_at_utc": "2026-11-14T17:00:00+00:00",
            "search_method": mod.SEARCH_METHOD,
            "listings": [
                {"id":"rentcast-stay", "area":"Morningside Heights", "rent":2800,"first_seen_at":"2026-11-01T00:00:00+00:00"},
                {"id":"rentcast-gone","area":"Morningside Heights","rent":2900}
            ]
        }
        mod.OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        mod.OUTPUT.write_text(json.dumps(previous))
        rows = [fixture("stay", 2600),fixture("arrived", 2750),fixture("out-of-state", 2400,state="NJ"),fixture("below-minimum",2249),fixture("above-maximum",3001)]
        with patch.object(mod, "retrieve", return_value=rows) as retrieve:
            mod.fetch()
        self.assertEqual(retrieve.call_count, 2)
        result = json.loads(mod.OUTPUT.read_text())
        ids = {x["id"]:x for x in result["listings"]}
        self.assertEqual(len(ids),2)
        self.assertEqual(result["comparison"]["price_drop_count"],1)
        self.assertEqual(result["comparison"]["newly_found_count"],1)
        self.assertEqual(result["comparison"]["not_found_count"],1)
        self.assertEqual(result["comparison"]["price_increase_count"],0)
        self.assertEqual(ids["rentcast-stay"]["price_change"],-200)
        self.assertEqual(ids["rentcast-stay"]["first_seen_at"],"2026-11-01T00:00:00+00:00")
        self.assertEqual(ids["rentcast-arrived"]["change_status"],"newly_seen")
        self.assertFalse(any(x["area"]=="Fort Lee" for x in ids.values()))

    def test_first_snapshot_is_baseline(self):
        with patch.object(mod,"retrieve",return_value=[fixture("first",2300)]):
            mod.fetch()
        result=json.loads(mod.OUTPUT.read_text())
        self.assertTrue(result["comparison"]["baseline"])
        self.assertEqual(result["comparison"]["newly_found_count"],0)
        self.assertEqual(result["listings"][0]["change_status"],"baseline")

    def test_exact_price_boundaries_are_included(self):
        with patch.object(mod, "retrieve", return_value=[
            fixture("lower-boundary",2250),fixture("upper-boundary",3000),
            fixture("below-boundary",2249),fixture("above-boundary",3001)
        ]) as retrieve:
            mod.fetch()
        self.assertEqual(retrieve.call_count,2)
        result=json.loads(mod.OUTPUT.read_text())
        self.assertEqual({x["rent"] for x in result["listings"]},{2250,3000})
        self.assertEqual(result["rent_min"],2250)
        self.assertEqual(result["rent_max"],3000)

    def test_two_searches_deduplicate_same_listing(self):
        responses=[
            [fixture("same",2500),fixture("southern",2600)],
            [fixture("same",2500),fixture("northern",2700, latitude=40.826, longitude=-73.947)]
        ]
        with patch.object(mod, "retrieve", side_effect=responses) as retrieve:
            mod.fetch()
        result=json.loads(mod.OUTPUT.read_text())
        self.assertEqual(retrieve.call_count,2)
        self.assertEqual(len(result["listings"]),3)
        self.assertEqual(sum(z["duplicate_ids"] for z in result["query_counts"].values()),1)
        self.assertEqual(result["search_method"],mod.SEARCH_METHOD)

    def test_new_geography_method_resets_baseline(self):
        mod.OUTPUT.write_text(json.dumps({
            "checked_at_utc":"2026-11-14T00:00:00Z",
            "search_method":"legacy-one-circle-reclassified-with-2020-nta",
            "listings":[{"id":"rentcast-missing", "rent":3000,"area":"South Harlem"}]
        }))
        with patch.object(mod,"retrieve",return_value=[fixture("now",2400)]):
            mod.fetch()
        result=json.loads(mod.OUTPUT.read_text())
        self.assertTrue(result["comparison"]["baseline"])
        self.assertTrue(result["comparison"]["methodology_changed"])
        self.assertEqual(result["comparison"]["newly_found_count"],0)
        self.assertEqual(result["comparison"]["not_found_count"],0)
        self.assertEqual(result["listings"][0]["change_status"],"baseline")

    def test_fetch_without_reservation_does_not_call_api(self):
        mod.LEDGER.write_text(json.dumps({"entries":[]}))
        with patch.object(mod,"retrieve") as retrieve:
            mod.fetch()
            retrieve.assert_not_called()
        self.assertFalse(mod.OUTPUT.exists())

    def test_budget_is_conservative(self):
        mod.LEDGER.write_text(json.dumps({"entries":[
            {"run":"other-attempt","at":NOW,"calls":mod.BUDGET}
        ]}))
        with patch.dict(os.environ,{"GITHUB_RUN_ID":"new-run","GITHUB_RUN_ATTEMPT":"1"}):
            mod.reserve()
        self.assertEqual(sum(x["calls"] for x in json.loads(mod.LEDGER.read_text())["entries"]),mod.BUDGET)


class NeighborhoodPolygonTests(unittest.TestCase):
    def test_all_selected_boundaries_present(self):
        self.assertEqual(len(polygons()),9)
        self.assertEqual(len(NTA_TO_AREA),9)

    def test_columbia_is_morningside_heights(self):
        self.assertEqual(classify_area(40.808,-73.960, "NY"),"Morningside Heights")

    def test_hamilton_heights_and_central_harlem(self):
        self.assertEqual(classify_area(40.826,-73.947,"NY"),"Hamilton Heights")
        self.assertEqual(classify_area(40.819,-73.945,"NY"),"Central Harlem")

    def test_inwood_and_bronx_are_excluded(self):
        self.assertIsNone(classify_area(40.877,-73.928,"NY"))
        self.assertIsNone(classify_area(40.806,-73.925,"NY"))
        self.assertIsNone(classify_area(40.809,-73.943,"NJ"))
        self.assertIsNone(classify_area(None,None,"NY"))

    def test_circles_cover_target_polygon_vertices(self):
        import math
        def vertices(obj):
            if isinstance(obj,list) and len(obj)==2 and isinstance(obj[0],(int,float)):
                return [obj]
            if isinstance(obj,list):
                return [c for child in obj for c in vertices(child)]
            return []
        def miles(lat,lon,a,b):
            rad=math.pi/180
            h=math.sin((lat-a)*rad/2)**2+math.cos(lat*rad)*math.cos(a*rad)*math.sin((lon-b)*rad/2)**2
            return 3958.8*2*math.asin(math.sqrt(min(1,h)))
        circles=[(float(q["latitude"]),float(q["longitude"]),float(q["radius"])) for _,q in mod.SEARCHES]
        for feature in polygons():
            for lon,lat in vertices(feature["geometry"]["coordinates"]):
                self.assertTrue(any(miles(lat,lon,a,b)<=radius+0.01 for a,b,radius in circles),
                                msg=feature["properties"]["ntaname"])


class RoomRentalFilteringTests(unittest.TestCase):
    def test_private_room_is_filtered(self):
        self.assertIsNotNone(room_rental_reason({"bedrooms":1,"title":"Private room in a shared apartment"}))

    def test_coliving_is_filtered(self):
        self.assertIsNotNone(room_rental_reason({"description":"Modern co-living with shared kitchen and bathrooms"}))

    def test_room_in_three_bedroom_apartment_is_filtered(self):
        self.assertIsNotNone(room_rental_reason({"title": "Furnished room in a 3-bedroom apartment"}))

    def test_provider_room_type_is_filtered(self):
        self.assertIsNotNone(room_rental_reason({"listingType": "Room"}))

    def test_unit_room_number_is_filtered(self):
        self.assertIsNotNone(room_rental_reason({"addressLine2":"Room 2B", "bedrooms":1}))

    def test_missing_private_bath_is_filtered(self):
        self.assertIsNotNone(room_rental_reason({"bedrooms":0,"bathrooms":0,"propertyType":"Apartment"}))

    def test_valid_studio_is_not_filtered(self):
        self.assertIsNone(room_rental_reason({"bedrooms":0,"bathrooms":1,"addressLine2":"Apt 4C",
                                              "description":"Bright studio with living room and kitchenette"}))

    def test_valid_one_bed_is_not_filtered(self):
        self.assertIsNone(room_rental_reason({"bedrooms":1,"bathrooms":1,"unit":"Unit 3B",
                                              "description":"One bedroom apartment with private living room"}))

    def test_not_proven_private_is_not_mislabeled_as_room(self):
        self.assertIsNone(room_rental_reason({"bedrooms":1,"bathrooms":None,
                                              "formattedAddress":"123 Broadway, New York"}))

if __name__=="__main__":
    unittest.main()
