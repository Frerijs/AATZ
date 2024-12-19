import streamlit as st
import geopandas as gpd
import pydeck as pdk
import zipfile
import tempfile
import os
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="SHP Poligona Vizualizācija", layout="wide")

st.title("SHP Poligona Vizualizācija Kartē")

st.markdown("""
Šī lietotne ļauj jums augšupielādēt SHP (Shapefile) ZIP arhīvu un vizualizēt poligonus interaktīvā kartē.
**Piezīme:** Augšupielādējiet ZIP failu, kas satur visus nepieciešamos Shapefile komponentus (.shp, .shx, .dbf utt.).
""")

uploaded_file = st.file_uploader("Augšupielādējiet SHP ZIP arhīvu", type=["zip"])

if uploaded_file is not None:
    with tempfile.TemporaryDirectory() as tmpdirname:
        st.write(f"Pagaidu direktorija: {tmpdirname}")
        # Saglabājam augšupielādēto ZIP failu pagaidu direktorijā
        zip_path = os.path.join(tmpdirname, "uploaded_shp.zip")
        with open(zip_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        st.success("ZIP arhīvs veiksmīgi augšupielādēts un saglabāts.")

        # Izvelkam ZIP saturu
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(tmpdirname)
            st.success("ZIP arhīvs veiksmīgi izvilkts.")
        except zipfile.BadZipFile:
            st.error("Nederīgs ZIP arhīvs. Lūdzu, pārliecinieties, ka augšupielādējat derīgu ZIP failu.")
            st.stop()
        
        # Meklējam .shp failu pagaidu direktorijā
        shp_files = [file for file in os.listdir(tmpdirname) if file.endswith(".shp")]
        
        if not shp_files:
            st.error("ZIP arhīvā nav atrasts .shp fails. Lūdzu, pārbaudiet arhīvu un mēģiniet vēlreiz.")
            st.stop()
        else:
            if len(shp_files) > 1:
                shp_file = st.selectbox("Izvēlieties SHP failu:", shp_files)
            else:
                shp_file = shp_files[0]
            
            shp_path = os.path.join(tmpdirname, shp_file)
            st.write(f"Atrodamais SHP fails: {shp_path}")
            
            # Pārbaudām, vai visi nepieciešamie faili eksistē
            required_extensions = ['.shp', '.shx', '.dbf']
            missing_files = []
            for ext in required_extensions:
                file = os.path.splitext(shp_file)[0] + ext
                if not os.path.exists(os.path.join(tmpdirname, file)):
                    missing_files.append(file)
            if missing_files:
                st.error(f"Trūkst nepieciešamie faili: {', '.join(missing_files)}. Lūdzu, pārbaudiet ZIP arhīvu.")
                st.stop()
            else:
                st.success("Visi nepieciešamie faili ir atrasti.")
            
            try:
                # Nolasīt shapefile ar geopandas
                gdf = gpd.read_file(shp_path)
                st.write("GeoDataFrame satur:")
                st.write(gdf.head())
                
                if gdf.empty:
                    st.warning("Shapefile nav saturis datus.")
                else:
                    # Pārbaudām oriģinālo CRS
                    st.write(f"Oriģinālā CRS: {gdf.crs}")
                    
                    # Pārbaudām, vai CRS ir EPSG:3059
                    if gdf.crs.to_string() != "EPSG:3059":
                        st.warning(f"Koordinātu sistēma nav EPSG:3059. Jūsu koordinātu sistēma ir {gdf.crs}.")
                    
                    # Pārliecināties, ka koordinātu sistēma tiek pareizi pārveidota uz WGS84 (EPSG:4326)
                    try:
                        gdf = gdf.to_crs(epsg=4326)
                        st.success("Koordinātu sistēma pārveidota uz WGS84 (EPSG:4326).")
                        st.write(f"Jaunā CRS: {gdf.crs}")
                    except Exception as e:
                        st.error(f"Kļūda pārveidojot CRS: {e}")
                        st.stop()
                    
                    # Pārbaudām, vai ģeometrija ir pareiza
                    if gdf.geometry.is_empty.all():
                        st.error("Visas ģeometrijas ir tukšas. Lūdzu, pārbaudiet SHP failu.")
                        st.stop()
                    
                    # Izvilkt centroidu, lai noteiktu sākuma skatījumu
                    centroid = gdf.geometry.centroid.iloc[0]
                    st.write(f"Poligona centroids: ({centroid.x}, {centroid.y})")
                    
                    # Izveidojiet Folium karti
                    m = folium.Map(location=[centroid.y, centroid.x], zoom_start=10)
                    
                    folium.GeoJson(
                        gdf,
                        name="Poligoni",
                        style_function=lambda feature: {
                            'fillColor': '#007BFF',
                            'color': 'black',
                            'weight': 2,
                            'fillOpacity': 0.5,
                        }
                    ).add_to(m)
                    
                    folium.LayerControl().add_to(m)
                    
                    st_folium(m, width=700, height=500)
                    
            except Exception as e:
                st.error(f"Kļūda lasot SHP failu: {e}")
