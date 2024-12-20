import geopandas as gpd
from shapely.geometry import Point
import os
import pandas as pd
import math
import warnings
from tqdm import tqdm
import laspy
import numpy as np
from scipy.spatial import cKDTree
import streamlit as st
import zipfile
import io
import requests
import datetime
from zoneinfo import ZoneInfo

# Ignorē Shapely runtime brīdinājumus, lai netraucētu skripta darbību
warnings.filterwarnings("ignore", category=RuntimeWarning)

# Supabase konfigurācija (Aizvietojiet ar savu Supabase URL un atslēgu)
supabase_url = "https://uhwbflqdripatfpbbetf.supabase.co"
supabase_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVod2JmbHFkcmlwYXRmcGJiZXRmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTczMDcxODE2MywiZXhwIjoyMDQ2Mjk0MTYzfQ.78wsNZ4KBg2l6zeZ1ZknBBooe0PeLtJzRU-7eXo3WTk"  # Aizvietojiet ar savu Supabase atslēgu

# Konstantas
APP_NAME = "LAS Punktu Filtrēšanas Aplikācija"
APP_VERSION = "1.0"
APP_TYPE = "web"

def authenticate(username, password):
    """
    Autentificē lietotāju, nosūtot pieprasījumu uz Supabase.
    """
    try:
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        }
        url = f"{SUPABASE_URL}/rest/v1/users"
        params = {
            "select": "*",
            "username": f"eq.{username}",
            "password": f"eq.{password}",
        }
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            if data:
                return True
            else:
                return False
        else:
            st.error(f"Kļūda autentificējot lietotāju: {response.status_code}")
            return False
    except Exception as e:
        st.error(f"Kļūda: {str(e)}")
        return False

def log_user_login(username):
    """
    Ieraksta lietotāja pieteikšanos Supabase datubāzē.
    """
    try:
        # Iegūstiet aktuālo laiku Latvijas laika zonā
        riga_tz = ZoneInfo('Europe/Riga')
        current_time = datetime.datetime.now(riga_tz).isoformat()

        # Sagatavojiet datu vārdnīcu ar pareiziem kolonnu nosaukumiem
        data = {
            "username": username,
            "App": APP_NAME,
            "Ver": APP_VERSION,
            "app_type": APP_TYPE,
            "login_time": current_time
        }

        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        url = f"{SUPABASE_URL}/rest/v1/user_data"

        response = requests.post(url, json=data, headers=headers)

        if response.status_code not in [200, 201]:
            st.error(f"Kļūda ierakstot datus: {response.status_code}, {response.text}")
    except Exception as e:
        st.error(f"Kļūda: {str(e)}")

def login():
    """
    Apstrādā lietotāja login pieprasījumu.
    """
    username = st.session_state.get('username', '').strip()
    password = st.session_state.get('password', '').strip()
    if not username or not password:
        st.error("Lūdzu, ievadiet gan lietotājvārdu, gan paroli.")
    else:
        if authenticate(username, password):
            st.session_state.logged_in = True
            st.session_state.username_logged = username
            log_user_login(username)
            st.success("Veiksmīgi pieteicies!")
        else:
            st.error("Nepareizs lietotājvārds vai parole.")

def show_login():
    """
    Parāda login formu lietotājam.
    """
    st.title("LAS Punktu Filtrēšanas Aplikācija")
    st.subheader("Pieteikties")
    with st.form(key='login_form'):
        username = st.text_input("Lietotājvārds", key='username')
        password = st.text_input("Parole", type="password", key='password')
        submit_button = st.form_submit_button(label="Pieslēgties", on_click=login)
    st.markdown("<div style='text-align: center; margin-top: 20px; color: gray;'>© 2024 METRUM</div>", unsafe_allow_html=True)

def load_polygons(shapefile_bytes, target_crs='EPSG:3059'):
    """
    Ielādē shapefile no bytes, validē poligonus un pārprojekcē uz mērķa CRS.
    """
    # Sagatavot shapefile no zip
    with zipfile.ZipFile(shapefile_bytes) as z:
        z.extractall("temp_shapefile")
    shapefile_path = [os.path.join("temp_shapefile", f) for f in os.listdir("temp_shapefile") if f.endswith('.shp')][0]

    gdf = gpd.read_file(shapefile_path)
    # Validē un izlabo poligonus, ja nepieciešams
    gdf['geometry'] = gdf['geometry'].apply(lambda geom: geom.buffer(0) if not geom.is_valid else geom)
    # Pārprojekcē uz mērķa CRS, lai nodrošinātu metriskas vienības
    gdf = gdf.to_crs(target_crs)
    return gdf

def load_lidar(las_file, target_crs='EPSG:3059'):
    """
    Ielādē Lidar datus no LAS faila, pārprojekcē uz mērķa CRS un atgriež kā GeoDataFrame.
    """
    st.write("Ielādē LAS datus...")
    las = laspy.read(las_file)
    points = np.vstack((las.x, las.y, las.z)).transpose()
    # Izveido GeoDataFrame ar LAS punktiem
    lidar_gdf = gpd.GeoDataFrame(
        {'x': points[:,0], 'y': points[:,1], 'z': points[:,2]},
        geometry=[Point(x, y) for x, y, z in points],
        crs='EPSG:3059'  # Pieņemot, ka LAS dati ir EPSG:3059
    )
    # Pārprojekcē, ja nepieciešams
    if lidar_gdf.crs != target_crs:
        st.write(f"Pārprojekcē LAS datus no {lidar_gdf.crs} uz {target_crs}...")
        lidar_gdf = lidar_gdf.to_crs(target_crs)
    else:
        st.write("LAS dati jau ir norādītajā CRS.")
    return lidar_gdf

def filter_points_within_polygons(lidar_gdf, polygons_gdf):
    """
    Atlasīt tikai tos LAS punktus, kas atrodas poligonos.
    """
    st.write("Atlasīt punktus, kas atrodas poligonos...")
    # Izmanto spatial join, lai atlasītu punktus, kas atrodas poligonos
    points_within = gpd.sjoin(lidar_gdf, polygons_gdf, how='inner', predicate='within')
    # Izņem neatbilstošos atribūtus, kas iegūti no spatial join
    points_within = points_within.drop(columns=['index_right'])
    st.write(f"Atlasīti {len(points_within)} punkti, kas atrodas poligonos.")
    return points_within

def select_points_with_constraints(points_gdf, min_distance=2, max_distance=7):
    """
    Atlasīt punktus, nodrošinot, ka:
    - Nav divu punktu, kuru attālums ir mazāks par min_distance.
    - Katram punktam ir vismaz viens cits punkts, kura attālums ir ne lielāks par max_distance.
    """
    st.write("Atlasīt punktus ar attāluma ierobežojumiem...")
    # Izvilkt koordinātes
    coords = np.array([(point.x, point.y) for point in points_gdf.geometry])
    num_points = coords.shape[0]
    tree = cKDTree(coords)

    # Shuffle point order
    indices = np.random.permutation(num_points)

    selected_indices = []
    selected_mask = np.zeros(num_points, dtype=bool)
    covered_mask = np.zeros(num_points, dtype=bool)

    st.write("Izvēlas punktus, saglabājot minimālo attālumu...")
    for idx in tqdm(indices, desc="Min distance selection"):
        if not covered_mask[idx]:
            # Atlasīt šo punktu
            selected_indices.append(idx)
            selected_mask[idx] = True
            # Atzīmēt visus punktus, kas ir mazāk par min_distance, kā segtus (nav izvēlēti)
            neighbors_min = tree.query_ball_point(coords[idx], r=min_distance)
            covered_mask[neighbors_min] = True

    # Tagad pārbaudīt katram atlasītajam punktam, vai tam ir vismaz viens cits punkts ar attālumu <= max_distance
    st.write("Pārbauda katru atlasīto punktu, vai tam ir vismaz viens cits punkts ar attālumu <= max_distance...")
    valid_selected = []
    selected_coords = coords[selected_indices]
    selected_tree = cKDTree(selected_coords)

    for i, coord in enumerate(tqdm(selected_coords, desc="Verifying max distance")):
        neighbors = selected_tree.query_ball_point(coord, r=max_distance)
        if len(neighbors) > 1:  # ir vismaz viens cits punkts
            valid_selected.append(selected_indices[i])

    # Izveido filtrēto GeoDataFrame
    filtered_gdf = points_gdf.iloc[valid_selected].copy()
    st.write(f"Atlasīti {len(filtered_gdf)} punkti, kas atbilst attāluma kritērijiem.")

    return filtered_gdf

def create_zip_from_gdf(gdf, filename='filtered_lidar_points'):
    """
    Izveido zip arhīvu no GeoDataFrame shapefile failiem.
    """
    # Saglabā shapefile uz disku
    shapefile_dir = f"temp_shapefile_{filename}"
    os.makedirs(shapefile_dir, exist_ok=True)
    shapefile_path = os.path.join(shapefile_dir, f"{filename}.shp")
    gdf.to_file(shapefile_path, driver='ESRI Shapefile')

    # Izveido zip arhīvu
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(shapefile_dir):
            for file in files:
                zf.write(os.path.join(root, file), arcname=file)
    zip_buffer.seek(0)

    # Tīra temporāros failus
    for file in os.listdir(shapefile_dir):
        os.remove(os.path.join(shapefile_dir, file))
    os.rmdir(shapefile_dir)

    return zip_buffer

def process_all_polygons(shapefile_bytes, las_file, output_dir, min_distance=2, max_distance=7):
    """
    Apstrādā poligonus un LAS datus, atlasot punktus ar attāluma ierobežojumiem,
    un saglabā rezultātus shapefile izvades mapē.
    """
    # Ielādē poligonus
    st.write("Ielādē poligonus...")
    polygons_gdf = load_polygons(shapefile_bytes)
    if polygons_gdf.empty:
        st.error("Shapefile ir tukšs vai nav atrasts.")
        return

    # Ielādē LAS datus
    st.write("Ielādē LAS datus...")
    lidar_gdf = load_lidar(las_file)

    # Atlasīt punktus, kas atrodas poligonos
    st.write("Atlasīt punktus, kas atrodas poligonos...")
    points_within = filter_points_within_polygons(lidar_gdf, polygons_gdf)
    if points_within.empty:
        st.warning("Nav punktu, kas atrodas poligonos.")
        return

    # Atlasīt punktus ar attāluma ierobežojumiem
    st.write(f"Atlasīt punktus ar attālumu no {min_distance} līdz {max_distance} metriem...")
    filtered_points = select_points_with_constraints(points_within, min_distance, max_distance)
    if filtered_points.empty:
        st.warning("Nav punktu, kas atbilst attāluma kritērijiem.")
        return

    # Saglabā filtrētos punktus kā shapefile ZIP
    zip_buffer = create_zip_from_gdf(filtered_points)

    # Piedāvā lejupielādi
    st.success("Filtrēšana pabeigta!")
    st.download_button(
        label="Lejupielādēt Filtrētos Punktus (ZIP)",
        data=zip_buffer,
        file_name="filtered_lidar_points.zip",
        mime="application/zip"
    )

def show_main_app():
    """
    Parāda galveno LAS punktu filtrēšanas aplikāciju.
    """
    st.title("LAS Punktu Filtrēšanas Aplikācija")
    st.write("Atlasiet LAS un poligonu shapefile failus, un norādiet attāluma ierobežojumus punktu filtrēšanai.")

    # Shapefile Augšupielāde
    st.header("1. Augšupielādēt Poligonu Shapefile (ZIP formātā)")
    shapefile = st.file_uploader("Izvēlieties shapefile (ZIP formātā)", type=["zip"])

    # LAS Faila Augšupielāde
    st.header("2. Augšupielādēt LAS Failu")
    las_file = st.file_uploader("Izvēlieties LAS failu", type=["las", "laz"])

    if shapefile and las_file:
        # Iegūst lietotāja ievadi par attāluma ierobežojumiem
        st.header("3. Norādīt Attāluma Ierobežojumus")
        min_distance = st.number_input("Minimālais attālums starp punktiem (metri):", min_value=0.1, value=2.0, step=0.1)
        max_distance = st.number_input("Maksimālais attālums starp punktiem (metri):", min_value=0.1, value=7.0, step=0.1)

        if min_distance > max_distance:
            st.error("Minimālais attālums nevar būt lielāks par maksimālo attālumu.")
        else:
            # Apstrādes Poga
            if st.button("Sākt Punktu Filtrēšanu"):
                with st.spinner("Apstrādā datus..."):
                    try:
                        # Apstrādā poligonus un LAS datus ar norādītajiem attāluma ierobežojumiem
                        process_all_polygons(shapefile, las_file, "out",
                                            min_distance=min_distance, max_distance=max_distance)
                    except Exception as e:
                        st.error(f"Kļūda apstrādājot datus: {e}")

def main():
    # Inicializējiet sesijas stāvokļa mainīgos, ja nepieciešams
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'username_logged' not in st.session_state:
        st.session_state.username_logged = ''

    if not st.session_state.logged_in:
        show_login()
    else:
        st.sidebar.header(f"Lietotājs: {st.session_state.username_logged}")
        if st.sidebar.button("Iziet"):
            st.session_state.logged_in = False
            st.session_state.username_logged = ''
            st.experimental_rerun()

        show_main_app()

if __name__ == "__main__":
    main()
