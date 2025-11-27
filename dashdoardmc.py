import streamlit as st
import folium
from streamlit_folium import st_folium
from shapely.geometry import Point
import geopandas as gpd

st.set_page_config(page_title="My Position Map", layout="wide")

st.title("📍 Real-Time Position on Map")

st.info("Click the button below to get your GPS location. This works on ANY Android device if you share the link.")

# -----------------------------
# Get Location from Browser
# -----------------------------

location = st.experimental_get_query_params()

lat = None
lon = None

# Button to request location
getloc = st.button("📍 Get My Position")

# Inject Javascript to request GPS coordinates
if getloc:
    st.markdown(
        """
        <script>
        navigator.geolocation.getCurrentPosition(
            function(pos) {
                const lat = pos.coords.latitude;
                const lon = pos.coords.longitude;
                const url = new URL(window.location.href);
                url.searchParams.set("lat", lat);
                url.searchParams.set("lon", lon);
                window.location.href = url.toString();
            },
            function(err) {
                alert("Location permission denied or unavailable.");
            },
            { enableHighAccuracy: true }
        );
        </script>
        """,
        unsafe_allow_html=True
    )

# Extract coordinates from URL
if "lat" in location and "lon" in location:
    lat = float(location["lat"][0])
    lon = float(location["lon"][0])


# -----------------------------
# Folium Map
# -----------------------------
if lat and lon:
    st.success(f"Your position: {lat}, {lon}")

    m = folium.Map(location=[lat, lon], zoom_start=15)

    # Add marker for user's position
    folium.Marker(
        [lat, lon],
        popup="📍 You are here",
        tooltip="Current Location",
        icon=folium.Icon(color="blue", icon="info-sign")
    ).add_to(m)

    st_folium(m, width=900, height=600)

else:
    st.warning("Click the button above to display your position on the map.")
