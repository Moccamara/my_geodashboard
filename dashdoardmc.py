import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from pathlib import Path
import pandas as pd
from shapely.geometry import Point
# ---------------------------------------------------------
# 🔐 PASSWORD AUTHENTICATION
# ---------------------------------------------------------
if "auth_ok" not in st.session_state:
    st.session_state.auth_ok = False
# Try to get password from secrets, fallback to default
try:
    PASSWORD = st.secrets["auth"]["dashboard_password"]
except Exception:
    PASSWORD = "instat2025"
if not st.session_state.auth_ok:
    with st.sidebar:
        st.header("🔐 Secure Access Required")
        pwd = st.text_input("Enter Password:", type="password")
        login_btn = st.button("Login")
        if login_btn:
            if pwd == PASSWORD:
                st.session_state.auth_ok = True
                st.rerun()  # hide password box after login
            else:
                st.error("❌ Incorrect Password")
    st.stop()
# ---------------------------------------------------------
# FRONT-END PROTECTION
# ---------------------------------------------------------
st.markdown("""
<style>
* { -webkit-user-select: none; user-select: none; }
body { -webkit-touch-callout: none; }
</style>
<script>
// Block right-click + shortcuts
document.addEventListener('contextmenu', event => event.preventDefault());
document.addEventListener('keydown', function(e) {
    if (e.ctrlKey && (e.key === 'p' || e.key === 's' || e.key === 'u')) e.preventDefault();
});
document.addEventListener('keyup', e => { if(e.key=='PrintScreen'){alert("Screenshots disabled");} });
// ======= RECEIVE GPS FROM ANDROID APP =======
window.addEventListener("message", (event) => {
    if (event.data.type === "gps_position") {
        const lat = event.data.lat;
        const lon = event.data.lon;
        window.parent.postMessage(
            {type: "streamlit:run", data: {lat: lat, lon: lon}},
            "*"
        );
    }
});
</script>
""", unsafe_allow_html=True)
# ---------------------------------------------------------
# RECEIVE USER POSITION FROM ANDROID WEBVIEW
# ---------------------------------------------------------
gps_data = st.experimental_get_query_params()

if "lat" in gps_data and "lon" in gps_data:
    st.session_state.user_lat = float(gps_data["lat"][0])
    st.session_state.user_lon = float(gps_data["lon"][0])
# ---------------------------------------------------------
# MAIN DASHBOARD
# ---------------------------------------------------------
st.title("**RGPH5 Census Update**")
# -----------------------------
# Folder containing GeoJSON/Shapefile
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
rename_map = {"lregion": "region", "lcercle": "cercle", "lcommune": "commune", "idse_new": "idse_new"}
gdf = gdf.rename(columns=rename_map)
gdf = gdf.to_crs(epsg=4326)
gdf = gdf[gdf.is_valid & ~gdf.is_empty]
# -----------------------------
# Sidebar + Logo
# -----------------------------
logo_path = Path("images/logo_wgv.png")
with st.sidebar:
    st.image(logo_path, width=150)
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
# Map
# -----------------------------
minx, miny, maxx, maxy = gdf_idse.total_bounds
center_lat = (miny + maxy) / 2
center_lon = (minx + maxx) / 2
m = folium.Map(location=[center_lat, center_lon], zoom_start=19, tiles="OpenStreetMap")
m.fit_bounds([[miny, minx], [maxy, maxx]])
folium.GeoJson(
    gdf_idse,
    name="IDSE Layer",
    style_function=lambda x: {"fillOpacity": 0, "color": "blue", "weight": 2},
    tooltip=folium.GeoJsonTooltip(fields=["idse_new", "pop_se", "pop_se_ct"], localize=True),
    popup=folium.GeoJsonPopup(fields=["idse_new", "pop_se", "pop_se_ct"], localize=True)
).add_to(m)
# -----------------------------
# Add USER GPS Location Marker
# -----------------------------
if "user_lat" in st.session_state:
    folium.Marker(
        [st.session_state.user_lat, st.session_state.user_lon],
        tooltip="📍 Votre position GPS",
        icon=folium.Icon(color="red", icon="glyphicon glyphicon-user")
    ).add_to(m)
# -----------------------------
# CSV from server path
# -----------------------------
csv_folder = Path("data")
csv_file_name = "Denombrement-B_DENOMBREMENT.csv"
csv_path = csv_folder / csv_file_name
points_gdf = None
if csv_path.exists():
    df_csv = pd.read_csv(csv_path)
    df_csv = df_csv.dropna(subset=["LAT", "LON"])
    points_gdf = gpd.GeoDataFrame(
        df_csv,
        geometry=gpd.points_from_xy(df_csv["LON"], df_csv["LAT"]),
        crs="EPSG:4326"
    )
if points_gdf is not None:
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






