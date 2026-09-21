import asf_search as asf

SEED_GRANULES = [
    "S1_056013_IW2_20250927T125539_VV_5367-BURST",
    "S1_056012_IW2_20250927T125536_VV_01C8-BURST",
    "S1_056011_IW2_20250927T125534_VV_01C8-BURST",
]

results = asf.granule_search(SEED_GRANULES)

results.raise_if_incomplete()

print(f"\nFound {len(results)} seed bursts\n")

for product in results:
    p = product.properties
    burst = p.get("burst") or {}

    print("=" * 90)
    print("Scene Name        :", p.get("sceneName"))
    print("Full Burst ID     :", burst.get("fullBurstID"))
    print("Relative Burst ID :", burst.get("relativeBurstID"))
    print("Absolute Burst ID :", burst.get("absoluteBurstID"))
    print("Path              :", p.get("pathNumber"))
    print("Direction         :", p.get("flightDirection"))
    print("Polarization      :", p.get("polarization"))
    print("Beam Swath        :", p.get("beamSwath"))
    print("Start Time        :", p.get("startTime"))
    print("Burst metadata    :", burst)
    