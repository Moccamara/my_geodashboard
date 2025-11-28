import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from pathlib import Path
import os
import altair as alt
import json
import pandas as pd
from shapely.geometry import Point
import matplotlib.pyplot as plt

# ---------------------------------------------------------
# FRONT-END PROTECTION (Disable print, screenshot, right-click, copy)
# ---------------------------------------------------------
protect_js = """
<style>
/* Disable text selection */
* {
    -webkit-touch-callout: none;
    -webkit-user-select: none;
    -khtml-user-select: none;
    -moz-user-select: none;
    -ms-user-select: none;
    user-select: none;
}

/* Disable right click */
body {
    -webkit-touch-callout: none;
}
</style>

<script>
// Disable CTRL+P, CTRL+S, CTRL+U, PrintScreen
document.addEventListener('keydown', function(e) {

    // Disable PrintScreen key
    if (e.key === 'PrintScreen') {
        e.preventDefault();
        alert("Screenshots are disabled.");
    }

    // Disable printing, saving, view-source
    if (e.ctrlKey && (e.key === 'p' || e.key === 's' || e.key === 'u')) {
        e.preventDefault();
        alert("Printing and saving are disabled.");
    }
});

// Disable right-click menu
document.addEventListener('contextmenu', event => event.preventDefault());
</script>
"""

st.markdown(protect_js, unsafe_allow_html=True)

# -----------------------------
# App title
# -----------------------------
APP_TITLE = '**RGPH5 Census Update**'
st.title(APP_TITLE)

# ---------------------------------------------------------
# FULL DASHBOARD ACCESS LOCK (Only authorized users)
# ---------------------------------------------------------
ACCESS_PASSWORD = "instat2025"   # <<< Change your password here

access_input = st.sidebar.text_input("Enter Dashboard Access Password:", type="password")

if access_input != ACCESS_PASSWORD:
    st.warning("🔐 Access Locked. Enter the correct password to open the dashboard.")
    st.stop()

# -----------------------------
# Folder containing GeoJSON/Shapefile
# -----------------------------
folder = Path("data")  # relative path

geo_file = next((f for f in folder.glob("*.geojson")), None)
if not geo_file:
    geo_file = next((f for f in folder.glob("*.shp")), None)

if not geo_file:
    st.error("No GeoJSON ou Shapefile file find.")
    st.stop()

gdf = gpd.read_file(geo_file)
gdf.columns = gdf.columns.str.lower().str.strip()

rename_map = {
    "lregion": "region",
    "lcercle": "cercle",
    "lcommune": "commune",
    "idse_new": "idse_new"
}
gdf = gdf.rename(columns=rename_map)
gdf = gdf.to_crs(epsg=4326)
gdf = gdf[gdf.is_valid & ~gdf.is_empty]

# -----------------------------
# Sidebar + LOGO
# -----------------------------
logo_path = Path("images/instat_logo.png")
with st.sidebar:
    st.image(logo_path, width=120)
    st.markdown("### Geographical level")

# -----------------------------
# Filters
# -----------------------------
regions = sorted(gdf["region"].dropna().unique())
region_selected = st.sidebar.selectbox("Region", regions)
gdf_region = gdf[gdf["region"] == region_selected]

cercles = sorted(gdf_region["cercle"].dropna().unique())
cercle_selected = st.sidebar.selectbox("Cercle", cercles)
gdf_cercle = gdf_region[gdf_region["cercle"] == cercle_selected]

communes = sorted(gdf_cercle["commune"].dropna().unique())
commune_selected = st.sidebar.selectbox("Commune", communes)
gdf_commune = gdf_cercle[gdf_cercle["commune"] == commune_selected]

idse_list = ["No filtre"] + sorted(gdf_commune["idse_new"].dropna().unique().tolist())
idse_selected = st.sidebar.selectbox("IDSE_NEW (optionnal)", idse_list)

gdf_idse = gdf_commune.copy()
if idse_selected != "No filtre":
    gdf_idse = gdf_commune[gdf_commune["idse_new"] == idse_selected]

for col in ["pop_se", "pop_se_ct"]:
    if col not in gdf_idse.columns:
        gdf_idse[col] = 0

# -----------------------------
# Map bounds
# -----------------------------
minx, miny, maxx, maxy = gdf_idse.total_bounds
center_lat = (miny + maxy) / 2
center_lon = (minx + maxx) / 2

# -----------------------------
# Folium Map
# -----------------------------
m = folium.Map(location=[center_lat, center_lon], zoom_start=19, tiles="OpenStreetMap")
m.fit_bounds([[miny, minx], [maxy, maxx]])

folium.GeoJson(
    gdf_idse,
    name="IDSE Layer",
    style_function=lambda x: {"fillOpacity": 0, "color": "blue", "weight": 2},
    tooltip=folium.GeoJsonTooltip(
        fields=["idse_new", "pop_se", "pop_se_ct"], localize=True, sticky=True
    ),
    popup=folium.GeoJsonPopup(fields=["idse_new", "pop_se", "pop_se_ct"], localize=True)
).add_to(m)

# -----------------------------
# SECURED CSV UPLOAD (Only admin)
# -----------------------------
st.sidebar.markdown("### Import CSV Points")

ADMIN_PASSWORD = "instat2025"   # <<< Change your admin upload password here
admin_input = st.sidebar.text_input("Enter Admin Password:", type="password")

csv_file = None
points_gdf = None

if admin_input == ADMIN_PASSWORD:
    csv_file = st.sidebar.file_uploader("Upload CSV", type=["csv"])
else:
    st.sidebar.info("CSV upload disabled (no permission).")

if csv_file:
    try:
        df_csv = pd.read_csv(csv_file)
        df_csv = df_csv.dropna(subset=["LAT", "LON"])
        if not df_csv.empty:
            points_gdf = gpd.GeoDataFrame(
                df_csv,
                geometry=gpd.points_from_xy(df_csv["LON"], df_csv["LAT"]),
                crs="EPSG:4326"
            )
    except Exception as e:
        st.sidebar.error(f"Error loading CSV: {e}")

# Add points
if points_gdf is not None and not points_gdf.empty:
    for _, row in points_gdf.iterrows():
        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x],
            radius=2,
            color="red",
            fill=True,
            fill_opacity=0.8
        ).add_to(m)

# -----------------------------
# Layout
# -----------------------------
col_map, col_chart = st.columns([4, 1])

with col_map:
    st.subheader(
        f"🗺️ Commune : {commune_selected}"
        if idse_selected == "No filtre"
        else f"🗺️ IDSE {idse_selected}"
    )
    st_folium(m, width=530, height=350)

# -----------------------------
# Footer
# -----------------------------
st.markdown("""
**Projet : Actualisation de la cartographie du RGPG5 (AC-RGPH5) – Mali**  
Développé avec Streamlit sous Python par **CAMARA, PhD** • © 2025
""")
