import streamlit as st
import geopandas as gpd
import pydeck as pdk
import zipfile
import tempfile
import os
import shutil

st.set_page_config(page_title="SHP Poligona Vizualizācija", layout="wide")

st.title("SHP Poligona Vizualizācija Kartē")

st.markdown("""
Šī lietotne ļauj jums augšupielādēt SHP (Shapefile) ZIP arhīvu un vizualizēt poligonus interaktīvā kartē.
**Piezīme:** Augšupielādējiet ZIP failu, kas satur visus nepieciešamos Shapefile komponentus (.shp, .shx, .dbf utt.).
""")

uploaded_file = st.file_uploader("Augšupielādējiet SHP ZIP arhīvu", type=["zip"])

if uploaded_file is not None:
    with tempfile.TemporaryDirectory() as tmpdirname:
        # Saglabājam augšupielādēto ZIP failu pagaidu direktorijā
        zip_path = os.path.join(tmpdirname, "uploaded_shp.zip")
        with open(zip_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        # Izvelkam ZIP saturu
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(tmpdirname)
        
        # Meklējam .shp failu pagaidu direktorijā
        shp_files = [file for file in os.listdir(tmpdirname) if file.endswith(".shp")]
        
        if not shp_files:
            st.error("ZIP arhīvā nav atrasts .shp fails. Lūdzu, pārbaudiet arhīvu un mēģiniet vēlreiz.")
        else:
            shp_path = os.path.join(tmpdirname, shp_files[0])
            
            try:
                # Nolasīt shapefile ar geopandas
                gdf = gpd.read_file(shp_path)
                
                if gdf.empty:
                    st.warning("Shapefile nav saturis datus.")
                else:
                    # Pārliecināties, ka koordinātu sistēma ir WGS84
                    if gdf.crs != "EPSG:4326":
                        gdf = gdf.to_crs(epsg=4326)
                    
                    # Izvilkt centroidu, lai noteiktu sākuma skatījumu
                    centroid = gdf.geometry.centroid.iloc[0]
                    view_state = pdk.ViewState(
                        longitude=centroid.x,
                        latitude=centroid.y,
                        zoom=10,
                        pitch=0,
                    )
                    
                    # Definēt slāni ar GeoJSON datiem
                    polygon_layer = pdk.Layer(
                        "GeoJsonLayer",
                        data=gdf.to_json(),
                        stroked=True,
                        filled=True,
                        get_fill_color=[0, 128, 255, 100],
                        get_line_color=[0, 0, 0],
                        line_width_min_pixels=2,
                    )
                    
                    # Izveidot Deck.gl karti
                    r = pdk.Deck(
                        layers=[polygon_layer],
                        initial_view_state=view_state,
                        tooltip={"text": "Poligons"},
                    )
                    
                    st.pydeck_chart(r)
            except Exception as e:
                st.error(f"Kļūda lasot SHP failu: {e}")
