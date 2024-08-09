import geopandas as gpd
from shapely.ops import unary_union
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def interseccion2020(gdf_1990, gdf_2020):
    """
    Filtra y devuelve las geometrías de un GeoDataFrame del año 2020 que intersectan con un conjunto de geometrías de 1990.

    Esta función toma dos GeoDataFrames, uno con geometrías de 1990 y otro con geometrías de 2020, y devuelve un nuevo GeoDataFrame
    que contiene únicamente las geometrías de 2020 que intersectan con las geometrías de 1990.

    Parameters:
    gdf_1990 : GeoDataFrame
        Un GeoDataFrame que contiene las geometrías de 1990.

    gdf_2020 : GeoDataFrame
        Un GeoDataFrame que contiene las geometrías de 2020.

    Returns:
    GeoDataFrame
        Un GeoDataFrame con las geometrías de 2020 que intersectan con las geometrías de 1990.

    """
    inter = gdf_2020[gdf_2020.intersects(gdf_1990.unary_union)]
    inter.reset_index(inplace = True)
    return inter


def combinaciones_vecinos(gdf_interseccion2020):
    """
    Genera combinaciones de polígonos vecinos a partir de un GeoDataFrame.

    Parameters:
    gdf_interseccion2020 (GeoDataFrame): GeoDataFrame con las geometrías de los polígonos.

    Returns:
    GeoDataFrame: Nuevo GeoDataFrame con combinaciones de polígonos vecinos.

    Este proceso se realiza en los siguientes pasos:
    1. Se copia el GeoDataFrame original y se asigna un identificador único a cada fila.
    2. Se determinan los vecinos de cada polígono, es decir, aquellos que tocan su geometría.
    3. Se define una función interna `combinar_vecinos` que toma un DataFrame y el GeoDataFrame original para combinar los polígonos vecinos y crear nuevas geometrías.
    4. Se inicializa un nuevo GeoDataFrame con las combinaciones de vecinos.
    5. Se actualizan los identificadores y se recalculan los vecinos.
    6. Se devuelven las combinaciones de polígonos vecinos en un nuevo GeoDataFrame.
    """
    gdf = gdf_interseccion2020.copy()

    # Determinar los vecinos
    gdf['id'] = range(len(gdf))
    gdf['neighbors'] = gdf.apply(lambda row: gdf[gdf.geometry.touches(row['geometry'])]['id'].tolist(), axis=1)

    # Función para combinar vecinos
    def combinar_vecinos(df, gdf_original):
    """
    Combina las geometrías vecinas en un GeoDataFrame y genera nuevas combinaciones.

    Esta función itera sobre un GeoDataFrame y, para cada geometría, combina sus vecinos adyacentes para crear nuevas geometrías. 
    Las nuevas geometrías son la unión de las geometrías originales y sus vecinos, y se almacenan en un nuevo GeoDataFrame.

    Parameters:
    df : GeoDataFrame
        Un GeoDataFrame que contiene las geometrías y sus vecinos correspondientes.
        
    gdf_original : GeoDataFrame
        El GeoDataFrame original del cual provienen las geometrías y vecinos, utilizado para obtener la geometría del vecino.

    Returns:
    GeoDataFrame
        Un nuevo GeoDataFrame que contiene las nuevas geometrías combinadas y sus vecinos.
    
    """
        combinaciones = []
        for idx, row in df.iterrows():
            if row['neighbors']:
                for neighbor_id in row['neighbors']:
                    if neighbor_id > row['id']:  # Para evitar duplicados y combinaciones inversas
                        new_geom = unary_union([row['geometry'], gdf_original.loc[neighbor_id, 'geometry']])
                        new_neighbors = list(set(row['neighbors'] + gdf_original.loc[neighbor_id, 'neighbors']) - {row['id'], neighbor_id})
                        combinaciones.append({'geometry': new_geom, 'neighbors': new_neighbors})
        return gpd.GeoDataFrame(combinaciones, columns=['geometry', 'neighbors'])

    # Inicializar DataFrame de combinaciones
    combinaciones_gdf = combinar_vecinos(gdf, gdf)

    combinaciones_gdf.reset_index(drop=True, inplace=True)
    gdf = gpd.GeoDataFrame(pd.concat([gdf, combinaciones_gdf], ignore_index=True))
    gdf['id'] = range(len(gdf))
    gdf['neighbors'] = gdf.apply(lambda row: gdf[gdf.geometry.touches(row['geometry'])]['id'].tolist(), axis=1)
    combinaciones_gdf = combinar_vecinos(gdf, gdf)
    
    return combinaciones_gdf

def dice_coefficient(poly1, poly2):
    intersection_area = poly1.intersection(poly2).area
    return 2 * intersection_area / (poly1.area + poly2.area)

def reproyectar_poligonos(poligonos_1990, poligonos_2020, combinaciones_gdf):
    """
    Reemplaza los polígonos en un GeoDataFrame global `poligonos_1990` con los polígonos más similares
    de otro GeoDataFrame `combinaciones_gdf` utilizando el coeficiente de Dice para medir la similitud.

    Parameters:
    combinaciones_gdf (GeoDataFrame): GeoDataFrame con las combinaciones de polígonos vecinos.

    Returns:
    GeoDataFrame: Nuevo GeoDataFrame con los polígonos de `poligonos_1990` reemplazados por los más similares
                  de `combinaciones_gdf`.

    El proceso se realiza de la siguiente manera:
    1. Inicializa una lista para almacenar los nuevos polígonos.
    2. Itera sobre cada polígono en `poligonos_1990`.
    3. Para cada polígono en `poligonos_1990`, itera sobre cada polígono en `combinaciones_gdf` para encontrar
       el polígono más similar utilizando el coeficiente de Dice.
    4. Agrega el polígono más similar a la lista `poligonos_reemplazados`.
    5. Si no se encuentra un polígono similar, se mantiene el polígono original.
    6. Crea un nuevo GeoDataFrame `correccion_1990` con los polígonos reemplazados.
    7. Devuelve el GeoDataFrame corregido.
    """
    # Crear una lista para almacenar los nuevos polígonos
    poligonos_reemplazados = []

    # Iteramos sobre cada polígono en poligonos_1990
    for index_1990, row_1990 in poligonos_1990.iterrows():
        pol1990 = row_1990['geometry']

        # Inicializamos variables para guardar el polígono más similar y la mayor similitud
        max_similarity = 0
        most_similar_polygon = None

        # Iteramos sobre cada polígono en combinaciones_gdf
        for index_comb, row_comb in combinaciones_gdf.iterrows():
            poly = row_comb['geometry']

            # Verificar si los polígonos tienen área no nula
            if poly.area == 0 or pol1990.area == 0:
                continue

            # Calcular la similitud
            similarity = dice_coefficient(pol1990, poly)

            if similarity > max_similarity:
                max_similarity = similarity
                most_similar_polygon = poly

        # Añadimos el polígono más similar a la lista
        if most_similar_polygon is not None:
            poligonos_reemplazados.append(most_similar_polygon)
        else:
            poligonos_reemplazados.append(pol1990)  # Si no se encontró similar, mantenemos el original

    # Crear un nuevo GeoDataFrame con los polígonos reemplazados
    correccion_1990 = gpd.GeoDataFrame(poligonos_1990.drop(columns='geometry'), geometry=poligonos_reemplazados)
    
    return correccion_1990

def plot_ageb(ciudad, poligonos_interseccion2020, poligonos_1990, correccion_1990):
    plt.rcParams['font.family'] = 'Arial'
    sns.set(style="darkgrid")

    fig, ax = plt.subplots(1, 2, figsize=(15, 8))

    # Graficar los polígonos originales
    poligonos_interseccion2020.plot(ax=ax[0], color='#ffffcc', edgecolor='black', alpha=0.3)
    poligonos_1990.plot(ax=ax[0], color='none', edgecolor='#d7191c')
    ax[0].set_title('Polígonos Originales (1990)', fontsize=14)

    # Graficar los polígonos reproyectados
    poligonos_interseccion2020.plot(ax=ax[1], color='#ffffcc', edgecolor='black', alpha=0.3)
    correccion_1990.plot(ax=ax[1], color='none', edgecolor='#253494')
    ax[1].set_title('Polígonos Reproyectados', fontsize=14)

    # Eliminar los números en los ejes X y Y
    for axis in ax:
        axis.set_xticks([])
        axis.set_yticks([])

    # título 
    plt.suptitle(f'{ciudad.upper()}', fontsize=16, fontweight='bold', y=0.85)
    plt.savefig(f'graficos/{ciudad}_reproyeccion57.png', dpi=300, bbox_inches='tight')
    plt.show()
