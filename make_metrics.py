import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling

RAW = Path("raw_data")


def find(name):
    hits = sorted(RAW.rglob(name))
    if not hits:
        raise SystemExit("Cannot find " + name + " inside raw_data")
    return hits[0]


with rasterio.open(find("demground.tif")) as e, rasterio.open(find("iitr_dtm.tif")) as d:
    print("DEM:", e.crs, e.res, "| DTM:", d.crs, d.res)
    dem = e.read(1, masked=True).astype("float64")
    win = d.window(*e.bounds).round_offsets().round_lengths()
    ref = d.read(1, window=win, out_shape=(e.height, e.width),
                 resampling=Resampling.average, masked=True).astype("float64")

ok = ~(np.ma.getmaskarray(dem) | np.ma.getmaskarray(ref))
diff = (dem.filled(np.nan) - ref.filled(np.nan))[ok]
diff = diff[np.isfinite(diff)]
offset = float(np.median(diff))
err = diff - offset

rmse = float(np.sqrt((err ** 2).mean()))
mae = float(np.abs(err).mean())
nmad = float(1.4826 * np.median(np.abs(err - np.median(err))))
within25 = float(100 * (np.abs(err) <= 0.25).mean())
within50 = float(100 * (np.abs(err) <= 0.50).mean())
close = np.abs(err) < 1.0
rmse_close = float(np.sqrt((err[close] ** 2).mean()))

print("cells compared:", err.size)
print("constant offset DEM - DTM: %.2f m" % offset)
print("RMSE %.2f | MAE %.2f | NMAD %.2f | within 25 cm %.1f%% | within 50 cm %.1f%%" % (rmse, mae, nmad, within25, within50))
print("RMSE without the %.1f%% of cells off by more than 1 m: %.2f" % (100 * (~close).mean(), rmse_close))

metrics = {
    "is_sample": False,
    "precision": None, "recall": None, "f1": None, "iou": None,   # need field-marked waterlogged spots
    "dtm_rmse_m": round(rmse, 2),
    "dtm_mae_m": round(mae, 2),
    "dtm_nmad_m": round(nmad, 2),
    "dtm_offset_m": round(offset, 2),
    "within_25cm_pct": round(within25, 1),
    "within_50cm_pct": round(within50, 1),
    "rmse_without_outliers_m": round(rmse_close, 2),
    "cells_compared": int(err.size),
}
Path("data").mkdir(exist_ok=True)
Path("data/metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
print("Saved data/metrics.json")
