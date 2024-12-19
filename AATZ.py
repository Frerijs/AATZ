import streamlit as st
import geopandas as gpd
from shapely.ops import unary_union
import folium
from streamlit_folium import st_folium
import tempfile
import zipfile
import os

st.set_page_config(page_title="Shapefile vizualizācija", layout="wide")
st.title("Poligona un punktu vizualizācija ar 5m buffer")

st.write("Lūdzu augšuplādējiet poligona shapefile un punktu shapefile ZIP arhīvus.")

polygon_zip = st.file_uploader("Augšupielādē poligona Shapefile (ZIP)", type="zip")
points_zip = st.file_uploader("Augšupielādē punktu Shapefile (ZIP)", type="zip")

if polygon_zip is not None and points_zip is not None:
    # Izveidojam pagaidu direktorijas
    with tempfile.TemporaryDirectory() as polygon_dir, tempfile.TemporaryDirectory() as points_dir:
        # Izpakot poligona zip
        with zipfile.ZipFile(polygon_zip, 'r') as zip_ref:
            zip_ref.extractall(polygon_dir)
        
        # Izpakot punktu zip
        with zipfile.ZipFile(points_zip, 'r') as zip_ref:
            zip_ref.extractall(points_dir)
        
        # Atrodam .shp failus izpakotajās direktorijās
        def find_shapefile(directory):
            for file in os.listdir(directory):
                if file.endswith(".shp"):
                    return os.path.join(directory, file)
            return None
        
        polygon_path = find_shapefile(polygon_dir)
        points_path = find_shapefile(points_dir)

        if polygon_path is None or points_path is None:
            st.error("Neizdevās atrast .shp failus augšuplādētajos ZIP arhīvos.")
        else:
            # Ielādē shapefiles ar geopandas
            polygons = gpd.read_file(polygon_path)
            points = gpd.read_file(points_path)

            st.write("Oriģinālā poligona informācija:")
            st.write(polygons.head())
            st.write("Oriģinālā punktu informācija:")
            st.write(points.head())

            # Veidojam 5 metru buffer ap poligoniem
            polygon_union = unary_union(polygons.geometry)
            buffer_area = polygon_union.buffer(5)

            # Atlasām punktus, kas ir 5m buffer zonā
            points_within_5m = points[points.geometry.within(buffer_area)]

            st.write("Punkti, kas atrodas poligona 5m buffer zonā:")
            st.write(points_within_5m)

            # Izveidojam folium karti
            polygon_centroid = polygon_union.centroid
            m = folium.Map(location=[polygon_centroid.y, polygon_centroid.x], zoom_start=14)

            # Poligons
            folium.GeoJson(polygons, name="Polygon").add_to(m)

            # 5m buffer
            folium.GeoJson(buffer_area, name="5m Buffer", style_function=lambda x: {
                'fillColor': 'green',
                'color': 'green',
                'fillOpacity': 0.2
            }).add_to(m)

            # Punkti bufferī
            for idx, row in points_within_5m.iterrows():
                folium.Marker(
                    location=[row.geometry.y, row.geometry.x],
                    popup=str(row),
                    icon=folium.Icon(color='blue', icon='info-sign')
                ).add_to(m)

            folium.LayerControl().add_to(m)

            st_map = st_folium(m, width=800, height=600)
