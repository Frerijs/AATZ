import streamlit as st
import geopandas as gpd
import zipfile
import tempfile
import os
import folium
from streamlit_folium import st_folium
from shapely.geometry import Point
import numpy as np

def generate_grid_points(polygon, spacing=5):
    """
    Ģenerē punktus poligona iekšpusē ar noteiktu attālumu starp tiem.

    Args:
        polygon (shapely.geometry.Polygon): Poligons, iekšā kurā ģenerēt punktus.
        spacing (float): Attālums starp punktiem metriem.

    Returns:
        list of shapely.geometry.Point: Saraksts ar ģenerētajiem punktiem.
    """
    minx, miny, maxx, maxy = polygon.bounds
    x_coords = np.arange(minx, maxx, spacing)
    y_coords = np.arange(miny, maxy, spacing)
    grid_points = [Point(x, y) for x in x_coords for y in y_coords if polygon.contains(Point(x, y))]
    return grid_points

st.set_page_config(page_title="SHP Poligona Vizualizācija ar Punktiem", layout="wide")

st.title("SHP Poligona Vizualizācija Kartē ar Punktiem")

st.markdown("""
Šī lietotne ļauj jums augšupielādēt SHP (Shapefile) ZIP arhīvu, vizualizēt poligonus interaktīvā kartē un ģenerēt punktus poligona iekšpusē ar maksimālu attālumu starp tiem 5 metri.
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
                    
                    # Ģenerējam punktus poligona iekšpusē
                    st.subheader("Ģenerētie punkti poligona iekšpusē")
                    
                    # Pārvēršam atpakaļ uz EPSG:3059, lai ģenerētu punktus precīzi metriskajā sistēmā
                    gdf_epsg3059 = gdf.to_crs(epsg=3059)
                    
                    all_points = []
                    for idx, row in gdf_epsg3059.iterrows():
                        geometry = row['geometry']
                        if geometry.type == 'Polygon':
                            points = generate_grid_points(geometry, spacing=5)
                            all_points.extend(points)
                        elif geometry.type == 'MultiPolygon':
                            for poly in geometry:
                                points = generate_grid_points(poly, spacing=5)
                                all_points.extend(points)
                    
                    if not all_points:
                        st.warning("Neizdevās ģenerēt punktus no SHP faila.")
                    else:
                        # Izveidojam GeoDataFrame ar punktiem
                        points_gdf = gpd.GeoDataFrame(geometry=all_points, crs="EPSG:3059")
                        
                        # Pārvēršam punktus uz EPSG:4326
                        points_gdf = points_gdf.to_crs(epsg=4326)
                        
                        st.write(f"Ģenerēto punktu skaits: {len(points_gdf)}")
                        st.write(points_gdf.head())
                        
                        # Izveidojiet Folium karti
                        # Izmantojam vidējo poligona centru kā kartes centru
                        centroid = gdf.geometry.centroid.unary_union
                        m = folium.Map(location=[centroid.y, centroid.x], zoom_start=14)
                        
                        # Pievienojam poligonu
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
                        
                        # Pievienojam punktus
                        folium.GeoJson(
                            points_gdf,
                            name="Punkti",
                            marker=folium.CircleMarker(
                                radius=2,
                                color='red',
                                fill=True,
                                fill_color='red'
                            ),
                            style_function=lambda feature: {
                                'radius': 2,
                                'color': 'red',
                                'fillColor': 'red',
                                'fillOpacity': 0.7,
                                'weight': 1,
                            }
                        ).add_to(m)
                        
                        folium.LayerControl().add_to(m)
                        
                        st_folium(m, width=700, height=500)
                        
            except Exception as e:
                st.error(f"Kļūda lasot SHP failu: {e}")
