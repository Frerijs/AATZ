import streamlit as st
import geopandas as gpd
import zipfile
import tempfile
import os
import folium
from streamlit_folium import st_folium
from shapely.geometry import Point, Polygon, MultiPolygon
import numpy as np
from folium.plugins import MarkerCluster
import pandas as pd
from io import BytesIO
import random

def generate_random_points_grid_based(polygon, grid_size=5):
    """
    Ģenerē nejaušus punktus poligona iekšpusē, izmantojot grīdas bāzētu metodi.
    Katras grīdas šūnas pārklājumā ar poligonu tiek ģenerēts viens nejaušs punkts.

    Args:
        polygon (shapely.geometry.Polygon or MultiPolygon): Poligons, iekšā kurā ģenerēt punktus.
        grid_size (float): Grīdas šūnas izmērs metriem.

    Returns:
        list of shapely.geometry.Point: Saraksts ar ģenerētajiem punktiem.
    """
    points = []
    if isinstance(polygon, Polygon):
        polygons = [polygon]
    elif isinstance(polygon, MultiPolygon):
        polygons = list(polygon)
    else:
        return points

    for poly in polygons:
        minx, miny, maxx, maxy = poly.bounds
        # Izveidojam grīdas šūnu koordinātas
        x_coords = np.arange(minx, maxx, grid_size)
        y_coords = np.arange(miny, maxy, grid_size)
        for x in x_coords:
            for y in y_coords:
                # Izveidojam grīdas šūnu kā poligonu
                grid_cell = Polygon([
                    (x, y),
                    (x + grid_size, y),
                    (x + grid_size, y + grid_size),
                    (x, y + grid_size)
                ])
                intersection = poly.intersection(grid_cell)
                if not intersection.is_empty:
                    # Ja šūna pārklājas ar poligonu, ģenerējam vienu nejaušu punktu šūnas pārklājumā
                    if isinstance(intersection, (Polygon, MultiPolygon)):
                        # Ja pārklājums ir poligons vai multipoligons, ģenerējam punktu
                        minx_i, miny_i, maxx_i, maxy_i = intersection.bounds
                        # Ja pārklājums ir MultiPolygon, izvēlamies vienu no tiem
                        if isinstance(intersection, MultiPolygon):
                            intersection = random.choice(list(intersection))
                            minx_i, miny_i, maxx_i, maxy_i = intersection.bounds
                        # Ģenerējam nejaušu punktu pārklājuma teritorijā
                        while True:
                            rand_x = random.uniform(minx_i, maxx_i)
                            rand_y = random.uniform(miny_i, maxy_i)
                            rand_point = Point(rand_x, rand_y)
                            if intersection.contains(rand_point):
                                points.append(rand_point)
                                break
    return points

def convert_gdf_to_csv(gdf):
    """
    Konvertē GeoDataFrame uz CSV formātu ar x, y, z koordinātēm.

    Args:
        gdf (geopandas.GeoDataFrame): GeoDataFrame ar punktiem.

    Returns:
        BytesIO: CSV datu plūsma.
    """
    # Izveidojam DataFrame ar x, y koordinātēm
    df = pd.DataFrame({
        'x': gdf.geometry.x,
        'y': gdf.geometry.y,
        'z': 0  # Pievienojam z koordinātu (piemēram, 0)
    })
    csv_buffer = BytesIO()
    df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)
    return csv_buffer

st.set_page_config(page_title="SHP Poligona Vizualizācija ar Punktiem", layout="wide")

st.title("SHP Poligona Vizualizācija Kartē ar Punktiem")
st.markdown("""
Šī lietotne ļauj jums augšupielādēt SHP (Shapefile) ZIP arhīvu, vizualizēt poligonus interaktīvā kartē un ģenerēt nejaušus punktus poligona iekšpusē ar maksimālu attālumu starp tiem 5 metri.
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
                        gdf_wgs84 = gdf.to_crs(epsg=4326)
                        st.success("Koordinātu sistēma pārveidota uz WGS84 (EPSG:4326).")
                        st.write(f"Jaunā CRS: {gdf_wgs84.crs}")
                    except Exception as e:
                        st.error(f"Kļūda pārveidojot CRS: {e}")
                        st.stop()

                    # Pārbaudām, vai ģeometrija ir pareiza
                    if gdf_wgs84.geometry.is_empty.all():
                        st.error("Visas ģeometrijas ir tukšas. Lūdzu, pārbaudiet SHP failu.")
                        st.stop()

                    # Ģenerējam punktus poligona iekšpusē
                    st.subheader("Ģenerētie punkti poligona iekšpusē")

                    # Pārvēršam atpakaļ uz EPSG:3059, lai ģenerētu punktus precīzi metriskajā sistēmā
                    gdf_epsg3059 = gdf.to_crs(epsg=3059)

                    all_points = []
                    for idx, row in gdf_epsg3059.iterrows():
                        geometry = row['geometry']
                        if geometry.type == 'Polygon' or geometry.type == 'MultiPolygon':
                            points = generate_random_points_grid_based(geometry, grid_size=5)
                            all_points.extend(points)

                    if not all_points:
                        st.warning("Neizdevās ģenerēt punktus no SHP faila.")
                    else:
                        # Izveidojam GeoDataFrame ar punktiem EPSG:3059
                        points_gdf_3059 = gpd.GeoDataFrame(geometry=all_points, crs="EPSG:3059")

                        # Pārvēršam punktus uz EPSG:4326
                        points_gdf_4326 = points_gdf_3059.to_crs(epsg=4326)

                        st.write(f"Ģenerēto punktu skaits: {len(points_gdf_3059)}")
                        st.write(points_gdf_3059.head())

                        # Izveidojiet Folium karti
                        # Izmantojam poligona kopējo robežu, lai noteiktu kartes centru
                        minx, miny, maxx, maxy = gdf_wgs84.total_bounds
                        center_x = (minx + maxx) / 2
                        center_y = (miny + maxy) / 2
                        m = folium.Map(location=[center_y, center_x], zoom_start=14)

                        # Pievienojam poligonu
                        folium.GeoJson(
                            gdf_wgs84,
                            name="Poligoni",
                            style_function=lambda feature: {
                                'fillColor': '#007BFF',
                                'color': 'black',
                                'weight': 2,
                                'fillOpacity': 0.5,
                            }
                        ).add_to(m)

                        # Pievienojam punktus ar MarkerCluster
                        marker_cluster = MarkerCluster(name="Punkti").add_to(m)

                        for _, point in points_gdf_4326.iterrows():
                            folium.CircleMarker(
                                location=[point.geometry.y, point.geometry.x],
                                radius=2,
                                color='red',
                                fill=True,
                                fill_color='red',
                                fill_opacity=0.7,
                                weight=1
                            ).add_to(marker_cluster)

                        folium.LayerControl().add_to(m)

                        # Pievienojam karti Streamlit interfeisam
                        st_folium(m, width=700, height=500)

                        # Pievienojam lejupielādes pogu
                        st.subheader("Lejupielādēt ģenerētos punktus")
                        csv_buffer = convert_gdf_to_csv(points_gdf_3059)
                        st.download_button(
                            label="Lejupielādēt Punktus kā CSV",
                            data=csv_buffer,
                            file_name="punkti.csv",
                            mime="text/csv"
                        )

            except Exception as e:
                st.error(f"Kļūda lasot SHP failu: {e}")
