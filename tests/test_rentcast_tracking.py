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
from scripts.rent_history import make_snapshot, update_history, load_history, AREAS
from scripts.areas import classify_area, polygons, NTA_TO_AREA, south_of_gwb, GWB_POLICY
from scripts.update_listings import area as imported_area

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
        self.history_patch = patch.object(mod, "HISTORY_OUTPUT", root/"market-history.json")
        self.ledger_patch.start();self.output_patch.start();self.history_patch.start()
        self.addCleanup(self.ledger_patch.stop)
        self.addCleanup(self.output_patch.stop)
        self.addCleanup(self.history_patch.stop)
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
        self.assertNotIn("rentcast-gone", ids)  # Prior missing units are not carried forward
        self.assertEqual(result["comparison"]["price_increase_count"],0)
        self.assertEqual(ids["rentcast-stay"]["price_change"],-200)
        self.assertEqual(ids["rentcast-stay"]["first_seen_at"],"2026-11-01T00:00:00+00:00")
        self.assertEqual(ids["rentcast-arrived"]["change_status"],"newly_seen")
        self.assertFalse(any(x["area"]=="Fort Lee" for x in ids.values()))

    def test_successful_refresh_removes_missing_and_inactive_provider_listings(self):
        """The current marketplace contains only newly sampled, Active records."""
        first=[fixture("still-active", 2700),fixture("no-longer-returned", 2750)]
        second=[fixture("still-active", 2700),{**fixture("now-inactive", 2800),"status":"Inactive"}]
        with patch.object(mod, "retrieve", return_value=first) as retrieve:
            mod.fetch()
        self.assertEqual(retrieve.call_count,2)
        first_ids={x["id"] for x in json.loads(mod.OUTPUT.read_text())["listings"]}
        self.assertEqual(first_ids,{"rentcast-still-active","rentcast-no-longer-returned"})
        with patch.object(mod, "retrieve", return_value=second) as retrieve:
            mod.fetch()
        self.assertEqual(retrieve.call_count,2)
        output=json.loads(mod.OUTPUT.read_text())
        self.assertEqual({x["id"] for x in output["listings"]},{"rentcast-still-active"})
        self.assertEqual(output["comparison"]["not_found_count"],1)
        self.assertIn("not rented",output["comparison"]["coverage_warning"].lower())
        self.assertEqual(output["listings"][0]["status_at_check"],"Active")
        self.assertTrue(all(x["status_at_check"]=="Active" for x in output["listings"]))

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

    def test_bridge_boundary_excludes_northern_rentcast_units(self):
        north = fixture("north-of-bridge", 2750, latitude=40.851083, longitude=-73.940032)
        south = fixture("south-of-bridge", 2550, latitude=40.846315, longitude=-73.937177)
        with patch.object(mod,"retrieve",return_value=[north,south]) as retrieve:
            mod.fetch()
        result=json.loads(mod.OUTPUT.read_text())
        self.assertEqual(retrieve.call_count, 2)
        self.assertEqual([x["id"] for x in result["listings"]],["rentcast-south-of-bridge"])
        self.assertEqual(result["geographic_policy"],GWB_POLICY)
        history=json.loads(mod.HISTORY_OUTPUT.read_text())
        self.assertEqual(history["snapshots"][0]["total_count"],1)
        self.assertEqual(history["snapshots"][0]["geographic_policy"],GWB_POLICY)

    def test_fetch_without_reservation_does_not_call_api(self):
        mod.LEDGER.write_text(json.dumps({"entries":[]}))
        with patch.object(mod,"retrieve") as retrieve:
            mod.fetch()
            retrieve.assert_not_called()
        self.assertFalse(mod.OUTPUT.exists())
        self.assertFalse(mod.HISTORY_OUTPUT.exists())

    def test_budget_is_conservative(self):
        mod.LEDGER.write_text(json.dumps({"entries":[
            {"run":"other-attempt","at":NOW,"calls":mod.BUDGET}
        ]}))
        with patch.dict(os.environ,{"GITHUB_RUN_ID":"new-run","GITHUB_RUN_ATTEMPT":"1"}):
            mod.reserve()
        self.assertEqual(sum(x["calls"] for x in json.loads(mod.LEDGER.read_text())["entries"]),mod.BUDGET)



class RentHistoryTests(unittest.TestCase):
    def test_history_aggregations_and_subgroup_medians(self):
        def row(identifier,area,rent,beds):
            return {"id":identifier, "source_kind":"rentcast", "area":area,
                    "rent":rent, "bedrooms":beds}
        observation={
            "checked_at_utc":"2026-11-24T14:00:00Z", "search_method":"test-method",
            "query_counts":{"south":{"returned":500,"at_response_limit":True}},
            "listings":[row("x","Morningside Heights",2300,0),
                        row("y","Morningside Heights",2450,1),
                        row("z","Morningside Heights",2550,1),
                        row("w","Central Harlem",3000,0)]
        }
        p=make_snapshot(observation)
        self.assertEqual(p["total_count"],4)
        self.assertEqual(p["overall"]["all"]["median"],2500)
        self.assertEqual(p["overall"]["studio"]["median"],2650)
        self.assertEqual(p["neighborhoods"]["Morningside Heights"]["all"],{"count":3,"median":2450})
        self.assertEqual(p["neighborhoods"]["Central Harlem"]["one_bed"],{"count":0,"median":None})
        self.assertEqual(len(p["neighborhoods"]),len(AREAS))
        self.assertTrue(p["response_cap_hit"])

    def test_history_is_idempotent_and_separates_methods(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"history.json"
            one={"checked_at_utc":"2026-11-21T12:00:00Z",
                 "search_method":"legacy", "snapshot_reclassified":True,
                 "listings":[{"source_kind":"rentcast","area":"Morningside Heights","rent":2500,"bedrooms":0}]}
            two={"checked_at_utc":"2026-11-28T12:00:00Z",
                 "search_method":"two-circles",
                 "listings":[{"source_kind":"rentcast","area":"Morningside Heights","rent":2700,"bedrooms":0}]}
            self.assertTrue(update_history(one,target))
            self.assertFalse(update_history(one,target))
            self.assertTrue(update_history(two,target))
            history=load_history(target)
            self.assertEqual(len(history["snapshots"]),2)
            self.assertTrue(history["snapshots"][0]["legacy_reclassified"])
            self.assertEqual(history["snapshots"][1]["search_method"],"two-circles")

    def test_never_overwrite_conflicting_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"history.json"
            observed={"checked_at_utc":"2026-11-21T12:00:00Z","search_method":"test","listings":[]}
            update_history(observed,target)
            changed={**observed,"listings":[{"source_kind":"rentcast",
                        "area":"Manhattan Valley","rent":2650,"bedrooms":1}]}
            with self.assertRaises(ValueError):
                update_history(changed,target)

    def test_history_rejects_above_bridge_records(self):
        p={"checked_at_utc":"2026-11-24T14:00:00Z",
           "geographic_policy":GWB_POLICY,
           "listings":[{"source_kind":"rentcast","area":"Washington Heights",
                        "rent":2500,"bedrooms":1,"latitude":40.851083,
                        "longitude":-73.940032}]}
        with self.assertRaises(ValueError):
            make_snapshot(p)
        p["listings"][0].update({"latitude":40.846315,"longitude":-73.937177})
        self.assertEqual(make_snapshot(p)["total_count"],1)

    def test_invalid_market_rows_rejected(self):
        p={"checked_at_utc":"2026-11-21T12:00:00Z",
           "listings":[{"source_kind":"historical","area":"Morningside Heights","rent":2500,"bedrooms":0}]}
        with self.assertRaises(ValueError):
            make_snapshot(p)
        p["listings"][0]["source_kind"]="rentcast"
        p["listings"][0]["rent"]=1700
        with self.assertRaises(ValueError):
            make_snapshot(p)



class NeighborhoodPolygonTests(unittest.TestCase):
    def test_all_selected_boundaries_present(self):
        self.assertEqual(len(polygons()),9)
        self.assertEqual(len(NTA_TO_AREA),9)

    def test_columbia_is_morningside_heights(self):
        self.assertEqual(classify_area(40.808,-73.960, "NY"),"Morningside Heights")

    def test_hamilton_heights_and_central_harlem(self):
        self.assertEqual(classify_area(40.826,-73.947,"NY"),"Hamilton Heights")
        self.assertEqual(classify_area(40.819,-73.945,"NY"),"Central Harlem")

    def test_sloped_bridge_boundary_keeps_southern_washington_heights(self):
        self.assertTrue(south_of_gwb(40.846315,-73.937177))  # W 176th Street
        self.assertFalse(south_of_gwb(40.851083,-73.940032)) # W 181st Street
        self.assertFalse(south_of_gwb(40.851027,-73.942044)) # Haven Avenue near bridge
        self.assertEqual(classify_area(40.846315,-73.937177,"NY"),"Washington Heights")
        self.assertIsNone(classify_area(40.851083,-73.940032,"NY"))
        self.assertIsNone(imported_area({"latitude":40.851083,"longitude":-73.940032,"state":"NY"}))
        self.assertEqual(imported_area({"latitude":40.846315,"longitude":-73.937177,"state":"NY"}),"Washington Heights")

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
                if not south_of_gwb(lat,lon):
                    continue
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
