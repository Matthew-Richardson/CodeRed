import arcpy
import os
import time
import zipfile
from datetime import datetime
from arcpy import env

# Set environment
env.workspace = r"T:\Richardsonm\OEM_CodeRED"
env.overwriteOutput = True

# Function to safely delete files with retry logic
def try_delete(file_path, retries=5, wait=2):
    for attempt in range(retries):
        try:
            os.remove(file_path)
            return True
        except Exception as e:
            print(f"Attempt {attempt + 1} failed to delete {os.path.basename(file_path)}: {e}")
            time.sleep(wait)
    print(f"❌ Failed to delete {file_path} after {retries} attempts.")
    return False

# --- Clean up old LPC_CodeRED outputs and zips in workspace ---
for fname in os.listdir(env.workspace):
    if fname.startswith("LPC_CodeRED_") and fname.lower().endswith((
        ".shp", ".shx", ".dbf", ".prj", ".sbn", ".sbx", ".cpg", ".xml", ".zip", ".lock"
    )):
        fpath = os.path.join(env.workspace, fname)
        try_delete(fpath)

# Prepare output file name
today_str = datetime.today().strftime("%Y%m%d")
output_name = f"LPC_CodeRED_{today_str}.shp"
final_output = os.path.join(env.workspace, output_name)

# Temp shapefile output directory
temp_dir = os.path.join(env.workspace, "temp")
if not os.path.exists(temp_dir):
    os.makedirs(temp_dir)

# --- Clean up temp shapefiles ---
for fname in os.listdir(temp_dir):
    if fname.lower().endswith((".shp", ".shx", ".dbf", ".prj", ".sbn", ".sbx", ".cpg", ".xml", ".lock")):
        fpath = os.path.join(temp_dir, fname)
        try_delete(fpath)

# Helper function to delete all components of a shapefile
def delete_shapefile(base_name):
    extensions = [".shp", ".shx", ".dbf", ".prj", ".sbn", ".sbx", ".cpg", ".xml", ".lock"]
    for ext in extensions:
        fpath = os.path.join(temp_dir, base_name + ext)
        if os.path.exists(fpath):
            try_delete(fpath)

# Define base names for temp shapefiles
point_base = "AddressPoints"
polygon_base = "Parcels"
point_shp = os.path.join(temp_dir, point_base + ".shp")
polygon_shp = os.path.join(temp_dir, polygon_base + ".shp")

# Extra cleanup of these named shapefiles
delete_shapefile(point_base)
delete_shapefile(polygon_base)
time.sleep(2)

# Input SDE feature classes
point_fc = r"C:\Users\RichardsonMD\AppData\Roaming\Esri\ArcGISPro\Favorites\SQLDB4GIS.sde\EntGDB.SDE.AddressRelated\EntGDB.SDE.AddressPoints"
polygon_fc = r"C:\Users\RichardsonMD\AppData\Roaming\Esri\ArcGISPro\Favorites\SQLDB4GIS.sde\EntGDB.sde.VWPARCEL"

# Export to shapefiles
arcpy.conversion.FeatureClassToFeatureClass(point_fc, temp_dir, point_base + ".shp")
arcpy.conversion.FeatureClassToFeatureClass(polygon_fc, temp_dir, polygon_base + ".shp")

# Step 1: Spatial Join
spatial_join_fc = os.path.join(temp_dir, "Temp_SpatialJoin.shp")
if arcpy.Exists(spatial_join_fc):
    arcpy.management.Delete(spatial_join_fc)

arcpy.analysis.SpatialJoin(
    target_features=point_shp,
    join_features=polygon_shp,
    out_feature_class=spatial_join_fc,
    join_type="KEEP_ALL",
    match_option="WITHIN"
)

# Step 2: Remove unwanted fields
keep_fields = ["SITE_DR", "SITE_ST", "SITE_MD", "SITE_UNIT", "SITE_NUM", "LABEL_TYPE", "PROPERTY_A", "SITE_CITY", "SITE_ZIP", "STATE_CO"]
all_fields = [f.name for f in arcpy.ListFields(spatial_join_fc)]
drop_fields = [f for f in all_fields if f not in keep_fields and f not in ("FID", "Shape")]

arcpy.management.DeleteField(spatial_join_fc, drop_fields)

# Step 3: Reproject to NAD83 and save to output shapefile
output_sr = arcpy.SpatialReference(4269)
arcpy.management.Project(spatial_join_fc, final_output, output_sr)

# Step 4: Add 'State' field and populate with 'CO'
state_field = "State"
if state_field not in [f.name for f in arcpy.ListFields(final_output)]:
    arcpy.management.AddField(final_output, state_field, "TEXT", field_length=2)

arcpy.management.CalculateField(
    in_table=final_output,
    field=state_field,
    expression="'CO'",
    expression_type="PYTHON3"
)

# Step 5: Zip the final shapefile and components (excluding .lock files)
zip_path = os.path.join(env.workspace, f"LPC_CodeRED_{today_str}.zip")
shapefile_components = [
    f for f in os.listdir(env.workspace)
    if f.startswith(f"LPC_CodeRED_{today_str}.") and not f.endswith(".lock")
]

with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
    for f in shapefile_components:
        zipf.write(os.path.join(env.workspace, f), f)

print("✅ Processing complete.")
print(f"🗂️  Final shapefile: {final_output}")
print(f"📦 Zipped output: {zip_path}")
