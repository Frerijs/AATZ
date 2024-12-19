import streamlit as st
import geopandas as gpd
import tempfile
import zipfile
import io

st.title("Shapefile augšupielāde un vizualizācija")

uploaded_file = st.file_uploader("Augšupielādē Shapefile ZIP arhīvu", type=["zip"])

if uploaded_file is not None:
    # Izveidojam pagaidu direktoriju failu izsaiņošanai
    with tempfile.TemporaryDirectory() as tmpdir:
        # Izsaiņojam ZIP saturu
        with zipfile.ZipFile(uploaded_file, "r") as z:
            z.extractall(tmpdir)
        
        # Meklējam shp failu
        import os
        shp_files = [f for f in os.listdir(tmpdir) if f.endswith('.shp')]
        
        if len(shp_files) == 0:
            st.error("ZIP arhīvā nav atrasts .shp fails.")
        else:
            shp_path = os.path.join(tmpdir, shp_files[0])
            gdf = gpd.read_file(shp_path)
            
            st.write("Shapefile ielādēts veiksmīgi!")
            st.write(gdf.head())

            # Ja vēlies parādīt kartē (izmantojot st_folium vai citu risinājumu):
            # Piem., izmanto folium vizualizācijai
            import folium
            from streamlit_folium import st_folium

            center = [gdf.geometry.iloc[0].centroid.y, gdf.geometry.iloc[0].centroid.x]
            m = folium.Map(location=center, zoom_start=12)
            folium.GeoJson(gdf.to_crs("EPSG:4326")).add_to(m)

            st_map = st_folium(m, width=700, height=500)
