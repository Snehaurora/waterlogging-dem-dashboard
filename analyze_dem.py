from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import shapes
from scipy import ndimage as ndi
from shapely.geometry import shape

# ---------- settings you can change ----------
RAW = Path("raw_data")   # the extracted zip can sit anywhere inside this folder
MIN_DEPTH = 0.15         # ignore depressions shallower than 15 cm
MIN_AREA = 25.0          # ignore depressions smaller than 25 m2
MAX_HOTSPOTS = 300       # keep the largest 300 by volume
# ---------------------------------------------

hits = sorted(RAW.rglob("depression_depth.tif"))
if not hits:
    raise SystemExit("Cannot find depression_depth.tif inside raw_data. Did you extract the zip there?")
print("Using:", hits[0])

with rasterio.open(hits[0]) as src:
    depth = src.read(1, masked=True).astype("float32").filled(0)
    transform, crs = src.transform, src.crs
    print("CRS:", crs, "| pixel:", src.res, "| size:", src.width, "x", src.height)

depth = np.nan_to_num(depth, nan=0.0)
depth[depth < 0] = 0

px_area = abs(transform.a * transform.e)
mask = depth >= MIN_DEPTH
labels, n = ndi.label(mask)
ids = np.arange(1, n + 1)
area = ndi.sum(mask.astype("float32"), labels, ids) * px_area
vol = ndi.sum(depth, labels, ids) * px_area
dmax = ndi.maximum(depth, labels, ids)

keep = np.zeros(n + 1, bool)
keep[1:] = area >= MIN_AREA
labels = np.where(keep[labels], labels, 0).astype(np.int32)
print("Depressions found:", int(keep.sum()))

rows = []
for geom, val in shapes(labels, mask=labels > 0, transform=transform):
    i = int(val) - 1
    rows.append({"depth_m": round(float(dmax[i]), 2), "area_m2": round(float(area[i]), 1),
                 "volume_m3": round(float(vol[i]), 1), "geometry": shape(geom)})

gdf = gpd.GeoDataFrame(rows, crs=crs)
gdf = gdf.sort_values("volume_m3", ascending=False).head(MAX_HOTSPOTS).reset_index(drop=True)
gdf["rank"] = gdf.index + 1
gdf["id"] = ["H%03d" % r for r in gdf["rank"]]
gdf["is_sample"] = False
gdf["geometry"] = gdf.geometry.simplify(abs(transform.a))
gdf = gdf.to_crs(4326)

Path("data").mkdir(exist_ok=True)
gdf[["id", "rank", "depth_m", "area_m2", "volume_m3", "is_sample", "geometry"]].to_file(
    "data/hotspots.geojson", driver="GeoJSON")
print("Saved data/hotspots.geojson with", len(gdf), "hotspots")
print("Deepest: %.2f m | total volume: %.0f m3" % (gdf["depth_m"].max(), gdf["volume_m3"].sum()))