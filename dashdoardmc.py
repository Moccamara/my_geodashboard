import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from pathlib import Path
import pandas as pd
from shapely.geometry import Point
import matplotlib.pyplot as plt

# -----------------------------
# App title
# -----------------------------
APP_TITLE = '**RGPH5 Census Update**'
st.title(APP_TITLE)

# -----------------------------
# Load GeoJSON/Shapefile
# -----------------------------
folder = Path("data")

geo_file = next((f for f in folder.glob("*.geojson")), None)
if not geo_file:
    geo_file = next((f for f in folder.glob("*.shp")), None)

if not geo_file:
    st.error("No GeoJSON or Shapefile found in /data folder.")
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
idse_selected = st.sidebar.selectbox("IDSE_NEW (optional)", idse_list)

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
m = folium.Map(location=[center_lat, center_lon], zoom_start=18, tiles="OpenStreetMap")
m.fit_bounds([[miny, minx], [maxy, maxx]])

# SE Polygon
folium.GeoJson(
    gdf_idse,
    name="IDSE Layer",
    style_function=lambda x: {"fillOpacity": 0, "color": "blue", "weight": 2},
    tooltip=folium.GeoJsonTooltip(fields=["idse_new", "pop_se", "pop_se_ct"], localize=True, sticky=True),
    popup=folium.GeoJsonPopup(fields=["idse_new", "pop_se", "pop_se_ct"], localize=True)
).add_to(m)

# -----------------------------
# 📍 Add "My Position" Button (GPS) — FIXED VERSION
# -----------------------------
gps_js = """
function addGPS() {

    // Check if map exists
    if (!window.map) {
        console.log("Map not ready");
        return;
    }

    var customControl = L.Control.extend({
        options: { position: 'topleft' },
        onAdd: function (map) {
            var btn = L.DomUtil.create('button');
            btn.title = "My Position";
            btn.innerHTML = "📍";
            btn.style.backgroundColor = "white";
            btn.style.width = "40px";
            btn.style.height = "40px";
            btn.style.border = "2px solid #444";
            btn.style.borderRadius = "5px";
            btn.style.cursor = "pointer";

            btn.onclick = function(){
                if (navigator.geolocation) {
                    navigator.geolocation.getCurrentPosition(function(position){
                        var lat = position.coords.latitude;
                        var lon = position.coords.longitude;

                        L.marker([lat, lon]).addTo(window.map)
                          .bindPopup("📱 You are here")
                          .openPopup();

                        window.map.setView([lat, lon], 19);
                    });
                } else {
                    alert("Geolocation not supported");
                }
            };
            return btn;
        }
    });

    window.map.addControl(new customControl());
}

setTimeout(addGPS, 500);
"""

m.get_root().html.add_child(folium.Element(f"<script>{gps_js}</script>"))

# -----------------------------
# CSV Upload
# -----------------------------
st.sidebar.markdown("### Import CSV Points")
csv_file = st.sidebar.file_uploader("Upload CSV", type=["csv"])

points_gdf = None

if csv_file:
    try:
        df_csv = pd.read_csv(csv_file)
        df_csv = df_csv.dropna(subset=["LAT", "LON"])
        points_gdf = gpd.GeoDataFrame(
            df_csv,
            geometry=gpd.points_from_xy(df_csv["LON"], df_csv["LAT"]),
            crs="EPSG:4326"
        )
    except Exception as e:
        st.sidebar.error(f"Error loading CSV: {e}")

if points_gdf is not None and not points_gdf.empty:
    for _, row in points_gdf.iterrows():
        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x],
            radius=3,
            color="red",
            fill=True,
            fill_opacity=0.8
        ).add_to(m)

# -----------------------------
# Display Map
# -----------------------------
col_map, col_chart = st.columns([4, 1])

with col_map:
    st.subheader(
        f"🗺️ Commune : {commune_selected}"
        if idse_selected == "No filtre"
        else f"🗺️ IDSE {idse_selected}"
    )
    st_folium(m, width=550, height=400)

# -----------------------------
# Footer
# -----------------------------
st.markdown("""
**Projet : Actualisation de la cartographie du RGPH5 (AC-RGPH5) – Mali**  
Développé avec Streamlit sous Python par **CAMARA, PhD** • © 2025
""")


