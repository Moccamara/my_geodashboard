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

# -----------------------------
# App title
# -----------------------------
APP_TITLE = '**RGPH5 Census Update**'
st.title(APP_TITLE)

# -----------------------------
# Folder containing GeoJSON/Shapefile
# -----------------------------
FOLDER_PATH = r"D:\Web_Mapping\geo_env\data"
folder = Path(FOLDER_PATH)

# Find first .geojson or .shp file
geo_file = next((f for f in folder.glob("*.geojson")), None)
if not geo_file:
    geo_file = next((f for f in folder.glob("*.shp")), None)
if not geo_file:
    st.error("Aucun fichier GeoJSON ou Shapefile trouvé dans le dossier.")
    st.stop()

# Load GeoJSON
gdf = gpd.read_file(geo_file)
gdf.columns = gdf.columns.str.lower().str.strip()

# -----------------------------
# Rename columns
# -----------------------------
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
with st.sidebar:
    st.image(r"D:\Web_Mapping\geo_env\instat_logo.png", width=120)
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

# Filter GeoJSON by IDSE_NEW
gdf_idse = gdf_commune.copy()
if idse_selected != "No filtre":
    gdf_idse = gdf_commune[gdf_commune["idse_new"] == idse_selected]

# Create missing pop columns if needed
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

# SE Polygon layer
folium.GeoJson(
    gdf_idse,
    name="IDSE Layer",
    style_function=lambda x: {"fillOpacity": 0, "color": "blue", "weight": 2},
    tooltip=folium.GeoJsonTooltip(fields=["idse_new", "pop_se", "pop_se_ct"], localize=True, sticky=True),
    popup=folium.GeoJsonPopup(fields=["idse_new", "pop_se", "pop_se_ct"], localize=True)
).add_to(m)

# -----------------------------
# Upload CSV Points (LAT, LON, Masculin, Feminin)
# -----------------------------
st.sidebar.markdown("### Import CSV Points")
csv_file = st.sidebar.file_uploader(
    "Upload CSV",
    type=["csv"],
    key="csv_points_uploader"
)

points_gdf = None
if csv_file:
    try:
        df_csv = pd.read_csv(csv_file)
        lat_col = "LAT"
        lon_col = "LON"

        df_csv = df_csv.dropna(subset=[lat_col, lon_col])

        if not df_csv.empty:
            points_gdf = gpd.GeoDataFrame(
                df_csv,
                geometry=gpd.points_from_xy(df_csv[lon_col], df_csv[lat_col]),
                crs="EPSG:4326"
            )
    except Exception as e:
        st.sidebar.error(f"Error loading CSV: {e}")

# Add CSV points to the map
if points_gdf is not None and not points_gdf.empty:
    for _, row in points_gdf.iterrows():
        if pd.notna(row.geometry.x) and pd.notna(row.geometry.y):
            folium.CircleMarker(
                location=[row.geometry.y, row.geometry.x],
                radius=2,
                color="red",
                fill=True,
                fill_opacity=0.8
            ).add_to(m)

# -----------------------------
# Layout: Map left & Chart right
# -----------------------------
col_map, col_chart = st.columns([4, 1])

with col_map:
    st.subheader(
        f"🗺️ Commune : {commune_selected}"
        if idse_selected == "No filtre"
        else f"🗺️ IDSE {idse_selected}"
    )
    st_folium(m, width=530, height=350)

with col_chart:
    # ---------------------------
    # Bar Chart (GeoJSON)
    # ---------------------------
    if idse_selected == "No filter":
        st.info("Select SE.")
    else:
        st.subheader("📊")

        # Prepare data
        df_geo_stats = gdf_idse[["idse_new", "pop_se", "pop_se_ct"]].copy()
        df_geo_stats["idse_new"] = df_geo_stats["idse_new"].astype(str)

        # Melt to long format
        df_long = df_geo_stats.melt(
            id_vars="idse_new",
            value_vars=["pop_se", "pop_se_ct"],
            var_name="Variable",
            value_name="Population"
        )

        df_long["Variable"] = df_long["Variable"].replace({
            "pop_se": "Pop SE",
            "pop_se_ct": "Pop Actu"
        })

        # Bar chart with legend visible
        chart = (
            alt.Chart(df_long)
            .mark_bar()
            .encode(
                x=alt.X(
                    "idse_new:N",
                    title=None,
                    axis=alt.Axis(
                        labelAngle=0,
                        labelFontSize=10,
                        ticks=False
                    )
                ),
                xOffset="Variable:N",      # Bars side-by-side
                y=alt.Y("Population:Q", title=None),
                color=alt.Color(
                    "Variable:N",
                    title="Type",            # Name of legend
                    legend=alt.Legend(
                        orient="right",
                        labelFontSize=10,
                        titleFontSize=10,
                        padding=0
                    )
                ),
                tooltip=["idse_new", "Variable", "Population"]
            )
            .properties(width=80, height=120)
        )

        st.altair_chart(chart, use_container_width=True)

        # ---------------------------
        # Pie Chart (CSV: Masculin / Feminin)
        # ---------------------------
        st.subheader("Sex(M.F)")

        if points_gdf is None:
            st.warning("Select CSV file.")
        else:
            try:
                points_inside = gpd.sjoin(
                    points_gdf,
                    gdf_idse[["idse_new", "geometry"]],
                    predicate="within",
                    how="inner"
                )

                if points_inside.empty:
                    st.warning("NO SE selected.")
                else:
                    if not all(col in points_inside.columns for col in ["Masculin", "Feminin"]):
                        st.error("Le CSV doit contenir les colonnes: Masculin, Feminin")
                    else:
                        total_masculin = int(points_inside["Masculin"].sum())
                        total_feminin = int(points_inside["Feminin"].sum())
                        total_population = total_masculin + total_feminin

                        labels = ["M", "F"]
                        values = [total_masculin, total_feminin]

                        fig, ax = plt.subplots(figsize=(3.5, 3.5))
                        wedges, texts, autotexts = ax.pie(
                            values,
                            labels=labels,
                            autopct=lambda pct: f"{pct:.1f}%" if pct > 0 else "",
                            textprops={'color': 'white', 'fontsize': 14}
                        )
                        
                        st.pyplot(fig)

                        st.markdown(f"""
                       
                        - 👨 M: **{total_masculin}**
                        - 👩 F: **{total_feminin}**
                        - 👥 Pop: **{total_population}**
                        """)

            except Exception as e:
                st.error(f"Erreur lors du pie chart : {e}")

# -----------------------------
# QGIS Button - Save selection
# -----------------------------
QGIS_PROJECT = r"D:\Web_Mapping\geo_env\qgis_project\project.qgz"
SE_FILE = r"D:\Web_Mapping\geo_env\qgis_project\se_selected\selected_se.json"

if st.button("🟢 Ouvrir dans QGIS"):
    try:
        selected_info = {
            "region": region_selected,
            "cercle": cercle_selected,
            "commune": commune_selected,
            "idse_new": idse_selected
        }

        os.makedirs(os.path.dirname(SE_FILE), exist_ok=True)

        with open(SE_FILE, "w", encoding="utf-8") as f:
            json.dump(selected_info, f, ensure_ascii=False, indent=4)

        os.startfile(QGIS_PROJECT)
        st.success("Projet QGIS ouvert et sélection envoyée ✔")

    except Exception as e:
        st.error(f"Erreur : {e}")

# -----------------------------
# Footer
# -----------------------------
st.markdown("""
**Projet : Actualisation de la cartographie du RGPG5 (AC-RGPH5) – Mali**  
Développé avec Streamlit sous Python par **CAMARA, PhD** • © 2025
""")
